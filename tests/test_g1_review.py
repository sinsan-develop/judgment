import unittest
from unittest.mock import patch
from pathlib import Path
from judgment.contracts import ConfigError,RunConfig,RunEvidence
from judgment.runner import final_storage_check,validate_upstream_execution


class G1ReviewTests(unittest.TestCase):
    def test_final_storage_uses_actual_total_not_estimate(self):
        c=RunConfig({'resources':{'disk_limit_bytes':100,'estimated_disk_bytes':1}})
        with patch('judgment.runner._storage_bytes',return_value=101),self.assertRaisesRegex(ConfigError,'disk_limit'):
            final_storage_check(c,Path('unused'))
        with patch('judgment.runner._storage_bytes',return_value=100):
            self.assertEqual(final_storage_check(c,Path('unused')),100)

    def test_skip_or_partial_optimizer_run_cannot_complete(self):
        c=RunConfig({'data_manifest':{'counts':{'train':697,'selection':374}},'training':{'epochs':1,'micro_batch':1,'grad_accum':8}})
        good={'train_items':697,'eval_items':374,'calibration_items':0,'skipped':{}}
        validate_upstream_execution(c,good,observed_steps=88)
        for bad,steps in [(dict(good,train_items=1),88),(dict(good,skipped={'invalid_target':1}),88),(good,87)]:
            with self.assertRaises(ConfigError):validate_upstream_execution(c,bad,observed_steps=steps)

    def test_real_failed_cli_is_nonzero(self):
        from judgment.__main__ import main
        c=RunConfig({'mode':'real'})
        with patch('sys.argv',['judgment','train','--config','unused']),patch.object(Path,'read_text',return_value='{"mode":"real"}'),patch('judgment.__main__.validate_run_config',return_value=c),patch('judgment.__main__.preflight'),patch('judgment.__main__.load_real_bundle'),patch('judgment.__main__.run_training',return_value=RunEvidence({'status':'failed','trained':False})):
            self.assertNotEqual(main(),0)
