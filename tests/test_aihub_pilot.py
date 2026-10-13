"""실제 mapping 경계는 합성 행으로 검증한다."""
import unittest
from unittest.mock import patch
from judgment.contracts import Candidate,ConfigError
from judgment.aihub116 import build_inherited_pilot


class AiHubPilotTests(unittest.TestCase):
    def fixture(self):
        rows=[{'file':0,'excel_row':i+2,'label':'의도'+str(i),'utterance':'합성 발화'+str(i),'context':()} for i in range(4)]
        names=('train','calibration','selection','test')
        mapping=[{'file_index':0,'excel_row':i+2,'group':i,'split':names[i],'representative':True} for i in range(4)]
        groups=[{'group':i,'split':names[i],'full_split':names[i],'positive_examples':1} for i in range(4)]
        taxonomy={(0,'의도'+str(i)):Candidate('intent-'+str(i),'합성 도메인 / 의도'+str(i)) for i in range(6)}
        return rows,mapping,groups,taxonomy

    def test_mapping_is_inherited_and_variants_keep_origin_split(self):
        args=self.fixture()
        with patch('judgment.data.split_groups',side_effect=AssertionError('분할 금지')):
            b=build_inherited_pilot(*args,derived_counts={k:1 for k in ('train','calibration','selection','test')})
        for split,part in b.parts.items():
            self.assertEqual(len(part),2)
            positive,negative=sorted(part,key=lambda e:e.gold_id is None)
            self.assertIsNotNone(positive.gold_id);self.assertIsNone(negative.gold_id)
            self.assertEqual(positive.source_id,negative.source_id)
            self.assertEqual(positive.conversation_id,negative.conversation_id)
            self.assertEqual(positive.request.utterance,negative.request.utterance)
            self.assertNotIn(positive.gold_id,{c.id for c in negative.request.candidates})
            self.assertEqual(len(negative.request.candidates),5)

    def test_split_move_and_insufficient_candidate_pool_are_rejected(self):
        rows,mapping,groups,taxonomy=self.fixture()
        groups[0]['split']='test'
        with self.assertRaisesRegex(ConfigError,'inherited_split'):
            build_inherited_pilot(rows,mapping,groups,taxonomy,derived_counts={})
        groups[0]['split']='train'
        with self.assertRaisesRegex(ConfigError,'candidate_pool'):
            build_inherited_pilot(rows,mapping,groups,dict(list(taxonomy.items())[:5]),derived_counts={})
