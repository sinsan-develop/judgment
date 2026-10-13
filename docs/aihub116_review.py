"""AI Hub 116 로컬 데이터 적합성 조사. 원문을 출력/저장/전송하지 않는다.

실행: bundled Python aihub116_review.py --archive ZIP --output IGNORED_DIRECTORY
요약은 원문 없는 집계, mapping은 로컬 전용 row index와 내부 그룹 번호뿐이다.
"""
import argparse
import collections
import hashlib
import io
import json
import math
from pathlib import Path
import random
import re
import unicodedata
import warnings
import zipfile

SCHEMA_VERSION = 'aihub116-review-v2-inherited-pilot'
SPLITS = ('train', 'calibration', 'selection', 'test')
RATIOS = (.7, .1, .1, .1)


def normalized(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(value))).strip() if value is not None else ''


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def entry_name(info):
    if not info.flag_bits & 0x800:
        try: return info.filename.encode('cp437').decode('cp949')
        except UnicodeError: pass
    return info.filename


def numeric_turn(value):
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number.is_integer() and number >= 1 else None
    except (TypeError, ValueError): return None


def bad_label(value):
    return value.casefold() in ('', '.', '-', 'null', 'none', 'nan', 'n/a', 'unknown', '미상')


class UnionFind:
    def __init__(self, n): self.parent = list(range(n))
    def root(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]; i = self.parent[i]
        return i
    def join(self, a, b): self.parent[self.root(a)] = self.root(b)


def ingest(archive):
    import openpyxl  # 실제 XLSX 판독 때만 필요하다. 합성 그룹 시험은 표준 라이브러리만 사용.
    all_rows, profiles = [], []
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('crc_failure')
        for file_index, info in enumerate(z.infolist()):
            if not info.filename.endswith('.xlsx'): raise ValueError('unexpected_file_type')
            wb = openpyxl.load_workbook(io.BytesIO(z.read(info)), read_only=True, data_only=True)
            if len(wb.worksheets) != 1: raise ValueError('unexpected_sheets')
            it = wb.worksheets[0].iter_rows(values_only=True)
            headers = [normalized(v) for v in next(it)]
            ix = {v: i for i, v in enumerate(headers) if v}
            business = 'SENTENCE' in ix
            required = ('SPEAKER', 'SENTENCE', 'MAIN', 'SUB', 'SENTENCEID', 'QA') if business else ('화자', '비식별 데이터', 'subintent', 'question')
            if any(k not in ix for k in required): raise ValueError('unexpected_schema')
            label_key = 'MAIN' if business else ('intent' if 'intent' in ix else 'main')
            if label_key not in ix: raise ValueError('missing_intent_column')
            rows = []
            for excel_row, values in enumerate(it, 2):
                if not any(normalized(v) for v in values): continue
                def cell(k):
                    i = ix.get(k)
                    return values[i] if i is not None and i < len(values) else None
                rows.append(dict(file=file_index, excel_row=excel_row, schema='business' if business else 'public',
                                 role=normalized(cell('SPEAKER' if business else '화자')),
                                 utterance=normalized(cell('SENTENCE' if business else '비식별 데이터')),
                                 label=normalized(cell(label_key)), sub=normalized(cell('SUB' if business else 'subintent')),
                                 turn=numeric_turn(cell('SENTENCEID')), qa=normalized(cell('QA')),
                                 qacnct=normalized(cell('QACNCT')),
                                 domain=normalized(cell('DOMAIN' if business else headers[0]))))
            wb.close()
            segments = []
            if business:
                block = []
                for row in rows:
                    # 순번 1 재시작만 경계 후보로 삼고, 누락/순번 불연속 블록은 격리한다.
                    if row['turn'] == 1 and block:
                        segments.append(block); block = []
                    block.append(row)
                if block: segments.append(block)
            else:
                # 명시 대화 ID 없는 공공민원은 파일 전체를 분할 금지 그룹으로 둔다.
                segments = [rows]
            malformed = 0
            for block_index, block in enumerate(segments):
                valid = business and [r['turn'] for r in block] == list(range(1, len(block)+1))
                if business and not valid: malformed += 1
                history = []
                for row in block:
                    row['block'] = (file_index, block_index)
                    row['valid_context_block'] = valid
                    # 공공민원은 대화 순서 근거가 없어 맥락을 합성하지 않는다.
                    row['context'] = tuple(history) if valid else ()
                    role = 'user' if row['role'] in ('고객', '민원인') else 'assistant'
                    if row['utterance']: history.append((role, row['utterance']))
            profiles.append({'file_index':file_index,'schema':'business' if business else 'public',
                             'nonempty_rows':len(rows),'source_blocks':len(segments),'malformed_blocks':malformed,
                             'headers':headers,'archive_name':entry_name(info)})
            all_rows.extend(rows)
    return all_rows, profiles


