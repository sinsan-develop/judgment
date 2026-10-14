import importlib.util
from pathlib import Path
import time
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('ab',Path(__file__).parents[1]/'docs/run_ab_comparison.py')
ab=importlib.util.module_from_spec(spec);spec.loader.exec_module(ab)


class StartGateTests(unittest.TestCase):
    def test_three_distinct_consecutive_low_samples_required(self):
        saved=[];values=iter([2,2,3,2,2,2])
        def load(_):
            used=next(values)
            stamp=saved[0]['sampled_epoch'] if len(saved)==1 else time.time()
            row=dict(sampled_epoch=stamp,bytes_used=int(used*1024**3),scope='windows_gpu_adapter_upper_bound',producer_pid=1)
            saved.append(row);return row
        with patch.object(ab,'load',side_effect=load),patch.object(ab.time,'sleep'):
            result=ab.wait_start_samples('synthetic',timeout=1)
        self.assertEqual(result,saved[-3:])
        self.assertEqual(len({x['sampled_epoch'] for x in result}),3)

    def test_high_gpu_never_passes(self):
        def load(_):return dict(sampled_epoch=time.time(),bytes_used=3*1024**3,scope='windows_gpu_adapter_upper_bound',producer_pid=1)
        with patch.object(ab,'load',side_effect=load),patch.object(ab.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'start_headroom_unavailable'):ab.wait_start_samples('synthetic',timeout=.005)
