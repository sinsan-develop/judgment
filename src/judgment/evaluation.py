"""독립 평가. 기권 100%와 빈 slice를 합격으로 포장하지 않는다."""
import math
import random
from dataclasses import replace
from .contracts import ABSTAIN_ID, ConfigError, Report, positive
from .policy import decide, probabilities, _role
from .data import connected_groups


def _metrics(rows, policy, labels, bins):
    names = ('top1_accuracy', 'macro_f1', 'nll', 'brier', 'ece', 'coverage', 'misselect_rate', 'selective_risk',
             'abstain_rate', 'decision_accuracy', 'candidate_recall', 'within_candidate_accuracy')
    if not rows: return {'n':0, **dict.fromkeys(names), 'risk_coverage':[]}
    n = len(rows)
    gold, predicted, ps, decisions = [], [], [], []
    for row in rows:
        p = probabilities(row.scores, policy.temperature_by_count.get(row.scores.audit.business_count, 1.))
        target = row.example.gold_id if row.example.gold_id is not None else ABSTAIN_ID
        gold.append(target); predicted.append(max(p,key=p.get)); ps.append(p); decisions.append(decide(row.scores,policy))
    f1 = []
    for label in labels:
        tp = sum(a == b == label for a,b in zip(gold,predicted))
        fp = sum(a != label and b == label for a,b in zip(gold,predicted))
        fn = sum(a == label and b != label for a,b in zip(gold,predicted))
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
    ece = 0.
    for i in range(bins):
        members = [j for j,p in enumerate(ps) if min(int(max(p.values())*bins), bins-1) == i]
        if members:
            acc = sum(predicted[j] == gold[j] for j in members)/len(members)
            conf = sum(max(ps[j].values()) for j in members)/len(members)
            ece += len(members)/n * abs(acc-conf)
    selected = [j for j,d in enumerate(decisions) if d.status == 'selected']
    wrong = sum(decisions[j].selected_id != gold[j] for j in selected)
    answerable = [j for j,g in enumerate(gold) if g != ABSTAIN_ID]
    ranked = sorted(range(n), key=lambda j: max(decisions[j].probabilities.values()), reverse=True)
    curve, errors = [], 0
    for k,j in enumerate(ranked,1):
        chosen = max(decisions[j].probabilities, key=decisions[j].probabilities.get)
        errors += chosen != gold[j]
        curve.append({'coverage':k/n, 'risk':errors/k})
    return {'n':n, 'top1_accuracy':sum(a == b for a,b in zip(gold,predicted))/n,
            'macro_f1':sum(f1)/len(f1), 'nll':sum(-math.log(max(p[g],1e-300)) for p,g in zip(ps,gold))/n,
            'brier':sum(sum((p.get(label,0.) - float(label == g))**2 for label in labels) for p,g in zip(ps,gold))/n,
            'ece':ece, 'coverage':len(selected)/n, 'misselect_rate':wrong/n,
            'selective_risk':wrong/len(selected) if selected else None,
            'abstain_rate':1-len(selected)/n,
            'decision_accuracy':sum((d.selected_id if d.selected_id is not None else ABSTAIN_ID) == g for d,g in zip(decisions,gold))/n,
            'candidate_recall':len(answerable)/n,
            'within_candidate_accuracy':sum(predicted[j] == gold[j] for j in answerable)/len(answerable) if answerable else None,
            'risk_coverage':curve}


def _quantile(values, q):
    values = sorted(v for v in values if v is not None)
    if not values: return None
    pos = (len(values)-1)*q; low = int(pos); high = min(low+1, len(values)-1)
    return values[low]*(high-pos)+values[high]*(pos-low) if high != low else values[low]


