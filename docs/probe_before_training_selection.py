"""고정 선택 자료의 학습 전 평가만 측정. optimizer·학습·final-test 접근 없음."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--probe-id',required=True)
args=parser.parse_args();root=args.root.resolve();os.chdir(root);sys.path.insert(0,str(root/'src'))
from judgment.contracts import RunConfig
from judgment.runner import _worker_limits,_memory,training_arguments
from judgment.telemetry import Telemetry,gpu_baseline,atomic_json,own_memory
from judgment.laya_adapter import LayaAdapter,offline
from judgment.replay import install_final_test_guard
from judgment.evaluation_memory import bounded_evaluation_forward

if not args.probe_id.replace('-','').isalnum():raise ValueError('probe_id')
folder=root/'.work/preselection_probe'/args.probe_id;folder.mkdir(parents=True,exist_ok=False)
c=json.loads((root/'.work/data_review/g1-78068da517cd.config.private.json').read_text());install_final_test_guard(RunConfig(c))
selection=root/'.work/data/selection.jsonl'
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
input_digest=digest(selection);weight=Path(c['model_dir'])/'model.safetensors';weight_digest=digest(weight)
gpu_baseline(c['resources']['gpu_memory_snapshot_path'],folder/'gpu.baseline.private.json',limit=6*1024**3)
start=time.monotonic()
with Telemetry(folder,role='worker') as t:
    with _worker_limits(RunConfig(c),folder) as resources,offline():
        with t.phase('model_load'):
            adapter=LayaAdapter.from_local(Path(c['model_dir']),source_commit=c['source_commit'],model_revision=c['model_revision'],device=c['device'])
        import torch
        import numpy as np
        import laya.train as upstream
        config=upstream.TrainConfig(**training_arguments(RunConfig(c),Path('unused-train'),selection,folder)['config'])
        cfg=adapter.backend.cfg;max_len=config.max_len or cfg.get('max_len',512);head_max_len=config.head_max_len or cfg.get('head_max_len',192)
        parallel=upstream.uses_parallel_layout(cfg);device=torch.device(c['device'])
        rows=upstream.read_data(str(selection),text_column=config.text_column,label_column=config.label_column,question_id=config.question_id,instructions=config.instructions)
        items,skipped=upstream.items_from_rows(adapter.backend.tok,rows,max_len,head_max_len,label_smoothing=0.)
        if len(items)!=374 or skipped:raise ValueError('selection_items_changed')
        sample=upstream.collate_items([[upstream.encode_item(adapter.backend.tok,x,max_len,head_max_len,parallel=parallel) for x in items[:16]]],adapter.backend.tok.pad_token_id)
        with torch.no_grad(),t.phase('score_equivalence_sample'):
            reference=[]
            for i in range(0,16,2):
                batch={k:v[i:i+2] for k,v in sample.items()}
                reference.append(upstream._forward(adapter.backend.model,batch,device,amp=False,detach_encoder=False).cpu())
            reference=torch.cat(reference)
            with bounded_evaluation_forward(upstream):actual=upstream._forward(adapter.backend.model,sample,device,amp=False,detach_encoder=False)
            max_abs=float((reference-actual).abs().max())
            close=bool(torch.allclose(reference,actual,rtol=1e-5,atol=1e-5))
            same_top=bool(torch.equal(reference.argmax(1),actual.argmax(1)))
            if not close or not same_top:raise ValueError('score_equivalence_failed')
        del sample,reference,actual
        torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
        with t.phase('before_training_selection'),bounded_evaluation_forward(upstream):
            records=upstream.calibration_records(adapter.backend.model,adapter.backend.tok,items,device,max_len,head_max_len,parallel=parallel)
        if len(records)!=374 or any(not np.isfinite(row[1]).all() for row in records):raise ValueError('evaluation_records')
        metrics=upstream.evaluate_records(records,cfg.get('temperature'),cfg.get('temperature_by_options'))
        memory=own_memory(_memory);t.event('selection_evaluation_complete',position=len(records))
        atomic_json(folder/'scores.private.json',dict(records=[dict(qtype=int(qt),logits=np.asarray(logits).tolist(),target=np.asarray(target).tolist(),k=int(k)) for qt,logits,target,k in records],metrics=metrics))
if digest(selection)!=input_digest or digest(weight)!=weight_digest:raise ValueError('source_changed')
atomic_json(folder/'summary.private.json',dict(status='preselection_evaluation_verified',items=374,collate_batch_size=16,gpu_forward_batch_size=1,
    no_grad=True,model_eval=True,outputs_cpu=True,score_sample_items=16,reference_forward_batch_size=2,score_sample_max_abs=max_abs,score_sample_close=close,score_sample_same_top=same_top,
    own_memory=memory,resources=resources,elapsed_seconds=time.monotonic()-start,optimizer_updates=0,training_started=False,final_test_opened=False,
    input_preserved=True,initial_weight_preserved=True,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
print('PRESELECTION_EVALUATION_VERIFIED',flush=True)
