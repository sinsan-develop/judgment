"""독립 임시 모델: 기존 평가374건 후 실제 학습16노출/AdamW2회만. 가중치 저장·재사용 없음."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--probe-id',required=True)
args=parser.parse_args();root=args.root.resolve();os.chdir(root);sys.path.insert(0,str(root/'src'))
from judgment.contracts import RunConfig
from judgment.runner import _worker_limits,_memory,training_arguments,observe_optimizer_steps
from judgment.telemetry import Telemetry,gpu_baseline,atomic_json,own_memory
from judgment.laya_adapter import LayaAdapter,offline
from judgment.replay import install_final_test_guard
from judgment.evaluation_memory import bounded_evaluation_forward

if not args.probe_id.replace('-','').isalnum():raise ValueError('probe_id')
folder=root/'.work/training_probe'/args.probe_id;folder.mkdir(parents=True,exist_ok=False)
c=json.loads((root/'.work/data_review/g1-78068da517cd.config.private.json').read_text());install_final_test_guard(RunConfig(c))
train=root/'.work/data/train.jsonl';selection=root/'.work/data/selection.jsonl';weight=Path(c['model_dir'])/'model.safetensors'
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
before={str(p):digest(p) for p in (train,selection,weight)}
gpu_baseline(c['resources']['gpu_memory_snapshot_path'],folder/'gpu.baseline.private.json',limit=6*1024**3)
start=time.monotonic()
class ProbeComplete(Exception):pass
counts=dict(forward=0,backward=0)
with Telemetry(folder,role='worker') as t:
    with _worker_limits(RunConfig(c),folder) as resources,offline():
        with t.phase('model_load'):
            adapter=LayaAdapter.from_local(Path(c['model_dir']),source_commit=c['source_commit'],model_revision=c['model_revision'],device=c['device'])
        import torch
        import laya.train as upstream
        config=upstream.TrainConfig(**training_arguments(RunConfig(c),train,selection,folder)['config'])
        cfg=adapter.backend.cfg;max_len=config.max_len or cfg.get('max_len',512);head_max_len=config.head_max_len or cfg.get('head_max_len',192)
        parallel=upstream.uses_parallel_layout(cfg);device=torch.device(c['device'])
        def items(path):
            rows=upstream.read_data(str(path),text_column=config.text_column,label_column=config.label_column,question_id=config.question_id,instructions=config.instructions)
            result,skipped=upstream.items_from_rows(adapter.backend.tok,rows,max_len,head_max_len,label_smoothing=0.)
            if skipped:raise ValueError('input_skipped')
            return result
        train_items=items(train);selection_items=items(selection)
        if len(train_items)!=697 or len(selection_items)!=374:raise ValueError('input_counts')
        with t.phase('before_training_selection'),bounded_evaluation_forward(upstream):
            records=upstream.calibration_records(adapter.backend.model,adapter.backend.tok,selection_items,device,max_len,head_max_len,parallel=parallel)
        evaluation_memory=own_memory(_memory);del records
        original_forward=upstream._forward;original_backward=torch.Tensor.backward
        head_before={n:p.detach().cpu().clone() for n,p in adapter.backend.model.named_parameters() if not n.startswith('encoder.')}
        def forward(*a,**k):
            if counts['forward']==16:raise ProbeComplete()
            with t.phase('training_forward'):result=original_forward(*a,**k)
            counts['forward']+=1
            return result
        def backward(tensor,*a,**k):
            with t.phase('training_backward'):result=original_backward(tensor,*a,**k)
            counts['backward']+=1
            return result
        with observe_optimizer_steps(t) as observed,patch.object(upstream,'_forward',forward),patch.object(torch.Tensor,'backward',backward):
            try:upstream.train_model(adapter.backend.model,adapter.backend.tok,train_items,config,device,max_len,head_max_len,parallel=parallel)
            except ProbeComplete:pass
        updates=observed['by_optimizer'].get('AdamW',0)
        changed=sum(not torch.equal(head_before[n],p.detach().cpu()) for n,p in adapter.backend.model.named_parameters() if n in head_before)
        if counts!={'forward':16,'backward':16} or updates!=2 or changed==0:raise ValueError('training_probe_incomplete')
        torch.cuda.synchronize();memory=own_memory(_memory);t.event('temporary_training_verified',position=16)
        del adapter,head_before;gc.collect();torch.cuda.empty_cache();t.event('temporary_model_released')
if before!={str(p):digest(p) for p in (train,selection,weight)}:raise ValueError('source_changed')
atomic_json(folder/'summary.private.json',dict(status='temporary_training_verified',elapsed_seconds=time.monotonic()-start,counts=counts,
    optimizer_updates=updates,changed_head_tensors=changed,evaluation_memory=evaluation_memory,own_memory=memory,resources=resources,
    initial_weight_preserved=True,inputs_preserved=True,probe_weights_saved=False,probe_weights_reused=False,final_test_opened=False,
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
print('TEMPORARY_TRAINING_VERIFIED',flush=True)
