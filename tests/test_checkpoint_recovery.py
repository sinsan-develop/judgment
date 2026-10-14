import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('ab',Path(__file__).parents[1]/'docs/run_ab_comparison.py')
ab=importlib.util.module_from_spec(spec);spec.loader.exec_module(ab)

class CheckpointRecoveryTests(unittest.TestCase):
    def test_fp16_manifest_validates_shape_bytes_and_nonfinite(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]/'.work') as tmp:
            p=Path(tmp)/'weights'
            def write(values,shape):
                h=json.dumps({'head':dict(dtype='F16',shape=shape,data_offsets=[0,4])}).encode()
                p.write_bytes(struct.pack('<Q',len(h))+h+struct.pack('<ee',*values))
            write([1.,2.],[2]);self.assertEqual(ab.fp16_manifest(p)['head']['shape'],[2])
            write([1.,float('inf')],[2])
            with self.assertRaisesRegex(ValueError,'checkpoint_nonfinite'):ab.fp16_manifest(p)
            write([1.,2.],[3])
            with self.assertRaisesRegex(ValueError,'checkpoint_structure'):ab.fp16_manifest(p)

    def test_remaining_followup_is_a_single_1230_second_deadline(self):
        self.assertEqual(ab.followup_remaining(100.,200.),1130.)
        with self.assertRaisesRegex(ValueError,'followup_time_limit'):ab.followup_remaining(0.,1230.)
