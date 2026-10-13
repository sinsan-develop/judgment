import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from judgment.contracts import RunConfig, ConfigError, SOURCE_COMMIT
from judgment.data import split_groups
from judgment.runner import preflight, run_training, training_arguments, assess_weight_change
from tests.test_data import examples, RATIOS


class RunnerTests(unittest.TestCase):
    def test_missing_approval_or_resource_limit_blocks_training(self):
        b = split_groups(examples(),ratios=RATIOS,seed=1)
        with patch('socket.socket',side_effect=AssertionError('network')):
            with self.assertRaises(ConfigError): run_training(RunConfig({'mode':'real'}), b)
        self.assertEqual(preflight(RunConfig({'mode':'fixture'})).values['training_allowed'],False)

    def test_only_train_reaches_optimizer_and_no_internal_resplit(self):
        c = RunConfig({'seed':7, 'device':'cuda', 'training':dict(epochs=1,micro_batch=1,grad_accum=1,encoder_lr=1e-5,head_lr=1e-4,freeze_encoder=True,precision='fp32')})
        args = training_arguments(c, 'train.jsonl', 'selection.jsonl', 'output')
        self.assertEqual(args['data'],'train.jsonl')
        self.assertEqual(args['config']['eval_data'],'selection.jsonl')
        self.assertEqual(args['config']['calib_frac'],0)
        self.assertEqual(args['config']['calib_max'],0)
        self.assertEqual(args['config']['loss'],'soft-ce')
        self.assertEqual(args['config']['shuffle_options'],('choice',))
        self.assertNotIn('test', json.dumps(args))
        self.assertNotIn('calibration.jsonl', json.dumps(args))

    def test_no_weight_change_is_not_trained(self):
        before = {'head': {'shape':[2,2],'digest':'a','numel':4}}
        self.assertFalse(assess_weight_change(before,before)['trained'])
        after = {'head': {'shape':[2,2],'digest':'b','numel':4}}
        self.assertEqual(assess_weight_change(before,after)['changed_tensors'],1)

    def test_resource_budget_counts_duplicate_checkpoint(self):
        from judgment.runner import resource_budget
        with self.assertRaisesRegex(ConfigError,'disk_budget'):
            resource_budget({'estimated_disk_bytes':100,'checkpoint_bytes':100,'disk_limit_bytes':250}, free_bytes=1000)
        self.assertEqual(resource_budget({'estimated_disk_bytes':100,'checkpoint_bytes':100,'disk_limit_bytes':300}, free_bytes=1000),300)

    def test_logs_contain_no_raw_text_and_fixture_never_trained(self):
        b = split_groups(examples(),ratios=RATIOS,seed=1)
        evidence = run_training(RunConfig({'mode':'fixture'}), b).values
        self.assertFalse(evidence['trained']); self.assertEqual(evidence['status'],'fixture_only')
        self.assertNotIn('예약', json.dumps(evidence,ensure_ascii=False))

    def test_test_set_not_opened_during_training(self):
        from judgment.runner import training_rows
        b = split_groups(examples(),ratios=RATIOS,seed=1)
        class Forbidden:
            def __iter__(self): raise AssertionError('test opened')
        b.parts['test'] = Forbidden()
        train, selection = training_rows(b)
        self.assertEqual(len(train),2); self.assertEqual(len(selection),2)

    def test_duplicate_checkpoint_count_and_precision(self):
        from judgment.runner import training_arguments
        c = RunConfig({'seed':1,'device':'cuda','training':dict(epochs=1,micro_batch=1,grad_accum=1,encoder_lr=1e-5,head_lr=1e-4,freeze_encoder=True,precision='bf16')})
        self.assertTrue(training_arguments(c,'train','selection','output')['config']['amp'])
