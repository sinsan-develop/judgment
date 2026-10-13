import math
import unittest
from dataclasses import replace
from judgment.contracts import Scores, TokenAudit, Policy, ModelError, ConfigError, ScoredExample, ABSTAIN_ID
from judgment.policy import decide, fit_temperatures, select_policy
from tests.test_data import examples


def scores(logits=(2., 0., -2.), ids=('0', '1', ABSTAIN_ID)):
    return Scores(ids, logits, 'fixture-only', TokenAudit(10, 20, 100, 200, len(ids)-1, len(ids), True))


def policy(p=0., margin=0.):
    return Policy('fixture-v1', {2: 1.}, {2: (p, margin)}, 'calibration-digest', 'selection-digest')


class PolicyTests(unittest.TestCase):
    def test_explicit_abstain(self): self.assertEqual(decide(scores((0., 1., 2.)), policy()).reason, 'explicit_abstain')
    def test_probability_and_margin(self):
        self.assertEqual(decide(scores(), policy(.99, 0.)).reason, 'low_probability')
        self.assertEqual(decide(scores(), policy(0., .99)).reason, 'low_margin')
    def test_tie(self): self.assertEqual(decide(scores((2., 2., 0.)), policy()).reason, 'tie')
    def test_bad_outputs(self):
        for s in (scores((math.nan, 0., 0.)), scores((math.inf, 0., 0.)), scores((1.,)), scores(ids=('0','0',ABSTAIN_ID))):
            with self.assertRaises(ModelError): decide(s, policy())
    def test_unknown_bucket_and_normalization(self):
        p = replace(policy(), temperature_by_count={}, thresholds_by_count={})
        d = decide(scores(), p)
        self.assertEqual(d.reason, 'unsupported_bucket')
        self.assertAlmostEqual(sum(d.probabilities.values()) + d.abstain_probability, 1.)
    def test_temperature_and_split_role(self):
        rows = tuple(ScoredExample(e, scores(), 'calibration') for e in examples(4))
        config = dict(temperature_min=.5, temperature_max=2., steps=4, min_samples=4)
        self.assertLessEqual(fit_temperatures(rows, config=config)[2], 1.)
        self.assertEqual(fit_temperatures(rows[:1], config=config), {})
        with self.assertRaisesRegex(ConfigError, 'split_role'): fit_temperatures((replace(rows[0], split='test'),), config=config)
    def test_policy_selection_criteria_required_and_not_relaxed(self):
        rows = tuple(ScoredExample(e, scores(), 'selection') for e in examples(4))
        criteria = dict(version='fixture', calibration_digest='c', max_error=0., min_coverage=1.,
                        min_samples=4, probability_grid=[0.], margin_grid=[0.])
        p = select_policy(rows, {2: 1.}, criteria=criteria)
        self.assertEqual(p.thresholds_by_count[2], (0., 0.))
        with self.assertRaises(ConfigError): select_policy(rows, {2: 1.}, criteria={})
        with self.assertRaisesRegex(ConfigError, 'split_role'): select_policy((replace(rows[0], split='test'),), {2: 1.}, criteria=criteria)
        wrong = tuple(replace(r, example=replace(r.example, gold_id='1')) for r in rows)
        with self.assertRaisesRegex(ConfigError, 'no_eligible_policy'): select_policy(wrong, {2: 1.}, criteria=criteria)
