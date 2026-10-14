"""모델 없이 실제 worker 감시·종료와 /proc 오류 분류를 검증한다."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from judgment.contracts import ConfigError, RunConfig
import judgment.runner as runner
from judgment.telemetry import Telemetry

TMP=Path(__file__).resolve().parents[1]/'.work/tmp/memory-monitor-tests'
TMP.mkdir(parents=True,exist_ok=True)


@contextmanager
def temporary_folder():
    temporary=tempfile.TemporaryDirectory(dir=TMP)
    try: yield temporary.name
    finally:
        deadline=time.monotonic()+2
        while True:
            try: temporary.cleanup();break
            except PermissionError:
                # bounded 중단 write의 fsync가 끝나기 전 Windows 파일 handle 경합.
                if time.monotonic()>=deadline: raise
                time.sleep(.02)


class MemoryMonitorTests(unittest.TestCase):
    @unittest.skipIf(os.name=='nt','PCWSL /proc 경계')
    def test_proc_missing_rss_and_read_failure_are_distinguished(self):
        for content,expected in [('State:\tZ (zombie)\n','rss_missing'),('VmRSS:\tinvalid kB\n','rss_parse_error')]:
            with self.subTest(expected=expected),patch.object(Path,'read_text',return_value=content):
                with self.assertRaises(ConfigError) as ctx: runner._memory(123)
                self.assertEqual(ctx.exception.monitor_detail['failure_kind'],expected)
        with patch.object(Path,'read_text',side_effect=PermissionError(13,'private message')):
            with self.assertRaises(ConfigError) as ctx: runner._memory(123)
            self.assertEqual(ctx.exception.monitor_detail['failure_kind'],'proc_read_error')
            self.assertEqual(ctx.exception.monitor_detail['errno'],13)
            self.assertNotIn('private message',json.dumps(ctx.exception.monitor_detail))

    def run_dummy(self,folder,code,*,device='cpu',duration=15):
        snapshot=os.environ.get('JUDGMENT_GPU_MEMORY_SNAPSHOT')
        resources=dict(time_limit_seconds=duration+15,ram_limit_bytes=24*1024**3,vram_limit_bytes=6*1024**3,
                       disk_limit_bytes=30*1024**3,estimated_disk_bytes=0)
        if snapshot: resources['gpu_memory_snapshot_path']=snapshot
        config=RunConfig(dict(device=device,resources=resources,code_revision='synthetic',source_commit='synthetic',
                             model_revision='synthetic',seed=13,training={'freeze_encoder':True}))
        with Telemetry(folder,role='parent',memory=lambda:{}) as telemetry:
            return runner._training_process(config,folder,[sys.executable,'-c',code],dict(os.environ),None,telemetry).values

    def test_worker_exit_code_is_recorded(self):
        with temporary_folder() as name:
            result=self.run_dummy(Path(name),'import time;time.sleep(.3);raise SystemExit(7)')
            self.assertEqual(result['worker_returncode'],7)
            self.assertEqual(json.loads((Path(name)/'worker.exit.private.json').read_text())['returncode'],7)

    def test_exit_during_rss_sample_preserves_worker_exit_code(self):
        def raced(pid):
            time.sleep(.5)
            raise ConfigError('memory_monitor_unavailable')
        with temporary_folder() as name,patch.object(runner,'_memory',side_effect=raced):
            result=self.run_dummy(Path(name),'import time;time.sleep(.1);raise SystemExit(7)')
            self.assertEqual(result['worker_returncode'],7)
            self.assertEqual(result['reason'],'worker_failed')
            self.assertNotIn('monitor_failure',result)

    def test_monitor_failure_stops_only_owned_worker_and_records_detail(self):
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        original=runner._memory
        def fail(pid):
            if pid!=os.getpid():
                error=ConfigError('memory_monitor_unavailable')
                error.monitor_detail=dict(failure_kind='proc_read_error',pid=pid,errno=13)
                raise error
            return original(pid)
        try:
            with temporary_folder() as name,patch.object(runner,'_memory',side_effect=fail):
                start=time.monotonic();result=self.run_dummy(Path(name),'import time;time.sleep(30)')
                self.assertLess(time.monotonic()-start,5)
                self.assertEqual(result['reason'],'memory_monitor_unavailable')
                self.assertEqual(result['monitor_failure']['failure_kind'],'proc_read_error')
                self.assertIsNotNone(result['worker_returncode'])
                stop=json.loads((Path(name)/'limit_failure.json').read_text())
                self.assertEqual(stop['monitor_failure']['errno'],13)
                self.assertIsNone(unrelated.poll())
                self.assertEqual(runner._ACTIVE_WORKERS,[])
        finally: unrelated.terminate();unrelated.wait(timeout=3)

    @unittest.skipUnless(os.environ.get('JUDGMENT_MONITOR_SECONDS'),'승인된 현지 장시간 시험에서만 수행')
    def test_live_monitor_exceeds_previous_stop_without_model(self):
        duration=float(os.environ['JUDGMENT_MONITOR_SECONDS'])
        self.assertGreaterEqual(duration,180)
        with temporary_folder() as name:
            result=self.run_dummy(Path(name),f'import time;time.sleep({duration})',device='cuda',duration=duration)
            self.assertEqual(result['worker_returncode'],0)
            self.assertNotIn('monitor_failure',result)
            self.assertGreaterEqual(result['elapsed_seconds'],duration)
            self.assertLessEqual(result['peak_vram_bytes'],6*1024**3)
            self.assertNotIn('torch',sys.modules)
            print('MODEL_FREE_MONITOR',json.dumps({k:result[k] for k in ['elapsed_seconds','worker_returncode','peak_ram_bytes','peak_vram_bytes']}),flush=True)
