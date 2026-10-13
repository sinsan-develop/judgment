"""외부 calibration과 selection 전용 정책 선택."""
import hashlib
import json
import math
from .contracts import ABSTAIN_ID, ModelError, ConfigError, Decision, Policy, positive


def probabilities(scores, temperature):
    if (not scores.audit.complete or len(scores.ids) != len(scores.logits) or not scores.ids
            or len(set(scores.ids)) != len(scores.ids) or scores.ids.count(ABSTAIN_ID) != 1
            or len(scores.ids) != scores.audit.business_count + 1
            or scores.audit.model_count != len(scores.ids)):
        raise ModelError('score_shape')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in scores.logits): raise ModelError('nonfinite_scores')
    positive(temperature, 'temperature')
    # 먼저 max를 빼므로 큰 finite logits/작은 온도에서도 overflow하지 않는다.
    m = max(scores.logits)
    exp = [math.exp((x-m)/temperature) for x in scores.logits]
    total = sum(exp)
    return dict(zip(scores.ids, (x/total for x in exp)))


def decide(scores, policy):
    count = scores.audit.business_count
    supported = count in policy.temperature_by_count and count in policy.thresholds_by_count
    probs = probabilities(scores, policy.temperature_by_count[count] if supported else 1.)
    ordered = sorted(probs, key=probs.get, reverse=True)
    reason = None
    if not supported: reason = 'unsupported_bucket'
    else:
        p, margin = policy.thresholds_by_count[count]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in (p, margin)): raise ConfigError('thresholds')
        if probs[ordered[0]] == probs[ordered[1]]: reason = 'tie'
        elif ordered[0] == ABSTAIN_ID: reason = 'explicit_abstain'
        elif probs[ordered[0]] < p: reason = 'low_probability'
        elif probs[ordered[0]] - probs[ordered[1]] < margin: reason = 'low_margin'
    return Decision('abstained' if reason else 'selected', None if reason else ordered[0],
                    {k: v for k, v in probs.items() if k != ABSTAIN_ID}, probs[ABSTAIN_ID], reason,
                    policy.version, scores.model_revision, scores.audit)


def _role(rows, role):
    if any(r.split != role for r in rows): raise ConfigError('split_role')
    for r in rows:
        ids = {c.id for c in r.example.request.candidates} | {ABSTAIN_ID}
        if set(r.scores.ids) != ids: raise ModelError('candidate_ids')
        if r.example.gold_id is not None and r.example.gold_id not in ids: raise ModelError('gold_id')


def scored_digest(rows):
    payload = [(r.example.example_id, r.scores.ids, r.scores.logits, r.example.gold_id) for r in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def fit_temperatures(calibration, *, config):
    _role(calibration, 'calibration')
    if not isinstance(config, dict): raise ConfigError('temperature_config')
    low = positive(config.get('temperature_min'), 'temperature_min')
    high = positive(config.get('temperature_max'), 'temperature_max')
    steps = positive(config.get('steps'), 'steps', integer=True)
    minimum = positive(config.get('min_samples'), 'min_samples', integer=True)
    if high < low or steps < 2: raise ConfigError('temperature_range')
    grid = [math.exp(math.log(low) + i*(math.log(high)-math.log(low))/(steps-1)) for i in range(steps)]
    result = {}
    for count in sorted({r.scores.audit.business_count for r in calibration}):
        rows = [r for r in calibration if r.scores.audit.business_count == count]
        if len(rows) < minimum: continue
        def loss(t):
            return sum(-math.log(max(probabilities(r.scores,t)[r.example.gold_id if r.example.gold_id is not None else ABSTAIN_ID], 1e-300)) for r in rows) / len(rows)
        result[count] = min(grid, key=loss)
    return result


def select_policy(selection, temperatures, *, criteria):
    _role(selection, 'selection')
    keys = ('version', 'calibration_digest', 'max_error', 'min_coverage', 'min_samples', 'probability_grid', 'margin_grid')
    if not isinstance(criteria, dict) or any(criteria.get(k) is None for k in keys): raise ConfigError('policy_criteria')
    for key in ('max_error', 'min_coverage'):
        v = criteria[key]
        if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not 0 <= v <= 1: raise ConfigError('policy_criteria')
    minimum = positive(criteria['min_samples'], 'min_samples', integer=True)
    for key in ('probability_grid', 'margin_grid'):
        if not isinstance(criteria[key], list) or not criteria[key] or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in criteria[key]): raise ConfigError('threshold_grid')
    thresholds = {}
    for count in sorted({r.scores.audit.business_count for r in selection}):
        rows = [r for r in selection if r.scores.audit.business_count == count]
        if count not in temperatures or len(rows) < minimum: continue
        eligible = []
        for p in criteria['probability_grid']:
            for m in criteria['margin_grid']:
                candidate = Policy(criteria['version'], temperatures, {count:(p,m)}, criteria['calibration_digest'], scored_digest(selection))
                decisions = [decide(r.scores, candidate) for r in rows]
                selected = [(r,d) for r,d in zip(rows,decisions) if d.status == 'selected']
                coverage = len(selected)/len(rows)
                risk = sum(d.selected_id != r.example.gold_id for r,d in selected)/len(selected) if selected else None
                if risk is not None and risk <= criteria['max_error'] and coverage >= criteria['min_coverage']:
                    eligible.append((coverage, -risk, -p, -m, (p,m)))
        if not eligible: raise ConfigError('no_eligible_policy')
        thresholds[count] = max(eligible)[-1]
    if not thresholds: raise ConfigError('no_eligible_policy')
    return Policy(criteria['version'], dict(temperatures), thresholds, criteria['calibration_digest'], scored_digest(selection))
