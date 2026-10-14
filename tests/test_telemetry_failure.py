import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from judgment.telemetry import Telemetry
from judgment.contracts import ConfigError

TMP=Path(__file__).resolve().parents[1]/'.work/tmp/telemetry-failure-tests'
TMP.mkdir(parents=True,exist_ok=True)

class FailureTests(unittest.TestCase):
    def read_failure(self,p):
        f=p/'telemetry.failure.min.private.jsonl';deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if f.exists() and f.stat().st_size:
                try:return json.loads(f.read_text().splitlines()[0])
                except ValueError:pass
            time.sleep(.01)
        self.fail('missing independent failure log')

    def test_writer_exception_survives_failed_normal_logger(self):
        with tempfile.TemporaryDirectory(dir=TMP) as name:
            p=Path(name);t=Telemetry(p,role='worker',memory=lambda:{})
            with patch('judgment.telemetry.append_json',side_effect=PermissionError(13,'secret raw text')):
                with self.assertRaises(ConfigError):t.__enter__()
            row=self.read_failure(p)
            self.assertEqual(row['operation'],'writer.append_json')
            self.assertEqual(row['exception_type'],'PermissionError');self.assertEqual(row['errno'],13)
            self.assertNotIn('secret',json.dumps(row))

    def test_wait_timeout_records_inflight_call_and_stage(self):
        with tempfile.TemporaryDirectory(dir=TMP) as name:
            p=Path(name);t=Telemetry(p,role='worker',memory=lambda:{},timeout=.03)
            with patch('judgment.telemetry.append_json',side_effect=lambda *a:time.sleep(.15)):
                t.__enter__()
            self.assertFalse(t.failed.is_set());self.assertTrue(t.delayed.is_set())
            row=json.loads((p/'telemetry.delay.min.private.jsonl').read_text().splitlines()[0])
            self.assertEqual(row['operation'],'submit.wait_timeout')
            self.assertEqual(row['stage'],'started');self.assertEqual(row['inflight_operation'],'writer.append_json')
            time.sleep(.3);t.__exit__(None,None,None)
