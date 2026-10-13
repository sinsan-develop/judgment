"""확정 출처 배정만 상속하는 AI Hub 116 최초 시험 변환 경계."""
import difflib
import hashlib
import random
from .contracts import Candidate,Example,SplitBundle,ConfigError,validate_request
from .data import SPLITS,connected_groups,bundle_digest


def build_inherited_pilot(rows,full_mapping,selected_groups,taxonomy,*,derived_counts,seed=13):
    assignment={r['group']:r for r in selected_groups}
    if len(assignment)!=len(selected_groups) or any(r['split'] not in SPLITS or r['split']!=r['full_split'] for r in selected_groups):
        raise ConfigError('inherited_split')
    if len({c.id for c in taxonomy.values()})!=len(taxonomy): raise ConfigError('taxonomy_ids')
    source={(r['file'],r['excel_row']):r for r in rows}
    parts={split:[] for split in SPLITS};counts={group:0 for group in assignment}
    for origin in full_mapping:
        group=origin['group']
        if group not in assignment: continue
        split=origin['split']
        if split!=assignment[group]['split']: raise ConfigError('inherited_split')
        if not origin['representative']: continue
        key=(origin['file_index'],origin['excel_row'])
        if key not in source: raise ConfigError('missing_source_row')
        raw=source[key];target=(raw['file'],raw['label'])
        if target not in taxonomy: raise ConfigError('missing_intent')
        gold=taxonomy[target]
        pool=[(label,c) for (file,label),c in taxonomy.items() if file==raw['file'] and c.id!=gold.id]
        pool.sort(key=lambda pair:(-difflib.SequenceMatcher(None,raw['label'],pair[0]).ratio(),pair[1].id))
        if len(pool)<5: raise ConfigError('candidate_pool')
        origin_id=f"row-{key[0]}-{key[1]}";group_id=f'component-{group}'
        candidates=[gold]+[c for _,c in pool[:4]]
        rng=random.Random(seed^int(hashlib.sha256(origin_id.encode()).hexdigest(),16));rng.shuffle(candidates)
        req=validate_request({'utterance':raw['utterance'],'question':'현재 발화의 의도를 주어진 후보에서 선택하세요.',
                              'context':[{'role':role,'content':content} for role,content in raw['context']],
                              'candidates':[{'id':c.id,'description':c.description} for c in candidates]})
        tags=('context',) if req.context else ()
        e=Example(origin_id+'-positive',origin_id,group_id,group_id,req,gold.id,tags)
        parts[split].append((e,[c for _,c in pool[:5]]));counts[group]+=1
    if any(counts[g]!=assignment[g]['positive_examples'] for g in assignment): raise ConfigError('inherited_counts')
    result={}
    for split,pairs in parts.items():
        positive=[e for e,_ in pairs];required=derived_counts.get(split,0)
        if isinstance(required,bool) or not isinstance(required,int) or not 0<=required<=len(pairs): raise ConfigError('derived_count')
        ordered=sorted(pairs,key=lambda pair:hashlib.sha256((str(seed)+pair[0].example_id).encode()).hexdigest())
        negatives=[]
        for e,candidates in ordered[:required]:
            candidates=list(candidates);random.Random(seed^int(hashlib.sha256(e.example_id.encode()).hexdigest(),16)).shuffle(candidates)
            req=validate_request({'utterance':e.request.utterance,'question':e.request.question,
                                  'context':[{'role':t.role,'content':t.content} for t in e.request.context],
                                  'candidates':[{'id':c.id,'description':c.description} for c in candidates]})
            negatives.append(Example(e.source_id+'-no-answer',e.source_id,e.conversation_id,e.duplicate_group,req,None,e.tags+('no_answer',)))
        result[split]=tuple(positive+negatives)
    if sum(map(len,result.values()))>2000: raise ConfigError('pilot_limit')
    owners={e.example_id:split for split,part in result.items() for e in part}
    for group in connected_groups(tuple(e for part in result.values() for e in part)):
        if len({owners[e.example_id] for e in group})!=1: raise ConfigError('inherited_split')
    manifest={'source':'AI Hub 116','version':'한국어대화_new_260226','terms_link':'https://www.aihub.or.kr/aihubdata/data/view.do?dataSetSn=116',
              'transform_version':'inherited-pilot-v1','seed':seed,'counts':{k:len(v) for k,v in result.items()},
              'group_counts':{k:len({e.conversation_id for e in v}) for k,v in result.items()},
              'file_digests':{k:bundle_digest(v) for k,v in result.items()},
              'checks':{'split_intersection':0,'missing_labels':0,'terms':'approved','pii':'not_checked','tokenizer':'not_checked'},
              'resplit':False}
    return SplitBundle(result,manifest)
