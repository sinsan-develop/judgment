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


def main(output, stop_file):
    command = ['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
               '-NoProfile', '-NonInteractive', '-Command',
               'Get-CimInstance Win32_PerfRawData_GPUPerformanceCounters_GPUAdapterMemory | '
               'Select-Object DedicatedUsage,SharedUsage,TotalCommitted | ConvertTo-Json -Compress']
    output = output.resolve(); stop_file = stop_file.resolve()
    if not output.is_relative_to(ROOT / '.work') or not stop_file.is_relative_to(ROOT / '.work'):
        raise ValueError('monitor_path_outside_project')
    deadline = time.monotonic() + 1900
    while not stop_file.exists() and time.monotonic() < deadline:
        raw = subprocess.check_output(command, text=True, encoding='utf-8-sig', timeout=10)
        value = dict(bytes_used=parse_adapter_memory(json.loads(raw)), sampled_epoch=time.time(),
                     scope='windows_gpu_adapter_upper_bound', producer_pid=os.getpid())
        temporary = output.with_suffix('.atomic.tmp')
        temporary.write_text(json.dumps(value), encoding='utf-8')
        os.replace(temporary, output)
        time.sleep(.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.stop_file)
