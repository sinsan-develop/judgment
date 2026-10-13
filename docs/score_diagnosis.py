"""저장 점수만 진단한다. 모델 import/호출, test 지표 계산, 설정 변경 없음.

실행: python docs/score_diagnosis.py --root . --output .work/score_diagnosis
대표 원문은 ignored 출력에만 기록한다. 공개 출력은 집계뿐이다.
"""
import argparse
import collections
import difflib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import warnings

ABSTAIN = '__judgment_abstain__'
JOB = 'g1-trial-17c30baf57c0428fa5dcb6c953ec075a'
TRAIN = 'run-52e908810f4342929f980af3b680f301'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def scored_rows(examples, scores):
    by_id = {row['example_id']: row for row in scores}
    require(len(by_id) == len(scores) == len(examples), 'score_unique_count')
    require(set(by_id) == {e['example_id'] for e in examples}, 'score_join_coverage')
    result = []
    for e in examples:
        row = by_id[e['example_id']]
        business = [c['id'] for c in e['request']['candidates']]
        ids, logits = row['ids'], row['logits']
        require(len(business) == len(set(business)) == 5, 'five_business_candidates')
        require(ids == business + [ABSTAIN] and len(logits) == 6, 'score_candidate_order')
        require(all(math.isfinite(v) for v in logits), 'finite_logits')
        require(e['gold_id'] is None or e['gold_id'] in business, 'gold_membership')
        winners = [i for i, v in enumerate(logits) if v == max(logits)]
        business_winners = [i for i, v in enumerate(logits[:5]) if v == max(logits[:5])]
        require(len(winners) == len(business_winners) == 1, 'ambiguous_top1_tie')
        rank = None if e['gold_id'] is None else 1 + sum(
            v > logits[ids.index(e['gold_id'])] for v in logits[:5])
        require(rank is None or sum(v == logits[ids.index(e['gold_id'])] for v in logits[:5]) == 1,
                'gold_rank_tie')
        result.append({'example_id': e['example_id'], 'rank': rank,
                       'business_prediction': ids[business_winners[0]],
                       'prediction': ids[winners[0]], 'abstain': ids[winners[0]] == ABSTAIN,
                       'ids': ids, 'logits': logits})
    return result


def metrics(rows):
    answerable = [r for r in rows if r['rank'] is not None]
    no_answer = [r for r in rows if r['rank'] is None]
    counts = collections.Counter(r['rank'] for r in answerable)
    return {'items': len(rows), 'answerable': len(answerable), 'no_answer': len(no_answer),
            'business_correct': counts[1], 'business_accuracy': counts[1] / len(answerable),
            'rank_histogram': {str(i): counts[i] for i in range(1, 6)},
            'mean_rank': sum(r['rank'] for r in answerable) / len(answerable),
            'mrr': sum(1 / r['rank'] for r in answerable) / len(answerable),
            'answerable_abstain': sum(r['abstain'] for r in answerable),
            'answerable_abstain_rate': sum(r['abstain'] for r in answerable) / len(answerable),
            'no_answer_abstain': sum(r['abstain'] for r in no_answer),
            'no_answer_abstain_rate': sum(r['abstain'] for r in no_answer) / len(no_answer),
            'rank1_abstain': sum(r['abstain'] and r['rank'] == 1 for r in answerable),
            'six_way_correct': sum(r['rank'] == 1 and not r['abstain'] for r in answerable)
                               + sum(r['abstain'] for r in no_answer)}