def analyze(rows, profiles, *, seed=13, full_mapping=None):
    excluded = collections.Counter()
    eligible = []
    for row in rows:
        if row['role'] not in ('고객','민원인'): reason = 'non_user_role'
        elif not row['utterance']: reason = 'missing_anonymized_utterance'
        elif bad_label(row['label']): reason = 'missing_or_placeholder_intent'
        elif row['schema'] == 'business' and not row['valid_context_block']: reason = 'unreliable_turn_block'
        elif row['schema'] == 'business' and row['qa'] not in ('Q','A'): reason = 'invalid_qa_flag'
        else: reason = None
        if reason: excluded[reason] += 1; continue
        row = dict(row)
        # 의도는 파일 도메인+MAIN으로 구분하고 SUB는 추적용으로 유지한다.
        row['target'] = (row['file'], row['label'])
        row['input_key'] = digest((row['utterance'],row['context']))
        eligible.append(row)
    conflicting_inputs = {key for key, group in _group_by(eligible,'input_key').items() if len({r['target'] for r in group}) > 1}
    usable = [r for r in eligible if r['input_key'] not in conflicting_inputs]
    excluded['contradictory_same_input'] = len(eligible)-len(usable)
    # 완전 동일한 입력+gold는 대표 1개로 줄이되 전체 출처 연결은 보존한다.
    identical = _group_by(usable,'input_key')
    representatives = [group[0] for key,group in sorted(identical.items())]
    u = UnionFind(len(representatives))
    seen_blocks, seen_text = {}, {}
    for i, rep in enumerate(representatives):
        for origin in identical[rep['input_key']]:
            key=origin['block']
            if key in seen_blocks: u.join(i,seen_blocks[key])
            else: seen_blocks[key]=i
        # 현재 발화만 같아도 같은 split에 두며 짧은 반복 문장의 큰 연결을 숨기지 않는다.
        key = digest(rep['utterance'])
        if key in seen_text: u.join(i,seen_text[key])
        else: seen_text[key]=i
    groups = collections.defaultdict(list)
    for i,r in enumerate(representatives): groups[u.root(i)].append(r)
    stable_groups = sorted(groups.values(),key=lambda g:min(r['input_key'] for r in g))
    random.Random(seed).shuffle(stable_groups)
    ideal = [len(stable_groups)*r for r in RATIOS]; group_counts=[math.floor(v) for v in ideal]
    for i in sorted(range(4),key=lambda i:ideal[i]-group_counts[i],reverse=True)[:len(stable_groups)-sum(group_counts)]: group_counts[i]+=1
    if full_mapping is None:
        parts=balanced_parts(stable_groups,seed=seed)
    else:
        # G1 추출은 저장된 확정 배정만 사용하며 splitter를 다시 호출하지 않는다.
        fixed={(r['file_index'],r['excel_row']):r for r in full_mapping}
        if len(fixed)!=len(full_mapping): raise ValueError('fixed_full_split_changed')
        parts={split:[] for split in SPLITS}; seen=set()
        for group_i,group in enumerate(stable_groups):
            assignments=set()
            for representative in group:
                for origin in identical[representative['input_key']]:
                    key=(origin['file'],origin['excel_row']);seen.add(key)
                    saved=fixed.get(key)
                    if saved is None or saved['group']!=group_i or saved['representative']!=(origin is representative):
                        raise ValueError('fixed_full_split_changed')
                    assignments.add(saved['split'])
            if len(assignments)!=1 or not assignments<=set(SPLITS): raise ValueError('fixed_full_split_changed')
            parts[next(iter(assignments))].append(group)
        if seen!=set(fixed): raise ValueError('fixed_full_split_changed')
    intersections={}
    for a_idx,a in enumerate(SPLITS):
        for b in SPLITS[a_idx+1:]:
            ra=[r for g in parts[a] for r in g]; rb=[r for g in parts[b] for r in g]
            intersections[a+'_'+b]={'input':len({r['input_key'] for r in ra}&{r['input_key'] for r in rb}),
                                  'utterance':len({digest(r['utterance']) for r in ra}&{digest(r['utterance']) for r in rb}),
                                  'block':len({o['block'] for r in ra for o in identical[r['input_key']]}&{o['block'] for r in rb for o in identical[r['input_key']]})}
    split_summary={k:{'groups':len(gs),'examples':sum(len(g) for g in gs),'intents':len({r['target'] for g in gs for r in g})} for k,gs in parts.items()}
    inventory=collections.defaultdict(lambda: {'rows':0,'examples':0,'intents':set(),'groups':set()})
    for r in usable:inventory[r['schema']]['rows']+=1
    for group_i,g in enumerate(stable_groups):
        for r in g:
            entry=inventory[r['schema']];entry['examples']+=1;entry['intents'].add(r['target']);entry['groups'].add(group_i)
    schema_summary={k:{**{kk:v for kk,v in d.items() if kk not in ('intents','groups')},'intents':len(d['intents']),'groups':len(d['groups'])} for k,d in inventory.items()}
    summary={'version':SCHEMA_VERSION,'seed':seed,'total_rows':len(rows),'excluded':dict(excluded),
             'eligible_before_conflicts':len(eligible),'retained_source_rows':len(usable),
             'duplicate_extra_rows_removed':len(usable)-len(representatives),'unique_input_examples':len(representatives),
             'distinct_utterances':len({r['utterance'] for r in representatives}),'intent_count':len({r['target'] for r in representatives}),
             'intent_label_text_count':len({r['label'] for r in representatives}),
             'group_count':len(stable_groups),'group_sizes_desc':sorted((len(g) for g in stable_groups),reverse=True)[:15],
             'schemas':schema_summary,'split':split_summary,'split_intersections':intersections,
             'group_split_possible':all(parts[k] for k in SPLITS) and all(all(v==0 for v in checks.values()) for checks in intersections.values()),
             'full_split_loaded_from_fixed_mapping':full_mapping is not None,
             'profiles':profiles,'tokenizer_checked':False,'gold_absent_source_rows_used':0,
             'quality_gate':'data_rules_proposal_not_training_approval'}
    assert len(rows)==sum(excluded.values())+len(usable)
    assert sum(v['examples'] for v in split_summary.values())==len(representatives)
    assert all(all(v==0 for v in checks.values()) for checks in intersections.values())
    summary['pilot']=pilot_plan(stable_groups,seed=seed,full_parts=parts)
    summary['groups_are_conservative_not_verified_source_dialogue_ids']=True
    group_ids={id(g):i for i,g in enumerate(stable_groups)}
    mapping=[{'file_index':origin['file'],'excel_row':origin['excel_row'],'group':group_ids[id(g)],'split':split,
              'representative':origin is r}
             for split,gs in parts.items() for g in gs for r in g for origin in identical[r['input_key']]]
    return summary,mapping


