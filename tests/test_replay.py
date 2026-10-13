import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from judgment.contracts import ConfigError, RunConfig
from judgment.replay import build_replay, validate_replay_schedule, final_test_audit_hook, observe_replay_consumption, remaining_trial_seconds
from judgment.data import load_real_bundle


def sample_data():
    original = []
    for i in range(8):
        original.append(dict(example_id=f'e{i}', source_id=f's{i}', conversation_id=f'g{i}',
                             duplicate_group=f'd{i}', request=dict(utterance='합성 질문', question='선택',
                             context=[], candidates=[dict(id='a', description='합성 선택 A'),
                                                     dict(id='b', description='합성 선택 B')]),
                             gold_id='a' if i < 6 else None, tags=[] if i < 6 else ['no_answer']))
    selected = copy.deepcopy([original[i] for i in (0, 1, 6, 7)])
    return original, selected


class ReplayTests(unittest.TestCase):
    def test_global_deadline_remaining_budget_and_expiry(self):
        self.assertEqual(remaining_trial_seconds(100., 200.), 1700)
        with self.assertRaisesRegex(ConfigError, 'comparison_time_limit'):
            remaining_trial_seconds(100., 1900.)
    def test_upstream_effective_shuffle_is_distinct_and_observed(self):
        original, selected = sample_data()
        rows, manifest = build_replay(original, selected, arm='B', seed=13, targets=(6, 2))
        effective = manifest['effective_schedule']
        self.assertNotEqual([e['input_position'] for e in effective], list(range(8)))
        items = [{'q': {'t': 'choice'}, 'k': 3} for _ in rows]
        module = SimpleNamespace()
        module.encode_item = lambda *args, **kwargs: None
        def train(model, tok, items, config, *args, **kwargs):
            for e in effective:
                module.encode_item(tok, items[e['input_position']], 10, 10, e['option_order'], False)
            return [1.]
        module.train_model = train
        cfg = SimpleNamespace(seed=13, epochs=1, micro_batch=1)
        with observe_replay_consumption(manifest, module=module) as observed:
            module.train_model(None, None, items, cfg)
        self.assertEqual(observed['exposures_observed'], 8)
        self.assertTrue(observed['effective_order_verified'])
        self.assertEqual(module.train_model, train)

    def test_wrong_effective_item_or_choice_order_blocked_before_encode(self):
        original, selected = sample_data()
        _, manifest = build_replay(original, selected, arm='B', seed=13, targets=(6, 2))
        items = [{'q': {'t': 'choice'}, 'k': 3} for _ in range(8)]
        module = SimpleNamespace(encode_item=lambda *a, **k: self.fail('must block before encoder'))
        first = manifest['effective_schedule'][0]
        def train(model, tok, items, config):
            module.encode_item(tok, items[(first['input_position']+1) % 8], 10, 10, first['option_order'], False)
        module.train_model = train
        with self.assertRaisesRegex(ConfigError, 'replay_effective_order'):
            with observe_replay_consumption(manifest, module=module):
                module.train_model(None, None, items, SimpleNamespace(seed=13, epochs=1, micro_batch=1))
    def test_fixed_order_counts_and_original_trace_with_unique_exposure_ids(self):
        original, selected = sample_data()
        original_before = copy.deepcopy(original)
        rows, manifest = build_replay(original, selected, arm='B', seed=13, targets=(6, 2))
        self.assertEqual((rows, manifest), build_replay(original, selected, arm='B', seed=13, targets=(6, 2)))
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(r['gold_id'] is not None for r in rows), 6)
        self.assertEqual(len({r['example_id'] for r in rows}), 8)
        self.assertEqual(set(s['original_example_id'] for s in manifest['schedule']), {'e0', 'e1', 'e6', 'e7'})
        validate_replay_schedule(original, selected, rows, manifest)
        self.assertEqual(original, original_before)

    def test_changed_order_or_group_or_label_rejected(self):
        original, selected = sample_data()
        rows, manifest = build_replay(original, selected, arm='B', seed=13, targets=(6, 2))
        for mutation in ('order', 'group', 'label'):
            changed = copy.deepcopy(rows)
            if mutation == 'order': changed[0], changed[1] = changed[1], changed[0]
            elif mutation == 'group': changed[0]['conversation_id'] = 'foreign-group'
            else: changed[0]['gold_id'] = 'b'
            with self.assertRaises(ConfigError): validate_replay_schedule(original, selected, changed, manifest)

    def test_foreign_eval_id_and_input_mutation_cannot_enter_replay(self):
        original, selected = sample_data()
        for key, value in [('example_id', 'selection-id'), ('source_id', 'foreign-source'),
                           ('request', dict(selected[0]['request'], utterance='변경 입력'))]:
            changed = copy.deepcopy(selected); changed[0][key] = value
            with self.assertRaises(ConfigError): build_replay(original, changed, arm='B', seed=13, targets=(6, 2))

    def test_a_uses_original_labels_b_uses_proposal_without_changing_source(self):
        original, selected = sample_data()
        selected[0]['gold_id'] = 'b'
        a, ma = build_replay(original, selected, arm='A', seed=13, targets=(6, 2))
        b, mb = build_replay(original, selected, arm='B', seed=13, targets=(6, 2))
        self.assertEqual(ma['selected_label_changes'], 1)
        self.assertEqual(mb['selected_label_changes'], 1)
        self.assertTrue(all(r['gold_id'] == original[int(s['original_example_id'][1:])]['gold_id'] for r,s in zip(a,ma['schedule'])))
        self.assertTrue(any(r['gold_id'] == 'b' for r in b))
        self.assertEqual(original[0]['gold_id'], 'a')

    def test_ab_loader_rejects_test_before_open(self):
        c = RunConfig({'experiment': {'kind': 'ab_replay_v1'}})
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not open')):
            with self.assertRaisesRegex(ConfigError, 'final_test_forbidden'):
                load_real_bundle(c, roles=('test',))

    def test_final_test_guard_catches_read_and_write_but_allows_train(self):
        denied = Path('D:/synthetic/test.examples.json')
        observations = {'blocked_attempts': 0}
        guard = final_test_audit_hook((denied,), observations)
        for mode in ('r', 'w'):
            with self.assertRaisesRegex(ConfigError, 'final_test_forbidden'):
                guard('open', (str(denied), mode, 0))
        guard('open', ('D:/synthetic/train.examples.json', 'r', 0))
        self.assertEqual(observations['blocked_attempts'], 2)
