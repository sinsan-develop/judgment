import json
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from judgment.contracts import ConfigError, RunConfig
from judgment.evaluation import audit_public_files
from judgment.runner import training_worker, preflight


class ReviewBoundaryTests(unittest.TestCase):
    def test_worker_requires_full_preflight_before_ml_import(self):
        with patch.object(Path,'read_text',return_value='{"mode":"real"}'), patch('judgment.runner.preflight',side_effect=ConfigError('g1_required')) as gate:
            with self.assertRaisesRegex(ConfigError,'g1_required'): training_worker(Path('missing-config.json'))
            self.assertEqual(gate.call_count,1)

    def test_release_rejects_traversal_to_real_data(self):
        self.assertFalse(audit_public_files((Path('../private.json'),)).values['safe'])

    def test_fixture_evaluate_calls_actual_metrics(self):
        from judgment.runner import run_fixture_evaluation, load_fixture_bundle
        r = run_fixture_evaluation(load_fixture_bundle()).values
        self.assertGreater(r['n'],0)
        self.assertIn('nll',r); self.assertIn('coverage',r)
        self.assertFalse(r['trained']); self.assertEqual(r['quality_status'],'not_decided')

    def test_missing_public_file_is_not_safe(self):
        self.assertFalse(audit_public_files((Path('missing-reviewed-source.txt'),)).values['safe'])

    def test_dirty_code_cannot_use_approved_head(self):
        c = {'mode':'real','canonical_checkout':str(Path.cwd()),'code_revision':'approved-head'}
        digest = hashlib.sha256(json.dumps(c,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        c['approval'] = {'scope_digest':digest}
        with patch('judgment.runner.validate_run_config',return_value=RunConfig(c)), patch('subprocess.check_output',side_effect=['approved-head',' M src/judgment/runner.py']):
            with self.assertRaisesRegex(ConfigError,'dirty_checkout'): preflight(RunConfig(c))

    def test_final_disk_overflow_is_failed(self):
        from judgment.runner import final_resource_check
        with self.assertRaisesRegex(ConfigError,'disk_limit'):
            final_resource_check({'disk_limit_bytes':100,'estimated_disk_bytes':30},artifact_bytes=71)
