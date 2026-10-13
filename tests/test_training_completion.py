"""갱신·동결·reload 관측이 함께 있어야 실제 완료로 표시한다."""
import unittest
from judgment.runner import completed_training_evidence,observe_optimizer_steps,training_jsonl_digest
from judgment.data import bundle_digest,to_laya_row
from tests.test_data import examples
from unittest.mock import patch
from pathlib import Path
import json


class TrainingCompletionTests(unittest.TestCase):
    def test_partial_evidence_and_encoder_change_cannot_be_trained(self):
        changed={'trained':True,'changed_tensors':2}
        for updates,reload,encoder in [(0,True,0),(1,False,0),(1,True,1)]:
            self.assertFalse(completed_training_evidence(changed,optimizer_updates=updates,reload_verified=reload,encoder_changed=encoder)['trained'])
        self.assertTrue(completed_training_evidence(changed,optimizer_updates=1,reload_verified=True,encoder_changed=0)['trained'])

    def test_actual_optimizer_steps_are_counted_independently_of_backward(self):
        import torch
        p=torch.nn.Parameter(torch.ones(2));optimizer=torch.optim.AdamW([p],lr=1e-4)
        with observe_optimizer_steps() as evidence:
            p.sum().backward();self.assertEqual(evidence['count'],0)
            optimizer.step();optimizer.step()
        self.assertEqual(evidence['count'],2)

    def test_worker_file_digest_matches_bundle_and_detects_modified_gold(self):
        es=examples(2);lines='\n'.join(json.dumps(to_laya_row(e),ensure_ascii=False) for e in es)+'\n'
        with patch.object(Path,'read_text',return_value=lines):
            self.assertEqual(training_jsonl_digest(Path('unused')),bundle_digest(es))
        changed=json.loads(lines.splitlines()[0]);changed['gold']={}
        with patch.object(Path,'read_text',return_value=json.dumps(changed)+'\n'+lines.splitlines()[1]):
            self.assertNotEqual(training_jsonl_digest(Path('unused')),bundle_digest(es))
