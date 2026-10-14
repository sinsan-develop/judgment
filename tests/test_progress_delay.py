import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from judgment.telemetry import Telemetry
from tests.test_memory_monitor import temporary_folder

class ProgressDelayTests(unittest.TestCase):
    def test_progress_wait_delay_does_not_mark_safety_failed(self):
        gate=threading.Event()
        with temporary_folder() as name:
            p=Path(name);t=Telemetry(p,role='worker',memory=lambda:{},timeout=.03)
            with patch('judgment.telemetry.atomic_json',side_effect=lambda *a,**k:gate.wait(2)):
                try:
                    t.__enter__()
                    self.assertFalse(t.failed.is_set());self.assertTrue(t.delayed.is_set())
                    deadline=time.monotonic()+1
                    while not (p/'telemetry.delay.min.private.jsonl').stat().st_size and time.monotonic()<deadline:time.sleep(.01)
                    row=json.loads((p/'telemetry.delay.min.private.jsonl').read_text().splitlines()[0])
                    self.assertEqual(row['classification'],'progress_delay')
                finally:gate.set();t.__exit__(None,None,None)

    def test_event_releases_state_lock_before_waiting_on_io(self):
        with temporary_folder() as name:
            t=Telemetry(Path(name),role='worker',memory=lambda:{})
            with t:
                held=[];original=t._wait_record
                def check(done):
                    result=[]
                    def acquire():
                        got=t.lock.acquire(timeout=.05);result.append(got)
                        if got:t.lock.release()
                    thread=threading.Thread(target=acquire);thread.start();thread.join(.2);held.append(result==[True]);return original(done)
                t._wait_record=check;t.event('model_load')
                self.assertTrue(all(held))