def evaluate(rows, policy, *, config):
    _role(rows, 'test')
    required = ('labels','ece_bins','seed','bootstrap_repeats','confidence_level','min_groups','counts','tags')
    if not isinstance(config,dict) or any(config.get(k) is None for k in required): raise ConfigError('evaluation_config')
    labels = config['labels']
    if not isinstance(labels,list) or not labels or len(set(labels)) != len(labels) or ABSTAIN_ID not in labels: raise ConfigError('labels')
    if any(not set(r.scores.ids).issubset(labels) for r in rows): raise ConfigError('labels')
    bins = positive(config['ece_bins'],'ece_bins',integer=True)
    repeats = positive(config['bootstrap_repeats'],'bootstrap_repeats',integer=True)
    positive(config['min_groups'],'min_groups',integer=True)
    level = config['confidence_level']
    if isinstance(level,bool) or not isinstance(level,(int,float)) or not 0 < level < 1: raise ConfigError('confidence_level')
    report = _metrics(rows,policy,labels,bins)
    report['by_count'] = {str(c):_metrics(tuple(r for r in rows if r.scores.audit.business_count == c),policy,labels,bins) for c in config['counts']}
    report['by_tag'] = {tag:_metrics(tuple(r for r in rows if tag in r.example.tags),policy,labels,bins) for tag in config['tags']}
    groups = connected_groups(tuple(r.example for r in rows))
    by_id = {r.example.example_id:r for r in rows}; rng = random.Random(config['seed'])
    samples = []
    for _ in range(repeats if groups else 0):
        drawn = [rng.choice(groups) for _ in groups]
        samples.append(_metrics(tuple(by_id[e.example_id] for g in drawn for e in g),policy,labels,bins))
    alpha = (1-level)/2
    report['uncertainty'] = {'unit':'connected_group','groups':len(groups),'repeats':len(samples),'seed':config['seed'],
                             'confidence_level':level, 'intervals':{k:[_quantile([s[k] for s in samples],alpha),_quantile([s[k] for s in samples],1-alpha)] for k in ('top1_accuracy','coverage','selective_risk')}}
    report['warnings'] = ['insufficient_groups'] if len(groups) < config['min_groups'] else []
    report['ablations'] = {}
    for name, thresholds in (('explicit_only',{c:(0.,0.) for c in policy.thresholds_by_count}), ('combined',policy.thresholds_by_count)):
        report['ablations'][name] = _metrics(rows,replace(policy,thresholds_by_count=thresholds),labels,bins)
    # 임계값만 적용하는 대조군은 기권 logit을 제거한 뒤 업무 후보에 재정규화하지 않는다.
    threshold_decisions = []
    for row in rows:
        d = decide(row.scores,policy); count = row.scores.audit.business_count
        business = sorted(d.probabilities,key=d.probabilities.get,reverse=True)
        p,m = policy.thresholds_by_count.get(count,(1.,1.))
        best = business[0]; runner = max([d.probabilities[k] for k in business[1:]],default=0.)
        selected = count in policy.thresholds_by_count and d.probabilities[best] > runner and d.probabilities[best] >= p and d.probabilities[best]-runner >= m
        threshold_decisions.append((selected, best == row.example.gold_id))
    nsel = sum(s for s,_ in threshold_decisions)
    report['ablations']['threshold_only'] = {'n':len(rows),'coverage':nsel/len(rows) if rows else None,
                                            'selective_risk':sum(s and not correct for s,correct in threshold_decisions)/nsel if nsel else None}
    report['quality_status'] = 'not_decided'
    report['token_rejection_rate'] = None  # rejected request counts require a separate ingress ledger.
    return Report(report)


def compare_stability(pairs, policy, *, id_maps):
    if len(pairs) != len(id_maps): raise ConfigError('id_mapping_count')
    stable = 0
    for (a,b), mapping in zip(pairs,id_maps):
        da,db = decide(a,policy),decide(b,policy)
        if db.selected_id is not None and db.selected_id not in mapping: raise ConfigError('id_mapping')
        stable += da.selected_id == (mapping[db.selected_id] if db.selected_id is not None else None)
    return Report({'n':len(pairs),'stable_rate':stable/len(pairs) if pairs else None})


