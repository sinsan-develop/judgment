import json
import unittest
from dataclasses import replace
from judgment.contracts import Example, ConfigError, InputError, validate_request, ABSTAIN_ID
from judgment.data import normalize_row, split_groups, to_laya_row
from tests.test_contracts import payload

RATIOS = dict(train=.25, calibration=.25, selection=.25, test=.25)


def examples(n=8):
    return tuple(Example(str(i), 's'+str(i), 'c'+str(i), 'd'+str(i), validate_request(payload()), '0', ()) for i in range(n))


class DataTests(unittest.TestCase):
    def test_transitive_groups_never_cross_splits(self):
        es = list(examples()); es[1] = replace(es[1], source_id=es[0].source_id)
        es[2] = replace(es[2], conversation_id=es[1].conversation_id)
        b = split_groups(tuple(es), ratios=RATIOS, seed=4)
        membership = {e.example_id: k for k, part in b.parts.items() for e in part}
        self.assertEqual(membership['0'], membership['2'])
        self.assertEqual(sum(map(len, b.parts.values())), 8)

    def test_future_turn_never_in_state(self):
        row = dict(example_id='e', source_id='s', conversation_id='c', duplicate_group='d',
                   request=payload(), gold_id='0', tags=[], current_index=1,
                   turns=[dict(role='user', content='과거'), dict(role='user', content='예약을 취소해 주세요'), dict(role='assistant', content='미래 정답')])
        mapping = {k: k for k in row}
        e = normalize_row(row, mapping)
        state = to_laya_row(e)['state']
        self.assertIn('과거', state); self.assertNotIn('미래 정답', state)

    def test_gold_permutation_preserved(self):
        e = examples()[0]
        e = replace(e, request=replace(e.request, candidates=tuple(reversed(e.request.candidates))))
        row = to_laya_row(e)
        self.assertEqual(row['gold']['decision']['probabilities'], {'0': 1.0})

    def test_missing_gold_maps_to_abstain(self):
        row = to_laya_row(replace(examples()[0], gold_id=None))
        self.assertEqual(row['gold']['decision']['probabilities'], {ABSTAIN_ID: 1.0})

    def test_manifest_has_no_raw_text(self):
        b = split_groups(examples(), ratios=RATIOS, seed=4)
        out = json.dumps(b.manifest, ensure_ascii=False)
        self.assertNotIn('예약', out); self.assertNotIn('example_id', out)
        self.assertEqual(b.manifest['counts'], dict(train=2, calibration=2, selection=2, test=2))

    def test_split_reproducible(self):
        self.assertEqual(split_groups(examples(), ratios=RATIOS, seed=4), split_groups(examples(), ratios=RATIOS, seed=4))

    def test_insufficient_groups_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'insufficient_groups'): split_groups(examples(3), ratios=RATIOS, seed=1)

    def test_invalid_gold_and_mapping_rejected(self):
        with self.assertRaisesRegex(InputError, 'invalid_gold'): to_laya_row(replace(examples()[0], gold_id='missing'))
        with self.assertRaisesRegex(ConfigError, 'mapping'): normalize_row({}, {})

    def test_fixture_context_pair(self):
        from pathlib import Path
        rows = [json.loads(x) for x in Path('tests/fixtures/synthetic_ko.jsonl').read_text(encoding='utf-8').splitlines()]
        a, b = [r for r in rows if 'context_pair' in r['tags']]
        self.assertEqual(a['request']['utterance'], b['request']['utterance'])
        self.assertNotEqual(a['gold_id'], b['gold_id'])
        self.assertNotEqual(a['request']['context'], b['request']['context'])
