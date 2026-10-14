"""승인된 현지 모델 로드·기록 검증만 수행. 자료·optimizer·평가를 열지 않는다."""
import argparse
from copy import deepcopy
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--probe-id',required=True)
parser.add_argument('--repeat-records',type=int,default=0)
args=parser.parse_args();root=args.root.resolve();os.chdir(root);sys.path.insert(0,str(root/'src'))
from judgment.contracts import RunConfig
from judgment.runner import _worker_limits, _memory
from judgment.telemetry import Telemetry,gpu_baseline,atomic_json,own_memory
from judgment.laya_adapter import LayaAdapter,offline
from judgment.replay import install_final_test_guard

if not args.probe_id.replace('-','').isalnum():raise ValueError('probe_id')
folder=root/'.work/model_load_probe'/args.probe_id;folder.mkdir(parents=True,exist_ok=False)
c=deepcopy(json.loads((root/'.work/data_review/g1-78068da517cd.config.private.json').read_text()))
install_final_test_guard(RunConfig(c))
gpu_baseline(c['resources']['gpu_memory_snapshot_path'],folder/'gpu.baseline.private.json',limit=6*1024**3)
start=time.monotonic()
with Telemetry(folder,role='worker') as t:
    with _worker_limits(RunConfig(c),folder),offline():
        with t.phase('framework_import'):
            import torch
        before=own_memory(_memory);t.event('device_before_load')
        with t.phase('model_load'):
            adapter=LayaAdapter.from_local(Path(c['model_dir']),source_commit=c['source_commit'],model_revision=c['model_revision'],device=c['device'])
        after=own_memory(_memory);t.event('device_after_load')
        for i in range(args.repeat_records):
            t.event('repeated_progress',position=i+1);time.sleep(.5)
        time.sleep(2);t.event('model_load_verified')
        del adapter;gc.collect();torch.cuda.empty_cache()
atomic_json(folder/'summary.private.json',dict(status='model_load_and_telemetry_complete',elapsed_seconds=time.monotonic()-start,
    before=before,after=after,optimizer_updates=0,training_started=False,final_test_opened=False,
    repeated_records=args.repeat_records,
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
print('MODEL_LOAD_AND_TELEMETRY_COMPLETE',flush=True)