def diagnose(root, output):
    root, output = root.resolve(), output.resolve()
    require(output.is_relative_to(root / '.work'), 'private_output_required')
    paths = [root / '.work/data' / f'{s}.examples.json' for s in ('calibration', 'selection')]
    paths += [root / '.work/runs' / JOB / f'{s}.scores.private.json' for s in ('base', 'trained')]
    paths += [root / '.work/runs' / TRAIN / 'output/train_report.json',
              root / '.work/data_review/group_map.private.json',
              root / '.work/data_review/inheritance_manifest.private.json',
              root / 'docs/한국어대화_new_260226.zip']
    before_hashes = {str(p): sha(p) for p in paths}
    calibration, selection = map(load, paths[:2])
    # 같은 JSON에 있는 test 배열을 지표 계산이나 사례 선정에 사용하지 않는다.
    base, trained = [load(p)['calibration'] for p in paths[2:4]]
    report, mapping, anchor = map(load, paths[4:7])
    require(before_hashes[str(paths[5])] == anchor['full_group_map_sha256'], 'full_mapping_anchor')
    require(before_hashes[str(paths[7])] == anchor['source_archive_sha256'], 'archive_anchor')
    require(report['eval_items'] == report['before']['items'] == report['after']['items'] == len(selection),
            'selection_report_items')
    require(report['is_held_out'] and Path(report['eval_source']).name == 'selection.jsonl', 'selection_role')
    a, b = scored_rows(calibration, base), scored_rows(calibration, trained)
    require([r['example_id'] for r in a] == [r['example_id'] for r in b], 'paired_comparison')
    require(all(x['ids'] == y['ids'] for x, y in zip(a, b)), 'paired_candidate_order')
    spec = importlib.util.spec_from_file_location('review', root / 'docs/aihub116_review.py')
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='Workbook contains no default style')
        raw_rows, profiles = review.ingest(paths[7])
    domains = {p['file_index']: re.sub(r'^[A-I]\s+', '', p['archive_name']).split('(')[0].strip()
               for p in profiles if p['schema'] == 'business'}
    keys = sorted({(r['file'], r['label']) for r in raw_rows
                   if r['schema'] == 'business' and not review.bad_label(r['label'])})
    taxonomy = {f'i{i:05d}': (file, label, domains[file] + ' / ' + label)
                for i, (file, label) in enumerate(keys)}
    raw = {(r['file'], r['excel_row']): r for r in raw_rows}
    full = {(r['file_index'], r['excel_row']): r for r in mapping}
    linked = {}
    all_ids = set()
    for split, examples in [('calibration', calibration), ('selection', selection)]:
        linked[split] = {}
        for e in examples:
            require(e['example_id'] not in all_ids, 'duplicate_example')
            all_ids.add(e['example_id'])
            _, file, row = e['source_id'].split('-')
            key = int(file), int(row)
            origin, assign = raw[key], full[key]
            require(assign['representative'] and assign['split'] == split, 'source_split')
            require(e['conversation_id'] == e['duplicate_group'] == f"component-{assign['group']}", 'source_group')
            require(e['request']['utterance'] == origin['utterance'], 'source_utterance')
            require(e['request']['context'] == [{'role': role, 'content': content}
                    for role, content in origin['context']], 'source_context')
            for c in e['request']['candidates']:
                require(taxonomy[c['id']][0] == key[0] and taxonomy[c['id']][2] == c['description'], 'candidate_description')
            gold = next(cid for cid, t in taxonomy.items() if t[:2] == (key[0], origin['label']))
            require(e['gold_id'] == gold if e['gold_id'] is not None else
                    gold not in [c['id'] for c in e['request']['candidates']], 'source_gold')
            distractors = sorted((cid for cid, t in taxonomy.items() if t[0] == key[0] and cid != gold),
                                 key=lambda cid: (-difflib.SequenceMatcher(None, origin['label'], taxonomy[cid][1]).ratio(), cid))
            expected = {gold, *distractors[:4]} if e['gold_id'] is not None else set(distractors[:5])
            require({c['id'] for c in e['request']['candidates']} == expected, 'source_candidate_pool')
            linked[split][e['example_id']] = {'example': e, 'original_gold_description': taxonomy[gold][2]}
        positives = {e['source_id']: e for e in examples if e['gold_id'] is not None}
        for e in examples:
            if e['gold_id'] is None:
                positive = positives[e['source_id']]
                require(all(e['request'][k] == positive['request'][k] for k in ('utterance', 'context', 'question')),
                        'derived_pair_input')
    require(not ({e['conversation_id'] for e in calibration} & {e['conversation_id'] for e in selection}),
            'group_intersection')
    result = {'scope': 'calibration candidate scores; selection existing aggregate only',
              'new_model_calls': 0, 'test_metrics_calculated': False, 'settings_changed': False,
              'calibration': {'before': metrics(a), 'after': metrics(b)},
              'selection': {'answerable': sum(e['gold_id'] is not None for e in selection),
                            'no_answer': sum(e['gold_id'] is None for e in selection),
                            'before': report['before'], 'after': report['after'],
                            'candidate_scores_available': False},
              'linkage': {'checked_examples': len(all_ids), 'mismatches': 0,
                          'calibration_groups': len({e['conversation_id'] for e in calibration}),
                          'selection_groups': len({e['conversation_id'] for e in selection}),
                          'group_intersection': 0, 'semantic_gold_accuracy': 'not established by provenance checks'},
              'transitions': dict(collections.Counter(
                  f"{x['rank']}->{y['rank']}" for x, y in zip(a, b) if x['rank'] is not None))}
    representatives = []
    predicates = [('업무 정답 1위인데 기권 유지', lambda x, y: y['rank'] == 1 and y['abstain']),
                  ('업무 순위 개선', lambda x, y: x['rank'] is not None and y['rank'] < x['rank']),
                  ('업무 정답 하위 유지', lambda x, y: x['rank'] == y['rank'] == 5),
                  ('정답 없는 사례에서 기권 실패', lambda x, y: y['rank'] is None and not y['abstain'])]
    for label, predicate in predicates:
        pair = next(((x, y) for x, y in zip(a, b) if predicate(x, y)), None)
        if pair:
            x, y = pair
            representatives.append({'reason': label, 'split': 'calibration',
                                    **linked['calibration'][x['example_id']], 'before': x, 'after': y})
    for kind in (True, False):
        e = next(e for e in selection if (e['gold_id'] is not None) == kind)
        representatives.append({'reason': 'selection 연결 확인 (점수 없음)', 'split': 'selection',
                                **linked['selection'][e['example_id']]})
    require(before_hashes == {str(p): sha(p) for p in paths}, 'source_mutation')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.private.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'representatives.private.json').write_text(json.dumps(representatives, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'source_hashes.private.json').write_text(json.dumps(before_hashes, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, default=Path('.work/score_diagnosis'))
    args = parser.parse_args()
    print(json.dumps(diagnose(args.root, args.output), ensure_ascii=True, indent=2))
