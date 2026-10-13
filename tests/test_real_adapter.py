import os
import unittest


class RealAdapterTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('JUDGMENT_REAL_CONFIG'), '실제 로컬 모델/tokenizer 검사 설정 경로 없음')
    def test_real_local_only_adapter(self):
        import json
        from pathlib import Path
        from judgment.contracts import validate_run_config, validate_request, InputError
        from judgment.laya_adapter import LayaAdapter
        from tests.test_contracts import payload
        c = validate_run_config(json.loads(Path(os.environ['JUDGMENT_REAL_CONFIG']).read_text(encoding='utf-8')),real=True).values
        a = LayaAdapter.from_local(Path(c['model_dir']),source_commit=c['source_commit'],model_revision=c['model_revision'],device=c['device'])
        s = a.score(validate_request(payload(2)))
        self.assertEqual(len(s.logits),3)
        for mode in ('long_option','prefix','context','special'):
            p = payload(2)
            if mode == 'long_option': p['candidates'][0]['description'] = '긴 한국어 설명 '*1000
            elif mode == 'prefix':
                for i, candidate in enumerate(p['candidates']): candidate['id']='공통접두부'*100+str(i)
            elif mode == 'context': p['context']=[dict(role='user',content='과거 맥락 '*1000)]
            else: p['utterance']=a.backend.tok.mask_token
            with self.assertRaises(InputError): a.audit(validate_request(p))