def benchmark(adapter, requests, *, config):
    import time
    if not isinstance(config,dict) or any(config.get(k) is None for k in ('device','repeats','warmup','synchronize','memory_sample')):
        raise ConfigError('benchmark_config')
    repeats = positive(config['repeats'],'repeats',integer=True)
    warmup = positive(config['warmup'],'warmup',integer=True)
    if not callable(config['synchronize']) or not callable(config['memory_sample']): raise ConfigError('benchmark_hooks')
    if not requests: raise ConfigError('empty_benchmark')
    peak_ram = peak_vram = 0
    def measure(request):
        nonlocal peak_ram,peak_vram
        config['synchronize'](); start = time.perf_counter()
        adapter.score(request); config['synchronize']()
        elapsed = time.perf_counter()-start
        memory = config['memory_sample']()
        for key in ('ram_bytes','vram_bytes'):
            if key not in memory or not isinstance(memory[key],int) or memory[key] < 0: raise ConfigError('memory_sample')
        peak_ram,peak_vram = max(peak_ram,memory['ram_bytes']),max(peak_vram,memory['vram_bytes'])
        return elapsed
    cold = [measure(requests[0])]
    for i in range(warmup): measure(requests[i%len(requests)])
    warm = [measure(requests[i%len(requests)]) for i in range(repeats)]
    def summary(values): return {'n':len(values),'p50_seconds':_quantile(values,.5),'p95_seconds':_quantile(values,.95)}
    return Report({'device':config['device'],'cold':summary(cold),'warm':summary(warm),'warmup':warmup,
                   'peak_ram_bytes':peak_ram,'peak_vram_bytes':peak_vram,'cold_scope':'first_inference_after_adapter_load',
                   'memory_scope':'sampled_after_each_call','model_revision':adapter.backend.model_revision})


def audit_public_files(paths):
    from pathlib import Path
    import re
    import os
    findings = []
    forbidden_parts = {'data','models','cache','checkpoints','.work','.env','.ssh'}
    forbidden_names = {'questions.json','train_report.json','development_environment.md','judgment-design-draft.md','judgment-implementation-plan.md','agents.md'}
    for path in paths:
        p = Path(os.path.abspath(path))
        # lexical 경계부터 검사한다. 일부 sandbox의 realpath는 '..'를 잘못 해석할 수 있다.
        try: p = p.relative_to(Path(os.path.abspath(Path.cwd())))
        except ValueError: findings.append({'code':'outside_repository'}); continue
        if any(parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()) for parent in [p]+list(p.parents)[:-1]):
            findings.append({'path':p.as_posix(),'code':'unreviewed_link'}); continue
        parts = {x.lower() for x in p.parts}
        private = bool(parts & forbidden_parts) or p.name.lower() in forbidden_names or p.name.startswith('.env')
        private |= p.suffix.lower() in ('.safetensors','.pt','.pth','.pem','.key','.ckpt','.bin')
        private |= p.suffix.lower() == '.jsonl' and p.as_posix() != 'tests/fixtures/synthetic_ko.jsonl'
        if private:
            findings.append({'path':p.as_posix(),'code':'private_artifact'}); continue
        if not p.is_file():
            findings.append({'path':p.as_posix(),'code':'missing_or_nonfile'}); continue
        if p.is_file():
            if p.stat().st_size > 2_000_000: findings.append({'path':p.as_posix(),'code':'large_unreviewed_file'}); continue
            try: content = p.read_text(encoding='utf-8-sig')
            except (UnicodeError,OSError): findings.append({'path':p.as_posix(),'code':'unreviewed_binary'}); continue
            if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[A-Z0-9]{16}',content):
                findings.append({'path':p.as_posix(),'code':'secret_pattern'})
    return Report({'safe':not findings,'findings':findings,'scope':'path_and_secret_patterns',
                   'raw_text_review':'manual_staged_diff_required','files':len(paths)})
