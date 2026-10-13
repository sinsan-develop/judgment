"""명시 mapping과 연결 성분 단위 split. 원문 manifest 공개 금지."""
import hashlib
import json
import math
import random
from dataclasses import asdict
from .contracts import Example, SplitBundle, ABSTAIN_ID, ConfigError, InputError, validate_request, text
from .laya_adapter import ABSTAIN_DESCRIPTION

SPLITS = ('train', 'calibration', 'selection', 'test')


def normalize_row(raw, mapping):
    required = ('example_id', 'source_id', 'conversation_id', 'duplicate_group', 'request', 'gold_id', 'tags')
    if not isinstance(raw, dict) or not isinstance(mapping, dict) or any(k not in mapping for k in required):
        raise ConfigError('mapping')
    try: values = {k: raw[mapping[k]] for k in required}
    except (KeyError, TypeError): raise ConfigError('mapping') from None
    for k in required[:4]: text(values[k], 'missing_group_key')
    request = values['request']
    if 'turns' in mapping or 'current_index' in mapping:
        if not all(k in mapping for k in ('turns', 'current_index')): raise ConfigError('mapping')
        turns, index = raw[mapping['turns']], raw[mapping['current_index']]
        if not isinstance(turns, list) or isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(turns):
            raise InputError('invalid_turn_index')
        if turns[index].get('content') != request.get('utterance'): raise InputError('current_turn_mismatch')
        request = dict(request, context=turns[:index])
    req = validate_request(request)
    gold = values['gold_id']
    if gold is not None and gold not in {c.id for c in req.candidates}: raise InputError('invalid_gold')
    tags = values['tags']
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags): raise InputError('invalid_tags')
    return Example(*(values[k] for k in required[:4]), req, gold, tuple(tags))


def connected_groups(examples):
    parent = list(range(len(examples)))
    def root(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    seen = {}
    ids = set()
    for i, e in enumerate(examples):
        if e.example_id in ids: raise InputError('duplicate_example_id')
        ids.add(e.example_id)
        for field in ('source_id', 'conversation_id', 'duplicate_group'):
            value = getattr(e, field)
            text(value, 'missing_group_key')
            key = (field, value)
            if key in seen: parent[root(i)] = root(seen[key])
            else: seen[key] = i
    groups = {}
    for i, e in enumerate(examples): groups.setdefault(root(i), []).append(e)
    return tuple(tuple(g) for g in groups.values())


def split_groups(examples, *, ratios, seed):
    if not isinstance(ratios, dict) or set(ratios) != set(SPLITS) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in ratios.values()) or not math.isclose(sum(ratios.values()), 1):
        raise ConfigError('split_ratios')
    if isinstance(seed, bool) or not isinstance(seed, int): raise ConfigError('seed')
    groups = sorted(connected_groups(examples), key=lambda g: min(e.example_id for e in g))
    if len(groups) < 4: raise ConfigError('insufficient_groups')
    random.Random(seed).shuffle(groups)
    ideal = [len(groups) * ratios[k] for k in SPLITS]
    counts = [math.floor(v) for v in ideal]
    for i in sorted(range(4), key=lambda i: ideal[i] - counts[i], reverse=True)[:len(groups)-sum(counts)]: counts[i] += 1
    if any(n == 0 for n in counts): raise ConfigError('insufficient_groups')
    parts, pos = {}, 0
    for k, count in zip(SPLITS, counts):
        parts[k] = tuple(e for g in groups[pos:pos+count] for e in g); pos += count
    manifest = {'source': 'synthetic', 'version': 'synthetic-ko-v1', 'terms_link': None,
                'transform_version': '1', 'seed': seed, 'counts': {k: len(p) for k, p in parts.items()},
                'group_counts': dict(zip(SPLITS, counts)), 'file_digests': {},
                'checks': {'split_intersection': 0, 'pii': 'synthetic_only', 'missing_labels': 0,
                           'label_distribution': {k: {'answerable': sum(e.gold_id is not None for e in p), 'abstain': sum(e.gold_id is None for e in p)} for k, p in parts.items()},
                           'terms': 'self_authored_synthetic_only'}}
    return SplitBundle(parts, manifest)


def to_laya_row(example):
    req = validate_request(asdict(example.request) | {'candidates': [asdict(c) for c in example.request.candidates], 'context': [asdict(t) for t in example.request.context]})
    criteria = {c.id: c.description for c in req.candidates}; criteria[ABSTAIN_ID] = ABSTAIN_DESCRIPTION
    if example.gold_id is not None and example.gold_id not in criteria: raise InputError('invalid_gold')
    state = json.dumps({'past_dialogue': [asdict(t) for t in req.context], 'current_utterance': req.utterance}, ensure_ascii=False)
    return {'state': state, 'questions': {'decision': {'type': 'choice', 'instructions': req.question, 'criteria': criteria}},
            'gold': {'decision': {'probabilities': {example.gold_id if example.gold_id is not None else ABSTAIN_ID: 1.0}}}}


def write_manifest(bundle, destination):
    # 공개 허용 목록만 사용한다. example/group 식별자나 원문 digest는 내보내지 않는다.
    allowed = ('source', 'version', 'terms_link', 'transform_version', 'seed', 'counts', 'group_counts', 'file_digests', 'checks')
    value = {k: bundle.manifest[k] for k in allowed if k in bundle.manifest}
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def bundle_digest(part):
    content = '\n'.join(json.dumps(to_laya_row(e), sort_keys=True, ensure_ascii=False) for e in part)
    return hashlib.sha256(content.encode()).hexdigest()


def load_real_bundle(config,*,roles):
    from pathlib import Path
    if not roles or any(role not in SPLITS for role in roles): raise ConfigError('split_role')
    c=config.values;parts={k:() for k in SPLITS}
    mapping={k:k for k in ('example_id','source_id','conversation_id','duplicate_group','request','gold_id','tags')}
    for role in roles:
        raw=json.loads(Path(c['split_paths'][role]).read_text(encoding='utf-8'))
        if not isinstance(raw,list): raise ConfigError('data_mapping')
        parts[role]=tuple(normalize_row(r,mapping) for r in raw)
        if bundle_digest(parts[role])!=c['data_manifest']['file_digests'].get(role): raise ConfigError('data_digest_mismatch')
    ownership={e.example_id:role for role,part in parts.items() for e in part}
    for group in connected_groups(tuple(e for part in parts.values() for e in part)):
        if len({ownership[e.example_id] for e in group})!=1: raise ConfigError('split_overlap')
    return SplitBundle(parts,c['data_manifest'])
