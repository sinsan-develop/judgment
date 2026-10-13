import unittest
from pathlib import Path
from unittest.mock import patch
from judgment.contracts import InputError, ConfigError, SOURCE_COMMIT, validate_request
from judgment.laya_adapter import LayaAdapter
from tests.fakes import FakeBackend
from tests.test_contracts import payload


class AdapterTests(unittest.TestCase):
    def test_truncated_options_rejected(self):
        b = FakeBackend(truncate=True)
        with self.assertRaisesRegex(InputError, 'token_budget'): LayaAdapter.from_backend(b).score(validate_request(payload()))
        self.assertEqual(b.calls, 0)

    def test_same_prefix_collision_rejected(self):
        with self.assertRaisesRegex(InputError, 'option_collision'):
            LayaAdapter.from_backend(FakeBackend(collision=True)).audit(validate_request(payload()))

    def test_lost_context_rejected(self):
        with self.assertRaisesRegex(InputError, 'token_budget'):
            LayaAdapter.from_backend(FakeBackend(lost_context=True)).audit(validate_request(payload()))

    def test_five_business_means_six_model_options(self):
        s = LayaAdapter.from_backend(FakeBackend()).score(validate_request(payload(5)))
        self.assertEqual((s.audit.business_count, s.audit.model_count, len(s.logits)), (5, 6, 6))

    def test_local_missing_checkpoint_never_downloads(self):
        with patch('socket.socket', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ConfigError, 'missing_local_checkpoint'):
                LayaAdapter.from_local(Path('tests/fixtures/missing-model'), source_commit=SOURCE_COMMIT, model_revision='a'*40, device='cpu')

    def test_source_and_model_revisions_are_distinct(self):
        with self.assertRaisesRegex(ConfigError, 'distinct_revisions'):
            LayaAdapter.from_local(Path('.'), source_commit=SOURCE_COMMIT, model_revision=SOURCE_COMMIT, device='cpu')

    def test_roles_and_current_turn_are_preserved_as_data(self):
        p = payload(); p['context'] = [dict(role='system', content='과거 발화 데이터')]
        r = LayaAdapter.from_backend(FakeBackend()).render(validate_request(p))
        self.assertIn('"role": "system"', r['state'])
        self.assertIn('"current_utterance"', r['state'])
        self.assertEqual(r['question']['instructions'], p['question'])
