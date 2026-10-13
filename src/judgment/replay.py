"""승인된 A/B 비교의 고정 반복 입력·출처 추적·final-test 접근 차단."""
from collections import Counter
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from .contracts import ConfigError


def require(condition, code):
    if not condition:
        raise ConfigError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def build_replay(original, selected, *, arm, seed, targets=(558, 139)):
    require(arm in ('A', 'B') and isinstance(seed, int) and not isinstance(seed, bool), 'replay_settings')
    require(len(targets) == 2 and all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in targets), 'replay_targets')
    originals = {e['example_id']: e for e in original}
    require(len(originals) == len(original) and original, 'replay_original_ids')
    selected_ids = {e['example_id'] for e in selected}
    require(len(selected_ids) == len(selected) and selected, 'replay_selected_ids')
    for e in selected:
        require(e['example_id'] in originals, 'replay_foreign_id')
        source = originals[e['example_id']]
        require(set(e) == set(source), 'replay_schema')
        require(all(e[k] == source[k] for k in source if k not in ('gold_id', 'tags')), 'replay_source_changed')
        require([t for t in e['tags'] if t != 'no_answer'] == [t for t in source['tags'] if t != 'no_answer'], 'replay_tags_changed')
        require(e['gold_id'] is None or e['gold_id'] in {c['id'] for c in e['request']['candidates']}, 'replay_gold')
        require(('no_answer' in e['tags']) == (e['gold_id'] is None), 'replay_gold_tags')
    require(tuple(sum(e['gold_id'] is not None if answerable else e['gold_id'] is None for e in original)
                  for answerable in (True, False)) == tuple(targets), 'replay_original_counts')
    pool = original if arm == 'A' else selected
    planned = []
    for bucket, (answerable, target) in enumerate(zip((True, False), targets)):
        members = sorted((e for e in pool if (e['gold_id'] is not None) == answerable), key=lambda e: e['example_id'])
        require(members and target >= len(members), 'replay_target_too_small')
        random.Random(seed + bucket + 1).shuffle(members)
        planned.extend(members[i % len(members)] for i in range(target))
    random.Random(seed).shuffle(planned)
    occurrences, rows, schedule = Counter(), [], []
    for position, e in enumerate(planned):
        occurrences[e['example_id']] += 1
        row = deepcopy(e)
        row['example_id'] = f'replay-{arm}-{position:04d}'
        rows.append(row)
        schedule.append({'position': position, 'exposure_id': row['example_id'],
                         'original_example_id': e['example_id'], 'source_id': e['source_id'],
                         'conversation_id': e['conversation_id'], 'duplicate_group': e['duplicate_group'],
                         'occurrence': occurrences[e['example_id']], 'gold_id': e['gold_id']})
    effective_order = list(range(len(rows)))
    random.Random(seed).shuffle(effective_order)  # 고정 upstream의 epoch=0 shuffle.
    option_rng = random.Random(seed)
    actual_occurrences, effective_schedule = Counter(), []
    for training_position, input_position in enumerate(effective_order):
        source = schedule[input_position]
        actual_occurrences[source['original_example_id']] += 1
        option_order = list(range(len(rows[input_position]['request']['candidates']) + 1))
        option_rng.shuffle(option_order)
        effective_schedule.append(dict(source, input_position=input_position,
            training_position=training_position, optimizer_window=training_position // 8 + 1,
            occurrence=actual_occurrences[source['original_example_id']], option_order=option_order))
    manifest = {'kind': 'ab_replay_v1', 'arm': arm, 'seed': seed, 'targets': list(targets),
                'total_exposures': len(rows), 'unique_examples': len(occurrences),
                'original_digest': digest(original), 'selected_digest': digest(selected),
                'selected_label_changes': sum(e['gold_id'] != originals[e['example_id']]['gold_id'] for e in selected),
                'schedule': schedule, 'effective_schedule': effective_schedule,
                'order_contract': 'schedule=input_jsonl; effective_schedule=upstream_epoch0_optimizer_input',
                'occurrences': dict(sorted(occurrences.items())),
                'rows_digest': digest(rows)}
    return rows, manifest


def validate_replay_schedule(original, selected, rows, manifest):
    expected_rows, expected_manifest = build_replay(original, selected, arm=manifest['arm'],
                                                   seed=manifest['seed'], targets=tuple(manifest['targets']))
    require(rows == expected_rows and manifest == expected_manifest, 'replay_schedule_changed')
    return manifest


def remaining_trial_seconds(start, now):
    seconds = int(1800 - (now - start))
    require(seconds > 0, 'comparison_time_limit')
    return seconds


