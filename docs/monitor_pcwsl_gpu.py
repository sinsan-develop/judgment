"""PCWSL 호스트에서 Windows GPU 계수를 atomic snapshot으로 기록한다.

Windows/CIM 조회만 수행하며 torch/GPU context/모델을 생성하지 않는다.
실행: python3 docs/monitor_pcwsl_gpu.py --output ABS --stop-file ABS
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from judgment.gpu_snapshot import parse_adapter_memory
from judgment.telemetry import append_json, atomic_json


def record_operation(operation, *, timeout=1.):
    finished=threading.Event();result={}
    def record():
        try: operation();result.update(failure_kind=None)
        except Exception as exc:
            result.update(failure_kind='exception',exception_type=type(exc).__name__,errno=getattr(exc,'errno',None))
        finally: finished.set()
    start=time.monotonic()
    threading.Thread(target=record,daemon=True).start()
    if not finished.wait(timeout): return dict(failure_kind='timeout',elapsed_seconds=time.monotonic()-start)
    return dict(result,elapsed_seconds=time.monotonic()-start)


def failure_note(fd,detail):
    try: owned=os.dup(fd)
    except OSError:return
    def write():
        try:os.write(owned,(json.dumps(detail)+'\n').encode())
        finally:os.close(owned)
    record_operation(write,timeout=.02)


def publish_live_snapshot(output,value,*,timing=None):
    # 두 슬롯을 번갈아 쓴다. 독자는 JSON이 완성된 최신 fresh 슬롯을 사용한다.
    # 한 슬롯 쓰기 중에는 다른 슬롯을 읽으며 replace/fsync를 기다리지 않는다.
    started=time.perf_counter();payload=json.dumps(value,allow_nan=False)
    if timing is not None:timing['serialize']=time.perf_counter()-started
    slot=getattr(publish_live_snapshot,'slot',0)
    target=Path(output).with_name(Path(output).name+f'.slot{slot}')
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        stream.write(payload);stream.flush()
    publish_live_snapshot.slot=1-slot
    if timing is not None:timing['total']=time.perf_counter()-started


def main(output, stop_file):
    command = ['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
               '-NoProfile', '-NonInteractive', '-Command',
               'Get-CimInstance Win32_PerfRawData_GPUPerformanceCounters_GPUAdapterMemory | '
               'Select-Object Name,DedicatedUsage,SharedUsage,TotalCommitted | ConvertTo-Json -Compress']
    output = output.resolve(); stop_file = stop_file.resolve()
    if not output.is_relative_to(ROOT / '.work') or not stop_file.is_relative_to(ROOT / '.work'):
        raise ValueError('monitor_path_outside_project')
    deadline = time.monotonic() + 1900
    # 일반 atomic/fsync 경로와 분리된 원문 없는 최소 진단. 대기를 추가하지 않는다.
    failure_fd=os.open(output.with_name(output.stem+'.failures.private.jsonl'),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:
        produce(command,output,stop_file,deadline,failure_fd)
    finally: os.close(failure_fd)


def produce(command,output,stop_file,deadline,failure_fd):
    while not stop_file.exists() and time.monotonic() < deadline:
        raw = subprocess.check_output(command, text=True, encoding='utf-8-sig', timeout=10)
        # 조회 중 요청된 정상 종료에서는 새 저장을 시작하지 않는다.
        if stop_file.exists(): return
        rows=json.loads(raw)
        if isinstance(rows,dict): rows=[rows]
        value = dict(bytes_used=parse_adapter_memory(rows), sampled_epoch=time.time(),adapters=rows,
                     scope='windows_gpu_adapter_upper_bound', producer_pid=os.getpid())
        timing={}
        result=record_operation(lambda:publish_live_snapshot(output,value,timing=timing))
        if result['failure_kind']:
            detail=dict(result,operation='snapshot',sampled_epoch=value['sampled_epoch'],failed_epoch=time.time(),stop_seen=stop_file.exists(),timing=dict(timing))
            failure_note(failure_fd,detail)
            raise RuntimeError('snapshot_recording_failed')
        # 기록 I/O가 막히면 생산자는 종료하며 독립 guard가 stale snapshot을 거절한다.
        history=output.with_name(output.stem+'.history.private.jsonl')
        result=record_operation(lambda:append_json(history,value,sync=False))
        if result['failure_kind']:
            failure_note(failure_fd,dict(result,operation='history',failed_epoch=time.time(),stop_seen=stop_file.exists()))
            raise RuntimeError('history_recording_failed')
        time.sleep(.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.stop_file)
