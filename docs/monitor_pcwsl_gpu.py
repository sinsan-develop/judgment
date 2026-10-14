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
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from judgment.gpu_snapshot import parse_adapter_memory
from judgment.telemetry import append_json, bounded_save, bounded_call


def main(output, stop_file):
    command = ['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
               '-NoProfile', '-NonInteractive', '-Command',
               'Get-CimInstance Win32_PerfRawData_GPUPerformanceCounters_GPUAdapterMemory | '
               'Select-Object Name,DedicatedUsage,SharedUsage,TotalCommitted | ConvertTo-Json -Compress']
    output = output.resolve(); stop_file = stop_file.resolve()
    if not output.is_relative_to(ROOT / '.work') or not stop_file.is_relative_to(ROOT / '.work'):
        raise ValueError('monitor_path_outside_project')
    deadline = time.monotonic() + 1900
    while not stop_file.exists() and time.monotonic() < deadline:
        raw = subprocess.check_output(command, text=True, encoding='utf-8-sig', timeout=10)
        rows=json.loads(raw)
        if isinstance(rows,dict): rows=[rows]
        value = dict(bytes_used=parse_adapter_memory(rows), sampled_epoch=time.time(),adapters=rows,
                     scope='windows_gpu_adapter_upper_bound', producer_pid=os.getpid())
        if not bounded_save(output,value,timeout=.2): raise RuntimeError('snapshot_recording_failed')
        # 기록 I/O가 막히면 생산자는 종료하며 독립 guard가 stale snapshot을 거절한다.
        history=output.with_name(output.stem+'.history.private.jsonl')
        if not bounded_call(lambda:append_json(history,value),timeout=.2):
            raise RuntimeError('history_recording_failed')
        time.sleep(.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.stop_file)
