"""별도 수동 맥락 검토표를 저장된 calibration 점수로 집계한다.

모델 import/호출, 원본/기존 평가 변경, final-test 계산 없음.
검토 판단 TSV와 원문 출력은 ignored .work/semantic_review에만 둔다.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

ABSTAIN = '__judgment_abstain__'
CLASSES = ('유일한 정답', '복수의 타당한 답', '정말 맞는 후보 없음', '문맥 부족')


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def classification(valid, uncertain):
    # 확정 2개면 복수는 확인됐다. 추가 미확정 후보의 판정은 별도 범위로 남긴다.
    if len(valid) >= 2:
        return CLASSES[1]
    if uncertain:
        return CLASSES[3]
    return CLASSES[0] if valid else CLASSES[2]


def predict(row, candidates, valid, uncertain):
    ids, logits = row['ids'], row['logits']
    require(ids == candidates + [ABSTAIN] and len(logits) == 6, 'candidate_order')
    require(len(set(ids)) == 6, 'duplicate_candidate')
    require(all(isinstance(v, (float, int)) and v == v and abs(v) != float('inf') for v in logits), 'finite')
    require(sum(v == max(logits) for v in logits) == 1, 'all_top1_tie')
    require(sum(v == max(logits[:5]) for v in logits[:5]) == 1, 'business_top1_tie')
    business = ids[max(range(5), key=lambda i: logits[i])]
    winner = ids[max(range(6), key=lambda i: logits[i])]
    ranks = {cid: 1 + sum(v > logits[ids.index(cid)] for v in logits[:5]) for cid in valid}
    return {'prediction': winner, 'abstain': winner == ABSTAIN,
            'business_prediction': business, 'business_known_valid': business in valid,
            'prediction_known_valid': winner in valid,
            'prediction_uncertain': winner in uncertain, 'business_uncertain': business in uncertain,
            'best_valid_rank': min(ranks.values()) if ranks else None,
            'candidate_valid_ranks': ranks, 'ids': ids, 'logits': logits}


def aggregate(rows, phase, category):
    selected = [r for r in rows if r['category'] == category]
    scores = [r[phase] for r in selected]
    n = len(scores)
    out = {'items': n, 'abstain': sum(s['abstain'] for s in scores),
           'abstain_rate': sum(s['abstain'] for s in scores) / n if n else None}
    if category == CLASSES[3]:
        return {**out, 'accuracy': None, 'reason': '문맥 또는 후보 경계 미확정; 정답 지표 분모 제외'}
    if category == CLASSES[2]:
        return {**out, 'correct': out['abstain'], 'accuracy': out['abstain_rate'],
                'business_accuracy': None, 'mean_best_valid_rank': None}
    business_right = sum(s['business_known_valid'] for s in scores)
    correct = sum(s['prediction_known_valid'] for s in scores)
    possible_extra = sum(s['prediction_uncertain'] for s in scores)
    business_extra = sum(s['business_uncertain'] for s in scores)
    ranks = [s['best_valid_rank'] for s in scores]
    return {**out, 'correct_known': correct, 'uncertain_prediction': possible_extra,
            'accuracy_lower': correct / n if n else None,
            'accuracy_upper': (correct + possible_extra) / n if n else None,
            'business_correct_known': business_right, 'business_uncertain': business_extra,
            'business_accuracy_lower': business_right / n if n else None,
            'business_accuracy_upper': (business_right + business_extra) / n if n else None,
            'mean_best_valid_rank': sum(ranks) / n if n else None,
            'best_valid_rank_histogram': {str(i): ranks.count(i) for i in range(1, 6)},
            'rank1_abstain': sum(s['abstain'] and s['best_valid_rank'] == 1 for s in scores)}


def run(root):
    root = root.resolve()
    folder = root / '.work/semantic_review'
    pairs_path, decisions_path = folder / 'pairs.private.json', folder / 'decisions.private.tsv'
    baseline_paths = [root / '.work/data/calibration.examples.json',
                      root / '.work/runs/g1-trial-17c30baf57c0428fa5dcb6c953ec075a/base.scores.private.json',
                      root / '.work/runs/g1-trial-17c30baf57c0428fa5dcb6c953ec075a/trained.scores.private.json',
                      root / '.work/runs/run-52e908810f4342929f980af3b680f301/output/train_report.json',
                      root / '.work/score_diagnosis/summary.private.json',
                      root / '.work/data_review/group_map.private.json',
                      root / '.work/data_review/inheritance_manifest.private.json',
                      root / 'docs/한국어대화_new_260226.zip', root / 'docs/G1_SCORE_DIAGNOSIS.md',
                      root / 'MODEL_CARD.md', pairs_path, decisions_path,
                      folder / 'label_usage.private.json']
    source_hashes = {str(p): sha(p) for p in baseline_paths}
    anchor = load(root / '.work/data_review/inheritance_manifest.private.json')
    require(sha(baseline_paths[5]) == anchor['full_group_map_sha256'], 'group_anchor')
    require(sha(baseline_paths[7]) == anchor['source_archive_sha256'], 'archive_anchor')
    pairs = load(pairs_path)
    with decisions_path.open(encoding='utf-8', newline='') as stream:
        decisions = list(csv.DictReader(stream, delimiter='\t'))
    require(len(pairs) == len(decisions) == 92, 'pair_count')
    require([int(d['n']) for d in decisions] == list(range(1, 93)), 'decision_order')
    examples = load(baseline_paths[0])
    index = {e['example_id']: e for e in examples}
    require(len(index) == len(examples) == 457, 'example_uniqueness')
    negatives = {e['example_id'] for e in examples if e['gold_id'] is None}
    require({p['negative_id'] for p in pairs} == negatives, 'negative_coverage')
    # 검토표 digest를 고정한 다음 저장 score의 calibration 배열만 참조한다.
    score_sets = {phase: load(path)['calibration'] for phase, path in
                  [('before', baseline_paths[1]), ('after', baseline_paths[2])]}
    scores = {phase: {s['example_id']: s for s in values} for phase, values in score_sets.items()}
    require(all(len(ix) == len(score_sets[phase]) == 457 and set(ix) == set(index)
                for phase, ix in scores.items()), 'score_join')
    records = []
    for pair, decision in zip(pairs, decisions):
        require(pair['n'] == int(decision['n']), 'case_order')
        valid = set(filter(None, decision['valid_ids'].split(',')))
        uncertain = set(filter(None, decision['uncertain_ids'].split(',')))
        require(not valid & uncertain and valid | uncertain <= set(pair['union_candidates']), 'review_candidate_membership')
        for role, id_key, candidates_key in [('positive', 'positive_id', 'positive_candidates'),
                                             ('negative', 'negative_id', 'negative_candidates')]:
            example = index[pair[id_key]]
            candidates = [c['id'] for c in example['request']['candidates']]
            require(candidates == pair[candidates_key], 'pair_candidates')
            require(example['request']['utterance'] == pair['utterance'] and
                    example['request']['context'] == pair['context'] and
                    example['source_id'] == pair['source_id'] and
                    example['conversation_id'] == pair['group'], 'pair_input_context')
            require(example['gold_id'] == (pair['original_gold'] if role == 'positive' else None), 'original_gold')
            local_valid = sorted(valid & set(candidates))
            local_uncertain = sorted(uncertain & set(candidates))
            category = classification(local_valid, local_uncertain)
            records.append({'case': pair['n'], 'variant': role, 'example_id': example['example_id'],
                            'source_id': pair['source_id'], 'group': pair['group'],
                            'utterance': pair['utterance'], 'context': pair['context'],
                            'candidates': example['request']['candidates'], 'original_gold_id': example['gold_id'],
                            'category': category, 'valid_candidate_ids': local_valid,
                            'uncertain_candidate_ids': local_uncertain,
                            'invalid_candidate_ids': sorted(set(candidates) - valid - uncertain),
                            'rule_id': decision['rule'], 'reason': decision['reason'],
                            'review_status': '어울 수동 맥락 검토 v1; 공식 라벨 변경 아님',
                            **{phase: predict(ix[example['example_id']], candidates, local_valid, local_uncertain)
                               for phase, ix in scores.items()}})
    require(len({r['example_id'] for r in records}) == 184, 'record_coverage')
    usage = load(folder / 'label_usage.private.json')
    criteria = []
    for pair, decision in zip(pairs, decisions):
        criteria.append({'case': pair['n'], 'rule_id': decision['rule'], 'reason': decision['reason'],
                         'official_definition': '원본 ZIP은 XLSX 13개만 포함; 별도 의도 정의서 없음',
                         'evidence_scope': '기존 확정 train 분할의 원본 발화/MAIN/SUB 사용례; final-test 제외',
                         'sample_limit': '라벨별 앞선 최대5개 사용례; 규범적 정의나 배타 경계의 증명 아님',
                         'labels': {cid: usage[cid] for cid in pair['union_candidates']}})
    result = {'pairs': 92, 'records': 184, 'groups': len({r['group'] for r in records}),
              'new_model_calls': 0, 'test_metrics': False, 'settings_changed': False,
              'annotation_sha256': source_hashes[str(decisions_path)], 'scope': '92 calibration 파생과 그 원본 92개만',
              'method': '현재 발화+저장된 과거 맥락; 후보 정의는 학습용 원본 사용례와 대조; 수동 잠정 검토',
              'variants': {}, 'transition': dict(collections.Counter(
                  f"{p['category']} -> {n['category']}" for p, n in zip(records[::2], records[1::2])))}
    for role in ('positive', 'negative'):
        rows = [r for r in records if r['variant'] == role]
        result['variants'][role] = {phase: {category: aggregate(rows, phase, category) for category in CLASSES}
                                    for phase in ('before', 'after')}
    result['original_positive_gold_review'] = dict(collections.Counter(
        'confirmed' if r['original_gold_id'] in r['valid_candidate_ids'] else
        'uncertain' if r['original_gold_id'] in r['uncertain_candidate_ids'] else 'not_current_intent'
        for r in records if r['variant'] == 'positive'))
    result['original_exact_id'] = {role: {phase: sum(r[phase]['prediction'] ==
        (r['original_gold_id'] or ABSTAIN) for r in records if r['variant'] == role)
        for phase in ('before', 'after')} for role in ('positive', 'negative')}
    require(source_hashes == {str(p): sha(p) for p in baseline_paths}, 'baseline_mutation')
    (folder / 'review_table.private.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'summary.private.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'preservation.private.json').write_text(json.dumps(source_hashes, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'criteria_evidence.private.json').write_text(json.dumps(criteria, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# calibration 92쌍 맥락 검토표', '', '수동 검토 v1. 원본 라벨/평가를 변경하지 않은 별도 검토. 문맥 부족은 입력 부족 또는 후보 구분 정의 부족을 포함한다.',
             '확정 2개 이상이면 복수, 확정 0~1개인데 미확정 후보가 있으면 문맥 부족. 문맥 부족에는 입력 누락과 후보 정의 부족이 있으므로 각 근거를 구별해 읽는다. 복수의 미확정 ID는 정확도 범위에만 반영한다.',
             '의도 구분의 상세 출처 사용례: criteria_evidence.private.json. 공식 정의서가 없어 확인 가능한 사용례와 미확정 경계를 분리했다.', '']
    for p, n in zip(records[::2], records[1::2]):
        lines += [f"## 사례 {p['case']} — {p['source_id']}", '', f"입력: {p['utterance']}", '', '저장된 과거 맥락 전체:', '']
        lines += [f"- {t['role']}: {t['content']}" for t in p['context']] or ['- 없음']
        lines += ['', f"판단 기준 {p['rule_id']}: {p['reason']}", '', '| ID | 후보 설명 | 원본에 있음 | 파생에 있음 | 판단 |', '|---|---|---|---|---|']
        union = {c['id']: c['description'] for c in p['candidates'] + n['candidates']}
        for cid, desc in union.items():
            status = '타당' if cid in set(p['valid_candidate_ids'] + n['valid_candidate_ids']) else '미확정' if cid in set(p['uncertain_candidate_ids'] + n['uncertain_candidate_ids']) else '부적합'
            lines += [f"| {cid} | {desc} | {cid in p['before']['ids'][:5]} | {cid in n['before']['ids'][:5]} | {status} |"]
        for row in (p, n):
            lines += ['', f"{row['variant']}: **{row['category']}**; 기존 정답 `{row['original_gold_id']}`; 타당 ID `{','.join(row['valid_candidate_ids']) or '없음'}`; 미확정 ID `{','.join(row['uncertain_candidate_ids']) or '없음'}`.",
                      f"저장 예측: `{row['before']['prediction']}` → `{row['after']['prediction']}`; 업무5 예측: `{row['before']['business_prediction']}` → `{row['after']['business_prediction']}`."]
        lines += ['']
    (folder / 'review_table.private.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    print(json.dumps(run(parser.parse_args().root), ensure_ascii=True, indent=2))
