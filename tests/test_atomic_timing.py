import json
from pathlib import Path
import tempfile
import unittest
from judgment.telemetry import atomic_json

class AtomicTimingTests(unittest.TestCase):
    def test_atomic_timing_preserves_data_and_covers_io_stages(self):
        root=Path(__file__).resolve().parents[1]/'.work/tmp';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as name:
            p=Path(name)/'saved.json';m={};value={'text':'합성', 'value':1}
            atomic_json(p,value,timing=m)
            self.assertEqual(json.loads(p.read_text()),value)
            for key in ['serialize','open','write','flush','fsync','close','replace','cleanup','total']:
                self.assertGreaterEqual(m[key],0)