@contextmanager
def observe_replay_consumption(manifest, *, module=None):
    if module is None:
        import laya.train as module
    original_train, original_encode = module.train_model, module.encode_item
    observations = {'exposures_observed': 0, 'effective_order_verified': False, 'observed_input_positions': []}
    def train(model, tok, items, config, *args, **kwargs):
        require(config.seed == manifest['seed'] and config.epochs == 1 and config.micro_batch == 1,
                'replay_effective_settings')
        require(len(items) == manifest['total_exposures'], 'replay_effective_items')
        positions = {id(item): i for i, item in enumerate(items)}
        require(len(positions) == len(items), 'replay_effective_items')
        def encode(tok, item, *args, **kwargs):
            if id(item) in positions:
                seen = observations['exposures_observed']
                require(seen < len(manifest['effective_schedule']), 'replay_effective_order')
                expected = manifest['effective_schedule'][seen]
                option_order = args[2] if len(args) > 2 else kwargs.get('option_order')
                require(positions[id(item)] == expected['input_position'] and option_order == expected['option_order'],
                        'replay_effective_order')
                observations['observed_input_positions'].append(positions[id(item)])
                observations['exposures_observed'] += 1
            return original_encode(tok, item, *args, **kwargs)
        module.encode_item = encode
        try:
            result = original_train(model, tok, items, config, *args, **kwargs)
        finally:
            module.encode_item = original_encode
        require(observations['exposures_observed'] == manifest['total_exposures'], 'replay_effective_count')
        observations['effective_order_verified'] = True
        return result
    module.train_model = train
    try:
        yield observations
    finally:
        module.train_model = original_train
        module.encode_item = original_encode


def final_test_audit_hook(paths, observations):
    blocked = {os.path.normcase(os.path.abspath(p)) for p in paths}
    def hook(event, args):
        if event != 'open' or not args or isinstance(args[0], int):
            return
        path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        if path in blocked:
            observations['blocked_attempts'] += 1
            raise ConfigError('final_test_forbidden')
    return hook


def install_final_test_guard(config):
    c = config.values
    if c.get('experiment', {}).get('kind') != 'ab_replay_v1':
        return None
    root = Path(c['canonical_checkout'])
    paths = [root / '.work/data/test.examples.json', root / '.work/data/test.jsonl',
             Path(c['split_paths']['test'])]
    # 과거 점수 파일도 test 배열을 포함하므로 이번 비교에서 열지 않는다.
    old_job = root / '.work/runs/g1-trial-17c30baf57c0428fa5dcb6c953ec075a'
    paths.extend(old_job / name for name in ('base.scores.private.json', 'trained.scores.private.json'))
    observations = {'blocked_attempts': 0, 'policy': 'final_test_and_old_mixed_scores_forbidden'}
    sys.addaudithook(final_test_audit_hook(paths, observations))
    return observations


def validate_replay_files(config, *, training_jsonl=None):
    c = config.values
    spec = c.get('experiment', {})
    if spec.get('kind') != 'ab_replay_v1':
        return None
    require(c['seed'] == 13 and c['training'] == dict(epochs=1, micro_batch=1, grad_accum=8,
            encoder_lr=1e-5, head_lr=1e-4, freeze_encoder=True, precision='fp32'), 'replay_training_settings')
    paths = spec['files']
    loaded = {}
    for role in ('original', 'selected', 'manifest', 'exposures'):
        path = Path(paths[role]['path'])
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == paths[role]['sha256'], 'replay_file_changed')
        loaded[role] = json.loads(raw.decode('utf-8'))
    require(len(loaded['original']) == 697 and len(loaded['selected']) == 280, 'replay_approved_counts')
    require(sum(e['gold_id'] is not None for e in loaded['selected']) == 216, 'replay_selected_labels')
    manifest = validate_replay_schedule(loaded['original'], loaded['selected'], loaded['exposures'], loaded['manifest'])
    require(manifest['selected_label_changes'] == 49 and manifest['total_exposures'] == 697 and
            manifest['targets'] == [558, 139] and manifest['arm'] == spec['arm'] and manifest['seed'] == c['seed'], 'replay_approved_scope')
    require(Path(c['split_paths']['train']).resolve() == Path(paths['exposures']['path']).resolve(), 'replay_train_path')
    if training_jsonl is not None:
        from .data import normalize_row, to_laya_row
        mapping = {k: k for k in loaded['exposures'][0]}
        expected = [to_laya_row(normalize_row(e, mapping)) for e in loaded['exposures']]
        actual = [json.loads(line) for line in Path(training_jsonl).read_text(encoding='utf-8').splitlines()]
        require(actual == expected, 'replay_worker_input_changed')
    return {'arm': spec['arm'], 'exposures': 697, 'unique_examples': manifest['unique_examples'],
            'source_ids_and_groups_verified': True, 'expected_optimizer_updates': 88,
            'manifest_sha256': paths['manifest']['sha256']}
