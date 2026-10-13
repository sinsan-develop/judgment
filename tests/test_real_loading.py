import dataclasses,json,unittest
from unittest.mock import patch
from pathlib import Path
from judgment.contracts import RunConfig,ConfigError
from judgment.data import load_real_bundle,bundle_digest
from tests.test_data import examples


class RealLoadingTests(unittest.TestCase):
    def test_training_loader_never_reads_calibration_or_test(self):
        es=examples(2);parts={'train':(es[0],),'selection':(es[1],)}
        c=RunConfig({'split_paths':{k:k+'.json' for k in ('train','calibration','selection','test')},
                     'data_manifest':{'file_digests':{k:bundle_digest(v) for k,v in parts.items()}}})
        def read(path,*args,**kwargs):
            key=path.stem
            if key not in parts:raise AssertionError('독립 split 열기 금지')
            return json.dumps([dataclasses.asdict(e) for e in parts[key]])
        with patch.object(Path,'read_text',read):b=load_real_bundle(c,roles=('train','selection'))
        self.assertEqual(b.parts['train'],parts['train'])
        self.assertEqual(b.parts['test'],())
        c.values['data_manifest']['file_digests']['train']='wrong'
        with patch.object(Path,'read_text',read),self.assertRaisesRegex(ConfigError,'data_digest_mismatch'):
            load_real_bundle(c,roles=('train','selection'))