def balanced_parts(groups, *, ratios=RATIOS, seed=13):
    """연결 성분을 자르지 않고 행 수 목표에 가장 부족한 split에 배정한다."""
    shuffled=groups[:];random.Random(seed).shuffle(shuffled)
    ordered=sorted(shuffled,key=len,reverse=True)
    total=sum(map(len,groups));targets=[total*r for r in ratios];counts=[0]*4;parts={k:[] for k in SPLITS}
    for group in ordered:
        i=max(range(4),key=lambda i:targets[i]-counts[i])
        parts[SPLITS[i]].append(group);counts[i]+=len(group)
    return parts


def pilot_plan(groups, *, seed=13, full_parts):
    """큰 연결/공공민원은 첫 시험에서 제외하고 완전한 소상공인 그룹만 고른다."""
    eligible=[g for g in groups if len(g)<=160 and all(r['schema']=='business' for r in g)]
    random.Random(seed).shuffle(eligible)
    chosen=[];count=0
    for group in eligible:
        if count+len(group)<=1600:chosen.append(group);count+=len(group)
    # 후보 선정 순서만 고정 seed를 사용한다. 분할은 확정 전체 자료에서 상속한다.
    membership=collections.defaultdict(list)
    for split,full_groups in full_parts.items():
        if split not in SPLITS: raise ValueError('full_group_assignment')
        for group in full_groups: membership[id(group)].append(split)
    if any(len(membership[id(group)])!=1 for group in groups):
        raise ValueError('full_group_assignment')
    parts={split:[group for group in chosen if membership[id(group)][0]==split] for split in SPLITS}
    group_ids={id(group):i for i,group in enumerate(groups)}
    assignments=[{'group':group_ids[id(group)],'split':split,'full_split':membership[id(group)][0],
                  'positive_examples':len(group)} for split,part in parts.items() for group in part]
    base_counts=[sum(map(len,parts[k])) for k in SPLITS]
    total_absent=min(400,count//4)
    raw=[total_absent*n/count if count else 0 for n in base_counts];absent=[math.floor(n) for n in raw]
    for i in sorted(range(4),key=lambda i:raw[i]-absent[i],reverse=True)[:total_absent-sum(absent)]:absent[i]+=1
    overlaps={}
    for i,a in enumerate(SPLITS):
        for b in SPLITS[i+1:]:
            ra=[r for g in parts[a] for r in g];rb=[r for g in parts[b] for r in g]
            overlaps[a+'_'+b]={'input':len({r['input_key'] for r in ra}&{r['input_key'] for r in rb}),
                              'utterance':len({digest(r['utterance']) for r in ra}&{digest(r['utterance']) for r in rb})}
    assert all(all(v==0 for v in d.values()) for d in overlaps.values())
    return {'business_only':True,'max_component_examples':160,'eligible_groups':len(eligible),'selected_groups':len(chosen),
            'positive_examples':count,'derived_no_answer_examples':sum(absent),'total_planned_examples':count+sum(absent),
            'intent_count':len({r['target'] for g in chosen for r in g}),
            'split':{k:{'groups':len(parts[k]),'positive':base_counts[i],'derived_no_answer':absent[i],'total':base_counts[i]+absent[i]} for i,k in enumerate(SPLITS)},
            'split_intersections':overlaps,'inherits_full_split':True,'group_assignment':assignments,
            'actual_candidates_generated':False,'actual_tokenizer_checked':False,
            'selection_rule':'complete connected components only; max 1600 positives then up to 400 post-split gold-excluded variants'}


def _group_by(rows,key):
    result=collections.defaultdict(list)
    for row in rows:result[row[key]].append(row)
    return result


def preserve_json_record(path,value):
    """기존 승인 근거는 비교만 하며 덮어쓰지 않는다."""
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))!=value:
            raise ValueError('existing_analysis_changed')
        return
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    warnings.filterwarnings('ignore',message='Workbook contains no default style')
    full_path=args.output/'group_map.private.json'
    if not full_path.is_file(): raise ValueError('fixed_full_map_required')
    full=json.loads(full_path.read_text(encoding='utf-8'))
    rows,profiles=ingest(args.archive);summary,mapping=analyze(rows,profiles,full_mapping=full)
    args.output.mkdir(parents=True,exist_ok=True)
    assignments=summary['pilot']['group_assignment']
    expected={(row['file_index'],row['excel_row']):(row['group'],row['split']) for row in full}
    actual={(row['file_index'],row['excel_row']):(row['group'],row['split']) for row in mapping}
    if expected!=actual: raise ValueError('fixed_full_split_changed')
    for assignment in assignments:
        origins=[row for row in full if row['group']==assignment['group']]
        if not origins or {row['split'] for row in origins}!={assignment['split']}:
            raise ValueError('pilot_does_not_inherit_full_split')
    preserve_json_record(args.output/'summary.json',summary)
    preserve_json_record(args.output/'pilot_groups.private.json',assignments)
    # 기준 전체 mapping은 읽기 전용으로 보존한다.
    safe={k:v for k,v in summary.items() if k not in ('profiles','split_intersections')}
    safe['pilot']={k:v for k,v in summary['pilot'].items() if k!='group_assignment'}
    print(json.dumps(safe,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
