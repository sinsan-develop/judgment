import math
import unittest
from dataclasses import replace
from judgment.contracts import ScoredExample, ConfigError, ABSTAIN_ID
from judgment.evaluation import evaluate, compare_stability
from tests.test_data import examples
from tests.test_policy import scores, policy

CONFIG = dict(labels=['0','1',ABSTAIN_ID], ece_bins=5, seed=7, bootstrap_repeats=20, confidence_level=.95,
              min_groups=4, counts=[2,5,10,20], tags=['context','negation','no_answer'])


class EvaluationTests(unittest.TestCase):
    def test_hand_calculated_metrics(self):
        e = examples(1)[0]
        s = scores(tuple(math.log(p) for p in (.6,.3,.1)))
        report = evaluate((ScoredExample(e,s,'test'),), policy(), config=CONFIG).values
        self.assertEqual(report['top1_accuracy'], 1.)
        self.assertAlmostEqual(report['nll'], -math.log(.6))
        self.assertAlmostEqual(report['brier'], .26)
        self.assertAlmostEqual(report['ece'], .4)
        self.assertAlmostEqual(report['macro_f1'], 1/3)
        self.assertEqual(report['coverage'], 1.)
        self.assertEqual(report['selective_risk'], 0.)
        self.assertEqual(report['uncertainty']['unit'], 'connected_group')

    def test_all_abstained_risk_is_undefined(self):
        row = ScoredExample(examples(1)[0], scores(), 'test')
        report = evaluate((row,), policy(.99), config=CONFIG).values
        self.assertEqual(report['coverage'], 0.)
        self.assertIsNone(report['selective_risk'])
        self.assertEqual(report['misselect_rate'], 0.)

    def test_empty_slice_and_split(self):
        r = evaluate((), policy(), config=CONFIG).values
        self.assertEqual(r['n'], 0); self.assertIsNone(r['top1_accuracy'])
        self.assertIsNone(r['by_count']['20']['coverage'])
        with self.assertRaisesRegex(ConfigError, 'split_role'):
            evaluate((ScoredExample(examples(1)[0], scores(), 'selection'),), policy(), config=CONFIG)

    def test_group_bootstrap_and_order_id_stability(self):
        a,b = examples(2); b = replace(b, source_id=a.source_id)
        rows = (ScoredExample(a,scores(),'test'), ScoredExample(b,scores(),'test'))
        r = evaluate(rows, policy(), config=CONFIG).values
        self.assertEqual(r['uncertainty']['groups'], 1)
        self.assertIn('insufficient_groups', r['warnings'])
        changed = scores((0.,2.,-2.), ('renamed-1','renamed-0',ABSTAIN_ID))
        self.assertEqual(compare_stability(((scores(),changed),), policy(), id_maps=({'renamed-1':'1','renamed-0':'0'},)).values['stable_rate'], 1.)
