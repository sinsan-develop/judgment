"""학습 분할의 수동 의미 검토표를 대조·집계한다. 모델 호출·학습 없음.

원본 train과 수동 검토만 선별 입력으로 사용한다. 다른 분할은 보존 digest와
그룹 경계 확인에만 사용한다. 출력 원문/검토표/잠정 정답은 ignored 로컬 전용.
실행: python docs/train_semantic_selection.py --root PROJECT_ROOT
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

CATEGORIES = ('unique', 'none', 'multiple', 'uncertain')


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def preserve_write(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path.exists():
        require(path.read_text(encoding='utf-8') == text, 'existing_output_differs:' + path.name)
    else:
        path.write_text(text, encoding='utf-8')


def run(root):
    root = root.resolve()
    folder = root / '.work/train_semantic_review'
    output = folder / 'results-v1'
    before = load(folder / 'preservation.before.private.json')
    require(before == {name: sha(root / name) for name in before}, 'source_changed_before_selection')
    original = load(root / '.work/data/train.examples.json')
    require(len(original) == 697, 'original_train_count')
    index = {e['example_id']: e for e in original}
    require(len(index) == len(original), 'original_duplicate_id')
    annotations = []
    for part in (1, 2, 3):
        units = load(folder / f'input-{part}.private.json')
        allowed = {e['example_id'] for u in units for e in (u['positive'], u['negative']) if e is not None}
        records = load(folder / f'review-{part}.private.json')
        require(len(records) == len(allowed), 'part_count')
        require({r['example_id'] for r in records} == allowed, 'part_coverage')
        for unit in units:
            for role in ('positive', 'negative'):
                e = unit[role]
                if e is not None:
                    require(e == index[e['example_id']], 'review_input_mutated')
        annotations.extend(records)
    by_id = {r['example_id']: r for r in annotations}
    require(len(by_id) == len(annotations) == 697 and set(by_id) == set(index), 'all_train_coverage')
    selected, held, proposed = [], [], []
    gold_changes = Counter()
    counts = Counter()
    original_role_counts = {role: Counter() for role in ('positive', 'derived_no_answer')}
    for e in original:
        r = by_id[e['example_id']]
        valid, uncertain = set(r['valid_candidate_ids']), set(r['uncertain_candidate_ids'])
        candidates = {c['id'] for c in e['request']['candidates']}
        require(not valid & uncertain and valid | uncertain <= candidates, 'candidate_membership')
        require(len(valid) == len(r['valid_candidate_ids']) and len(uncertain) == len(r['uncertain_candidate_ids']), 'duplicate_review_id')
        expected = ('multiple' if len(valid) >= 2 else 'uncertain' if uncertain
                    else 'unique' if valid else 'none')
        require(r['category'] == expected and expected in CATEGORIES, 'category_definition')
        require(r['context_reviewed'] is True and isinstance(r['reason'], str) and len(r['reason'].strip()) >= 8, 'review_evidence')
        require(r['original_gold_id'] == e['gold_id'], 'original_gold_changed')
        counts[expected] += 1
        original_role_counts['derived_no_answer' if e['gold_id'] is None else 'positive'][expected] += 1
        record = {'source_example': e, 'review': r}
        if expected in ('unique', 'none'):
            new_gold = next(iter(valid)) if valid else None
            candidate = deepcopy(e)
            candidate['gold_id'] = new_gold
            candidate['tags'] = [t for t in e['tags'] if t != 'no_answer']
            if new_gold is None:
                candidate['tags'].append('no_answer')
            record['proposed_example'] = candidate
            record['label_changed'] = new_gold != e['gold_id']
            record['status'] = 'manual_review_v1_proposal_not_approved_for_training'
            if new_gold != e['gold_id']:
                change = ('original_no_answer_to_unique' if e['gold_id'] is None else
                          'original_positive_to_none' if new_gold is None else 'original_positive_to_other_unique')
                gold_changes[change] += 1
            selected.append(record)
            proposed.append(candidate)
        else:
            record['status'] = 'preserved_not_in_proposed_training'
            held.append(record)
    # 같은 입력의 원본/파생에서 공통 후보의 의미 판정을 일관되게 유지한다.
    pair_checks = 0
    for part in (1, 2, 3):
        for u in load(folder / f'input-{part}.private.json'):
            if u['negative'] is None:
                continue
            p, n = by_id[u['positive']['example_id']], by_id[u['negative']['example_id']]
            common = {c['id'] for c in u['positive']['request']['candidates']} & {c['id'] for c in u['negative']['request']['candidates']}
            for field in ('valid_candidate_ids', 'uncertain_candidate_ids'):
                require(set(p[field]) & common == set(n[field]) & common, 'pair_candidate_inconsistency')
            pair_checks += 1
    require(pair_checks == 139, 'pair_check_count')
    train_groups = {e['conversation_id'] for e in original}
    selected_ids = {e['example_id'] for e in proposed}
    selected_groups = {e['conversation_id'] for e in proposed}
    boundary = {}
    for split in ('calibration', 'selection', 'test'):
        # 평가 문장·라벨은 읽어 학습 입력으로 만들지 않는다. 경계 식별자만 대조한다.
        metadata = load(root / '.work/data' / (split + '.examples.json'))
        other_ids = {e['example_id'] for e in metadata}
        other_groups = {e['conversation_id'] for e in metadata}
        require(not selected_ids & other_ids and not train_groups & other_groups, 'split_leakage')
        boundary[split] = {'id_overlap': 0, 'group_overlap': 0, 'source_unchanged': True}
    after = {name: sha(root / name) for name in before}
    require(before == after, 'source_changed_after_selection')
    summary = {
        'status': 'review_complete_training_not_started', 'review_version': 'manual_train_review_v1',
        'annotation_sha256': {f'review-{part}.private.json': sha(folder / f'review-{part}.private.json') for part in (1, 2, 3)},
        'original': {'total': 697, 'positive': 558, 'derived_no_answer': 139, 'groups': len(train_groups)},
        'categories': {c: counts[c] for c in CATEGORIES},
        'by_original_role': {role: {c: values[c] for c in CATEGORIES} for role, values in original_role_counts.items()},
        'selected_proposal': {'total': len(selected), 'positive': counts['unique'], 'no_answer': counts['none'], 'groups': len(selected_groups)},
        'preserved_held': {'total': len(held), 'multiple': counts['multiple'], 'uncertain': counts['uncertain'], 'groups': len({r['source_example']['conversation_id'] for r in held})},
        'proposed_label_changes': dict(gold_changes),
        'unchanged_label_selected': len(selected) - sum(gold_changes.values()),
        'pair_checks': pair_checks, 'boundaries': boundary,
        'original_eight_files_unchanged': True, 'new_model_calls': 0, 'new_training_runs': 0,
        'optimizer_updates_plan': {'original_697': 88, 'clean_natural_1_epoch': (len(selected) + 7) // 8, 'matched_697_presentations': 88},
        'limitations': ['수동 잠정 의미 검토이며 공식 taxonomy 정정/전문가 인수가 아니다', '새 학습과 token gate는 수행하지 않았다', '이미 공개된 평가 결과를 새로운 미사용 test라고 주장하지 않는다']}
    require(len(selected) + len(held) == 697, 'partition_count')
    output.mkdir(exist_ok=True)
    preserve_write(output / 'selected.review.private.json', selected)
    preserve_write(output / 'selected.proposed.examples.private.json', proposed)
    preserve_write(output / 'held.review.private.json', held)
    preserve_write(output / 'multiple.review.private.json', [r for r in held if r['review']['category'] == 'multiple'])
    preserve_write(output / 'uncertain.review.private.json', [r for r in held if r['review']['category'] == 'uncertain'])
    preserve_write(output / 'all.review.private.json', [by_id[e['example_id']] for e in original])
    preserve_write(output / 'preservation.after.private.json', after)
    preserve_write(output / 'summary.private.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    run(parser.parse_args().root)
