"""WSL의 전체 호스트 GPU 계수를 읽는다. 조회를 위해 GPU context를 만들지 않는다."""
import json
from pathlib import Path
import time
from .contracts import ConfigError


def parse_adapter_memory(rows):
    if isinstance(rows, dict): rows = [rows]
    if not isinstance(rows, list) or not rows: raise ConfigError('vram_monitor_unavailable')
    total = 0
    for row in rows:
        if not isinstance(row, dict): raise ConfigError('vram_monitor_unavailable')
        values = [row.get(k) for k in ('DedicatedUsage', 'SharedUsage', 'TotalCommitted')]
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values):
            raise ConfigError('vram_monitor_unavailable')
        dedicated, shared, committed = values
        total += max(dedicated + shared, committed)
    return total


def read_gpu_snapshot(path, *, now=None, observation=None):
    try: value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): raise ConfigError('vram_monitor_unavailable') from None
    used=validate_gpu_snapshot(value,now=now)
    if observation is not None: observation.update(value)
    return used


def validate_gpu_snapshot(value, *, now=None):
    now = time.time() if now is None else now
    if not isinstance(value, dict): raise ConfigError('vram_monitor_unavailable')
    stamp, used = value.get('sampled_epoch'), value.get('bytes_used')
    if (value.get('scope') != 'windows_gpu_adapter_upper_bound' or
        isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not 0 <= now-stamp <= 15 or
        isinstance(used, bool) or not isinstance(used, int) or used < 0 or
        isinstance(value.get('producer_pid'), bool) or not isinstance(value.get('producer_pid'), int) or value['producer_pid'] <= 0):
        raise ConfigError('vram_monitor_unavailable')
    return used
