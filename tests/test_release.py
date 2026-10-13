import unittest
from pathlib import Path
from judgment.contracts import ConfigError
from judgment.evaluation import audit_public_files, benchmark
from judgment.laya_adapter import LayaAdapter
from tests.fakes import FakeBackend
from tests.test_contracts import payload
from judgment.contracts import validate_request


class ReleaseTests(unittest.TestCase):
    def test_release_rejects_raw_data_and_checkpoints(self):
        for name in ('data/raw.jsonl','models/a.safetensors','.env','cache/tokens.json','output/model.pt','docs/private.pem'):
            self.assertFalse(audit_public_files((Path(name),)).values['safe'])

    def test_question_schema_artifact_is_private(self):
        for name in ('output/questions.json','output/train_report.json'):
            self.assertFalse(audit_public_files((Path(name),)).values['safe'])

    def test_fixture_report_never_claims_trained(self):
        from judgment.runner import run_training,load_fixture_bundle
        from judgment.contracts import RunConfig
        self.assertFalse(run_training(RunConfig({'mode':'fixture'}),load_fixture_bundle()).values['trained'])

    def test_missing_acceptance_is_not_decided(self):
        from judgment.runner import preflight
        from judgment.contracts import RunConfig
        self.assertFalse(preflight(RunConfig({'mode':'fixture'})).values['training_allowed'])

    def test_latency_records_device_and_sampling(self):
        a = LayaAdapter.from_backend(FakeBackend())
        c = dict(device='fixture-cpu',repeats=3,warmup=1,synchronize=lambda:None,
                 memory_sample=lambda:{'ram_bytes':100,'vram_bytes':0})
        r = benchmark(a,(validate_request(payload()),),config=c).values
        self.assertEqual(r['device'],'fixture-cpu')
        self.assertEqual(r['warm']['n'],3); self.assertEqual(r['cold']['n'],1)
        self.assertEqual(r['peak_ram_bytes'],100)
        self.assertIn('p95_seconds',r['warm'])

    def test_safe_source_list_and_synthetic_fixture(self):
        self.assertTrue(audit_public_files((Path('tests/fixtures/synthetic_ko.jsonl'),Path('src/judgment/data.py'))).values['safe'])
