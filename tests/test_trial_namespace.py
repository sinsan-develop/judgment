import importlib.util
from pathlib import Path
import tempfile
import unittest
from tests.test_telemetry import TEST_TMP

spec=importlib.util.spec_from_file_location('ab_trial',Path(__file__).resolve().parents[1]/'docs/run_ab_comparison.py')
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


class TrialNamespaceTests(unittest.TestCase):
    def test_fresh_trial_preserves_original_evidence_and_refuses_reuse(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            root=Path(temporary);base=root/'.work/ab_comparison';base.mkdir(parents=True)
            for name in trial.PREPARED_FILES: (base/name).write_text('immutable synthetic')
            (base/'A.training.private.json').write_text('old interrupted evidence')
            folder=trial.new_trial(root,'approved-retry-01')
            self.assertEqual((base/'A.training.private.json').read_text(),'old interrupted evidence')
            self.assertFalse((folder/'A.training.private.json').exists())
            self.assertEqual((folder/'A.manifest.private.json').read_text(),'immutable synthetic')
            with self.assertRaises(FileExistsError): trial.new_trial(root,'approved-retry-01')
            with self.assertRaises(ValueError): trial.new_trial(root,'../escape')
