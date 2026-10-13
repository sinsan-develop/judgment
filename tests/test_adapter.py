import unittest
import types
import sys
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

    def test_pinned_question_encoder_returns_list_not_mapping(self):
        from judgment.laya_adapter import _LocalBackend
        b = object.__new__(_LocalBackend)
        b.source_commit=SOURCE_COMMIT; b.model_revision='fixture'; b.head_limit=10000; b.total_limit=20000
        b.tok = types.SimpleNamespace(all_special_tokens=[])
        encode = lambda text: list(map(ord,text))
        options = lambda q: [k+': '+v for k,v in q['crit'].items()]
        def build_head(tok,q,limit):
            ids = [1]+encode('choice question: '+q['ins'])+[2]; markers=[]
            for option in options(q): markers.append(len(ids)); ids += [3]+encode(' '+option)
            return ids+[2],markers,{}
        def build_sequence(tok,state,q,*limits,**kwargs):
            head,markers,stats=build_head(tok,q,0)
            return head+encode(state)+[2],markers,stats,{'truncated':False}
        b.common=types.SimpleNamespace(_encode_question_text=lambda tok,s,**kw:encode(s),
            encode_text=lambda tok,s,**kw:{'input_ids':encode(s)},render_options=options,
            serialize_state=lambda s:s,build_head=build_head,build_sequence=build_sequence)
        b.Agent=types.SimpleNamespace(_to_internal=lambda q:{'t':'choice','ins':q['instructions'],'crit':q['criteria']})
        self.assertTrue(LayaAdapter.from_backend(b).audit(validate_request(payload())).complete)

    def test_finetune_emits_pinned_config_to_actual_boundary(self):
        from judgment.laya_adapter import _LocalBackend
        from judgment.contracts import RunConfig
        from unittest.mock import Mock
        b=object.__new__(_LocalBackend); b.source_commit=SOURCE_COMMIT; b.model_dir=Path('local-model')
        adapter=LayaAdapter.from_backend(b)
        c=RunConfig({'training':dict(epochs=1,micro_batch=1,grad_accum=1,encoder_lr=1e-5,head_lr=1e-4,freeze_encoder=True,precision='fp32'), 'seed':7,'device':'cpu'})
        train=types.ModuleType('laya.train'); train.TrainConfig=lambda **kw:kw; train.finetune=Mock(return_value={'fixture':True})
        with patch.dict(sys.modules,{'laya':types.ModuleType('laya'),'laya.train':train}), patch('judgment.contracts.validate_run_config',return_value=c):
            adapter.finetune(Path('train.jsonl'),Path('selection.jsonl'),Path('output'),config=c)
        args=train.finetune.call_args
        self.assertEqual(args.args[:2],('train.jsonl','local-model'))
        self.assertEqual(args.kwargs['config']['eval_data'],'selection.jsonl')
        self.assertEqual(args.kwargs['config']['calib_frac'],0)
        self.assertEqual(args.kwargs['config']['calib_max'],0)
        self.assertEqual(args.kwargs['config']['shuffle_options'],('choice',))
