"""승인된 고정 노출 A/B 비교. 원문/가중치는 ignored 로컬에만 보존한다.

준비/실행: python docs/run_ab_comparison.py prepare|run --root ABSOLUTE_ROOT
final-test와 과거 test 혼합 점수파일 접근 차단. 평가 대상은 calibration/selection.
"""
import argparse
from collections import Counter
from copy import deepcopy
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import struct
import sys
import time


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value, *, immutable=False):
    content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if immutable and path.exists():
        if path.read_text(encoding='utf-8') != content:
            raise ValueError('existing_evidence_differs:' + path.name)
    else:
        path.write_text(content, encoding='utf-8')


def bind(c):
    from judgment.contracts import RunConfig
    c['approval']['scope_digest'] = hashlib.sha256(json.dumps(
        {k: v for k, v in c.items() if k != 'approval'}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return RunConfig(c)


def source_paths(root):
    # test 내용/해시는 이번 승인 범위에서 다시 읽지 않는다.
    paths = [root / '.work/data' / (role + ext) for role in ('train', 'calibration', 'selection')
             for ext in ('.examples.json', '.jsonl')]
    paths.append(root / '.work/train_semantic_review/results-v1/selected.proposed.examples.private.json')
    paths.append(root / '.work/train_semantic_review/results-v1/selected.review.private.json')
    return paths


def prepare(root):
    from judgment.contracts import RunConfig
    from judgment.replay import build_replay, validate_replay_schedule, install_final_test_guard
    from judgment.data import normalize_row, bundle_digest
    template = load(root / '.work/data_review/g1-78068da517cd.config.private.json')
    template['experiment'] = {'kind': 'ab_replay_v1'}
    guard = install_final_test_guard(RunConfig(template))
    folder = root / '.work/ab_comparison'
    folder.mkdir(exist_ok=True)
    original_path = root / '.work/data/train.examples.json'
    selected_path = root / '.work/train_semantic_review/results-v1/selected.proposed.examples.private.json'
    original, selected = load(original_path), load(selected_path)
    review = load(root / '.work/train_semantic_review/results-v1/selected.review.private.json')
    if [r['proposed_example'] for r in review] != selected or len(review) != 280:
        raise ValueError('selected_review_binding')
    before = {str(p): sha(p) for p in source_paths(root)}
    mapping = {k: k for k in original[0]}
    summaries = {}
    for arm in ('A', 'B'):
        rows, manifest = build_replay(original, selected, arm=arm, seed=13)
        validate_replay_schedule(original, selected, rows, manifest)
        if manifest['selected_label_changes'] != 49 or manifest['total_exposures'] != 697:
            raise ValueError('approved_replay_scope')
        save(folder / f'{arm}.examples.private.json', rows, immutable=True)
        save(folder / f'{arm}.manifest.private.json', manifest, immutable=True)
        bundle = tuple(normalize_row(r, mapping) for r in rows)
        occurrences = Counter(manifest['occurrences'].values())
        summaries[arm] = dict(exposures=697, unique_examples=manifest['unique_examples'],
                             groups=len({e.conversation_id for e in bundle}),
                             positive=558, no_answer=139, expected_optimizer_updates=88,
                             repetitions={str(k): v for k, v in sorted(occurrences.items())},
                             file_digest=bundle_digest(bundle), manifest_sha256=sha(folder / f'{arm}.manifest.private.json'))
    if before != {str(p): sha(p) for p in source_paths(root)}:
        raise ValueError('source_mutation')
    save(folder / 'sources.before.private.json', before, immutable=True)
    result = {'status': 'replay_prepared_not_trained', 'arms': summaries,
              'source_preserved': True, 'final_test_guard': guard}
    save(folder / 'preparation.private.json', result, immutable=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def arm_config(root, folder, arm, preparation):
    from judgment.runner import _storage_bytes
    from judgment.contracts import RunConfig
    c = deepcopy(load(root / '.work/data_review/g1-78068da517cd.config.private.json'))
    c['code_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    c['split_paths']['train'] = str(folder / f'{arm}.examples.private.json')
    c['data_manifest']['file_digests']['train'] = preparation['arms'][arm]['file_digest']
    if 'group_counts' in c['data_manifest']:
        c['data_manifest']['group_counts']['train'] = preparation['arms'][arm]['groups']
    c['data_manifest']['transform_version'] = 'approved-ab-replay-v1'
    c['approval'].update(experiment='approved_ab_697_88', temporary_gold_changes=49, arm=arm)
    files = {'original': root / '.work/data/train.examples.json',
             'selected': root / '.work/train_semantic_review/results-v1/selected.proposed.examples.private.json',
             'manifest': folder / f'{arm}.manifest.private.json', 'exposures': folder / f'{arm}.examples.private.json'}
    c['experiment'] = {'kind': 'ab_replay_v1', 'arm': arm,
                       'files': {role: {'path': str(path), 'sha256': sha(path)} for role, path in files.items()}}
    c['resources']['estimated_disk_bytes'] = _storage_bytes(RunConfig(c), folder)
    return bind(c)


def diagnostics(rows, *, temperature, labels):
    from judgment.contracts import Policy, ABSTAIN_ID
    from judgment.evaluation import _metrics
    policy = Policy('AB-explicit-only-selection-diagnostic', {5: temperature}, {5: (0., 0.)},
                    'calibration_only', 'not_used_for_policy_selection')
    result = _metrics(rows, policy, labels, 10)
    positive = [r for r in rows if r.example.gold_id is not None]
    absent = [r for r in rows if r.example.gold_id is None]
    ranks, business_right, rank1_abstain, ties = [], 0, 0, 0
    for r in positive:
        ids, scores = r.scores.ids, r.scores.logits
        business = ids[:-1]
        gold_index = ids.index(r.example.gold_id)
        rank = 1 + sum(v > scores[gold_index] for v in scores[:-1])
        ranks.append(rank)
        winner = max(range(6), key=lambda i: scores[i])
        chosen = max(range(5), key=lambda i: scores[i])
        business_right += business[chosen] == r.example.gold_id
        rank1_abstain += rank == 1 and ids[winner] == ABSTAIN_ID
        ties += sum(v == max(scores) for v in scores) > 1
    def abstains(items):
        return sum(r.scores.ids[max(range(len(r.scores.logits)), key=lambda i: r.scores.logits[i])] == ABSTAIN_ID for r in items)
    result['answerable'] = dict(n=len(positive), business5_correct=business_right,
                               business5_accuracy=business_right / len(positive) if positive else None,
                               rank_histogram={str(i): ranks.count(i) for i in range(1, 6)},
                               mean_rank=sum(ranks) / len(ranks) if ranks else None,
                               abstain=abstains(positive), rank1_abstain=rank1_abstain, top1_ties=ties)
    result['no_answer'] = dict(n=len(absent), abstain=abstains(absent))
    result.pop('risk_coverage')
    return result


def measure(root, folder, arm, config, model_dir):
    from judgment.telemetry import Telemetry
    with Telemetry(folder/arm,role='parent',arm=arm) as telemetry:
        return _measure(root,folder,arm,config,model_dir,telemetry)


def _measure(root, folder, arm, config, model_dir,telemetry,*,strict_fp16=False):
    import torch
    from judgment.contracts import SOURCE_COMMIT, ScoredExample, ABSTAIN_ID
    from judgment.data import load_real_bundle
    from judgment.laya_adapter import LayaAdapter
    from judgment.policy import fit_temperatures
    bundle = load_real_bundle(config, roles=('calibration', 'selection'))
    labels = sorted({c.id for role in ('calibration', 'selection') for e in bundle.parts[role]
                     for c in e.request.candidates} | {ABSTAIN_ID})
    expected=fp16_manifest(model_dir/'model.safetensors') if strict_fp16 else None
    with telemetry.phase('measurement_model_load'):
        adapter = LayaAdapter.from_local(model_dir, source_commit=SOURCE_COMMIT,
                                        model_revision=config.values['model_revision'], device='cuda')
    if strict_fp16:
        with telemetry.phase('strict_fp16_reload'):
            live=adapter.backend.model.state_dict()
            if set(live)!=set(expected):raise ValueError('strict_reload_keys')
            for name,tensor in live.items():
                if list(tensor.shape)!=expected[name]['shape']:raise ValueError('strict_reload_shape')
                cpu=tensor.detach().to(device='cpu',dtype=torch.float16).contiguous()
                if hashlib.sha256(memoryview(cpu.numpy()).cast('B')).hexdigest()!=expected[name]['digest']:
                    raise ValueError('strict_reload_value')
                del cpu
            del live
            save(folder/arm/'strict-reload.private.json',dict(tensors=len(expected),stored_dtype='F16',
                 weight_sha256=sha(model_dir/'model.safetensors'),strict_values_verified=True),immutable=True)
    torch.cuda.reset_peak_memory_stats()
    scored = {}
    for role in ('calibration', 'selection'):
        telemetry.event('measurement_'+role,event='enter')
        rows = []
        for i, e in enumerate(bundle.parts[role], 1):
            score = adapter.score(e.request)
            if not all(math.isfinite(v) for v in score.logits):
                raise ValueError('nonfinite_comparison_score')
            rows.append(ScoredExample(e, score, role))
            if i % 100 == 0:
                print(json.dumps({'stage': 'measurement', 'arm': arm, 'role': role, 'completed': i}), flush=True)
        scored[role] = tuple(rows)
        telemetry.event('measurement_'+role,event='exit',position=len(rows))
    temperature = fit_temperatures(scored['calibration'], config=dict(
        temperature_min=.25, temperature_max=4., steps=41, min_samples=50))[5]
    reports = {role: {'raw': diagnostics(scored[role], temperature=1., labels=labels),
                      'calibrated': diagnostics(scored[role], temperature=temperature, labels=labels)}
               for role in ('calibration', 'selection')}
    result = {'arm': arm, 'temperature': temperature, 'reports': reports,
              'labels_scope': 'calibration_and_selection_only', 'label_count': len(labels),
              'quality_status': 'not_decided', 'final_test_opened': False,
              'cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
              'cuda_peak_reserved_bytes': torch.cuda.max_memory_reserved()}
    save(folder / f'{arm}.scores.private.json', {role: [dict(example_id=r.example.example_id,
          ids=r.scores.ids, logits=r.scores.logits) for r in scored[role]] for role in ('calibration', 'selection')}, immutable=True)
    save(folder / f'{arm}.measurement.private.json', result, immutable=True)
    del adapter
    gc.collect(); torch.cuda.empty_cache()
    telemetry.event('measurement_complete')
    return result


def paired_accuracy_interval(root, folder):
    from judgment.contracts import ABSTAIN_ID
    rows = load(root / '.work/data/selection.examples.json')
    scores = {arm: {r['example_id']: r for r in load(folder / f'{arm}.scores.private.json')['selection']}
              for arm in ('A', 'B')}
    by_group = {}
    for e in rows:
        target = e['gold_id'] or ABSTAIN_ID
        delta = []
        for arm in ('A', 'B'):
            r = scores[arm][e['example_id']]
            delta.append(int(r['ids'][max(range(6), key=lambda i: r['logits'][i])] == target))
        by_group.setdefault(e['conversation_id'], []).append(delta[1] - delta[0])
    keys = sorted(by_group)
    rng = random.Random(13)
    samples = []
    for _ in range(100):
        values = [d for key in rng.choices(keys, k=len(keys)) for d in by_group[key]]
        samples.append(sum(values) / len(values))
    from judgment.evaluation import _quantile
    return dict(unit='existing_selection_connection_group', groups=len(keys), repeats=100, seed=13,
                confidence_level=.95, delta_B_minus_A_interval=[_quantile(samples, .025), _quantile(samples, .975)])


PREPARED_FILES=('A.examples.private.json','B.examples.private.json','A.manifest.private.json','B.manifest.private.json',
                'preparation.private.json','sources.before.private.json')


def new_trial(root,trial_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',trial_id): raise ValueError('invalid_trial_id')
    folder=root/'.work/ab_trials'/trial_id
    folder.mkdir(parents=True,exist_ok=False)
    for name in PREPARED_FILES:
        source=root/'.work/ab_comparison'/name
        target=folder/name
        shutil.copyfile(source,target)
        if sha(source)!=sha(target): raise ValueError('trial_preparation_copy')
    return folder


def fp16_manifest(path):
    import array
    result={};spans=[]
    with Path(path).open('rb') as stream:
        n=struct.unpack('<Q',stream.read(8))[0];header=json.loads(stream.read(n));base=8+n
        payload=Path(path).stat().st_size-base
        for name,item in header.items():
            if name=='__metadata__':continue
            a,b=item['data_offsets'];shape=item['shape']
            if item['dtype']!='F16' or not 0<=a<=b<=payload or b-a!=math.prod(shape)*2:
                raise ValueError('checkpoint_structure')
            spans.append((a,b));stream.seek(base+a);left=b-a;digest=hashlib.sha256()
            while left:
                data=stream.read(min(left,4*1024**2))
                if not data:raise ValueError('checkpoint_structure')
                left-=len(data);digest.update(data)
                try:
                    import numpy as np
                    bits=np.frombuffer(data,dtype='<u2');bad=bool(np.any((bits&0x7c00)==0x7c00))
                except ImportError:
                    bits=array.array('H');bits.frombytes(data)
                    if sys.byteorder!='little':bits.byteswap()
                    bad=any((v&0x7c00)==0x7c00 for v in bits)
                if bad:raise ValueError('checkpoint_nonfinite')
            result[name]=dict(shape=shape,digest=digest.hexdigest())
        spans.sort()
        if not spans or spans[0][0]!=0 or spans[-1][1]!=payload or any(x[1]!=y[0] for x,y in zip(spans,spans[1:])):
            raise ValueError('checkpoint_structure')
    return result


def followup_remaining(start,now):
    remaining=1230.-(now-start)
    if remaining<=0:raise ValueError('followup_time_limit')
    return remaining


def stored_measure(root,trial_id,arm,model_dir):
    from judgment.contracts import RunConfig
    from judgment.runner import preflight,_worker_limits
    from judgment.replay import install_final_test_guard
    from judgment.telemetry import Telemetry
    folder=root/'.work/ab_trials'/trial_id;c=RunConfig(load(folder/arm/'evaluation.config.private.json'))
    install_final_test_guard(c);preflight(c)
    if str(model_dir)!=c.values['evaluation_model_dir'] or sha(model_dir/'model.safetensors')!=c.values['evaluation_model_sha256']:
        raise ValueError('evaluation_model_binding')
    with Telemetry(folder/arm,role='worker',arm=arm) as telemetry,_worker_limits(c,folder/arm):
        measured=_measure(root,folder,arm,c,model_dir,telemetry,strict_fp16=True)
        save(folder/arm/'summary.json',dict(status='stored_model_measured',trained=False,optimizer_updates_observed=0,
                                          measurement=measured,final_test_opened=False))


def measure_in_worker(root,folder,arm,config,model_dir):
    from judgment.runner import worker_invocation,_training_process
    from judgment.telemetry import Telemetry
    values=deepcopy(config.values);values.update(evaluation_model_dir=str(model_dir),evaluation_model_sha256=sha(model_dir/'model.safetensors'))
    config=bind(values);save(folder/arm/'evaluation.config.private.json',values,immutable=True)
    _,env,cwd=worker_invocation(config,folder/arm)
    command=[sys.executable,str(root/'docs/run_ab_comparison.py'),'stored-measure','--root',str(root),
             '--trial-id',folder.name,'--arm',arm,'--model-dir',str(model_dir)]
    with Telemetry(folder/arm,role='parent',arm=arm,preserve_output=True) as telemetry:
        result=_training_process(config,folder/arm,command,env,None,telemetry,cwd=cwd).values
    save(folder/(arm+'.evaluation-worker.private.json'),result,immutable=True)
    if result.get('worker_returncode')!=0 or result.get('status')!='stored_model_measured':raise ValueError('stored_evaluation_failed')
    return load(folder/(arm+'.measurement.private.json'))


def followup(root,trial_id,a_run):
    from judgment.runner import _worker_limits,run_training
    from judgment.replay import install_final_test_guard
    from judgment.data import load_real_bundle
    started=time.monotonic();folder=new_trial(root,trial_id);preparation=load(folder/'preparation.private.json')
    config=arm_config(root,folder,'A',preparation);install_final_test_guard(config)
    initial=Path(config.values['model_dir']);initial_sha=sha(initial/'model.safetensors')
    if initial_sha!='9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204':raise ValueError('initial_weight_changed')
    checkpoint=a_run/'output/checkpoint_latest'
    if sha(checkpoint/'model.safetensors')!='ecb8e425645ad42755841e9d960f0c03e9ea361a1bb960912d2c8d8a0b2f1339':raise ValueError('A_checkpoint_changed')
    original_cfg=load(a_run/'config.json')
    if original_cfg['training']!=config.values['training'] or original_cfg['model_revision']!=config.values['model_revision']:
        raise ValueError('A_training_config_mismatch')
    events=[json.loads(line) for line in (a_run/'worker.events.private.jsonl').read_text().splitlines()]
    if sum(x.get('stage')=='optimizer_step' and x.get('event')=='exit' for x in events)!=88 or not any(x.get('stage')=='train_model' and x.get('event')=='exit' and x.get('completed_optimizer_updates')==88 for x in events):
        raise ValueError('A_completion_evidence')
    values=deepcopy(config.values);values['resources']['time_limit_seconds']=followup_remaining(started,time.monotonic());global_config=bind(values)
    with _worker_limits(global_config,folder) as global_resources:
        for arm in ('A','B'):
            (folder/arm).mkdir()
            values=deepcopy(arm_config(root,folder,arm,preparation).values)
            values['resources']['time_limit_seconds']=followup_remaining(started,time.monotonic());config=bind(values)
            samples=wait_start_samples(values['resources']['gpu_memory_snapshot_path'],timeout=min(30.,followup_remaining(started,time.monotonic())))
            save(folder/arm/'start-headroom.private.json',dict(limit_bytes=int(2.75*1024**3),samples=samples),immutable=True)
            if arm=='A':
                source=fp16_manifest(initial/'model.safetensors');saved=fp16_manifest(checkpoint/'model.safetensors')
                if set(source)!=set(saved) or any(source[k]['shape']!=saved[k]['shape'] for k in source):raise ValueError('A_shape_mismatch')
                if any(source[k]['digest']!=saved[k]['digest'] for k in source if k.startswith('encoder.')):raise ValueError('A_encoder_changed')
                model_dir=folder/'A/restored_checkpoint';shutil.copytree(checkpoint,model_dir)
                provenance=load(initial/'judgment_provenance.json');provenance.update(trained_artifact_sha256=sha(model_dir/'model.safetensors'),
                    derived_from_epoch_checkpoint=str(checkpoint),completed_optimizer_updates=88,source_training_code_revision=original_cfg['code_revision'])
                save(model_dir/'judgment_provenance.json',provenance)
                save(folder/'A.training.private.json',dict(status='recovered_epoch_checkpoint',optimizer_updates_observed=88,
                     new_optimizer_updates=0,initial_weight_sha256=initial_sha,checkpoint_sha256=sha(model_dir/'model.safetensors')),immutable=True)
            else:
                if followup_remaining(started,time.monotonic())<600:raise ValueError('insufficient_time_for_B')
                if sha(initial/'model.safetensors')!=initial_sha:raise ValueError('initial_weight_changed')
                trained=run_training(config,load_real_bundle(config,roles=('train','selection'))).values
                save(folder/'B.training.private.json',trained,immutable=True)
                if not trained.get('trained') or trained.get('optimizer_updates_observed')!=88:raise ValueError('B_training_failed')
                model_dir=Path(trained['run_dir'])/'output'
            values=deepcopy(config.values);values['resources']['time_limit_seconds']=followup_remaining(started,time.monotonic());config=bind(values)
            measured=measure_in_worker(root,folder,arm,config,model_dir)
            save(folder/(arm+'.result.private.json'),dict(measurement=measured),immutable=True)
            from judgment.runner import _ACTIVE_WORKERS
            if _ACTIVE_WORKERS:raise ValueError('resources_not_released')
            torch=sys.modules.get('torch')
            initialized=bool(torch is not None and torch.cuda.is_initialized())
            if initialized:gc.collect();torch.cuda.empty_cache()
            allocated=torch.cuda.memory_allocated() if initialized else 0
            reserved=torch.cuda.memory_reserved() if initialized else 0
            if allocated or reserved:raise ValueError('resources_not_released')
            # 평가 child가 정상 종료돼 GPU context가 해제된 후 다음 arm의 새 표본을 검사한다.
            save(folder/arm/'released.private.json',dict(active_workers=0,measurement_worker_exited=True,
                 parent_gpu_initialized=initialized,allocated_bytes=allocated,reserved_bytes=reserved),immutable=True)
            print(json.dumps(dict(stage='arm_complete',arm=arm,elapsed_seconds=time.monotonic()-started)),flush=True)
        if sha(initial/'model.safetensors')!=initial_sha or load(folder/'sources.before.private.json')!={str(p):sha(p) for p in source_paths(root)}:
            raise ValueError('original_or_initial_weights_changed')
        summary=dict(status='ab_saved_fp16_comparison_complete',interpretation='combined_selection_label_change_repetition_effect',
          A_retrained=False,storage_comparison='both_fp16_saved_and_strict_reloaded',paired_selection_accuracy_delta=paired_accuracy_interval(root,folder),
          final_test_opened=False,source_preserved=True,elapsed_seconds=time.monotonic()-started,followup_limit_seconds=1230,global_resources=global_resources)
        followup_remaining(started,time.monotonic());save(folder/'summary.private.json',summary,immutable=True)


def wait_start_samples(snapshot, *, timeout=30., limit=int(2.75*1024**3)):
    from judgment.gpu_snapshot import validate_gpu_snapshot,read_gpu_value
    started=time.time();deadline=time.monotonic()+timeout;last=None;rows=[]
    while time.monotonic()<deadline:
        value=read_gpu_value(Path(snapshot));validate_gpu_snapshot(value)
        stamp=value['sampled_epoch']
        if stamp>=started and stamp!=last:
            last=stamp
            rows=rows+[value] if value['bytes_used']<=limit else []
            if len(rows)==3:return rows
        time.sleep(.2)
    raise ValueError('start_headroom_unavailable')


def precheck(root):
    from judgment.runner import run_training,_worker_limits
    from judgment.data import load_real_bundle
    from judgment.replay import install_final_test_guard
    folder=root/'.work/ab_comparison'
    config=arm_config(root,folder,'A',load(folder/'preparation.private.json'))
    install_final_test_guard(config)
    samples=wait_start_samples(config.values['resources']['gpu_memory_snapshot_path'])
    with _worker_limits(config,folder):
        result=run_training(config,load_real_bundle(config,roles=('train','selection')),precheck_only=True).values
    if result.get('status')!='worker_precheck_verified' or result.get('worker_returncode')!=0:
        raise ValueError('worker_precheck_failed')
    save(folder/'worker-precheck.latest.private.json',dict(result,start_samples=samples))
    print(json.dumps({'stage':'worker_precheck_complete','runtime':result['runtime'],'run_dir':result['run_dir'],
                      'optimizer_updates':0,'final_test_opened':False}),flush=True)


def run(root,*,trial_id=None):
    from judgment.contracts import RunConfig
    from judgment.replay import install_final_test_guard, validate_replay_files, remaining_trial_seconds
    from judgment.runner import preflight, run_training, _worker_limits, final_storage_check
    from judgment.data import load_real_bundle
    from judgment.telemetry import gpu_baseline
    overall_start = time.monotonic()
    folder = new_trial(root,trial_id) if trial_id else root / '.work/ab_comparison'
    preparation = load(folder / 'preparation.private.json')
    before = load(folder / 'sources.before.private.json')
    if before != {str(p): sha(p) for p in source_paths(root)}:
        raise ValueError('prepared_sources_changed')
    if any((folder / f'{arm}.training.private.json').exists() for arm in ('A', 'B')):
        raise ValueError('no_automatic_training_rerun')
    template = load(root / '.work/data_review/g1-78068da517cd.config.private.json')
    template['experiment'] = {'kind': 'ab_replay_v1'}
    guard = install_final_test_guard(RunConfig(template))
    initial_weight = Path(template['model_dir']) / 'model.safetensors'
    initial_sha = sha(initial_weight)
    arms = {}
    global_values = deepcopy(arm_config(root, folder, 'A', preparation).values)
    global_values['resources']['time_limit_seconds'] = remaining_trial_seconds(overall_start, time.monotonic())
    global_config = bind(global_values)
    snapshot=global_values['resources'].get('gpu_memory_snapshot_path')
    if snapshot: gpu_baseline(snapshot,folder/'gpu.before-trial.private.json',limit=global_values['resources']['vram_limit_bytes'])
    with _worker_limits(global_config, folder) as global_resources:
        for arm in ('A', 'B'):
            arm_folder = folder / arm
            arm_folder.mkdir(exist_ok=False)
            values = deepcopy(arm_config(root, folder, arm, preparation).values)
            values['resources']['time_limit_seconds'] = remaining_trial_seconds(overall_start, time.monotonic())
            config = bind(values)
            if arm=='B':
                import torch
                gc.collect();torch.cuda.empty_cache()
                release=dict(allocated_bytes=torch.cuda.memory_allocated(),reserved_bytes=torch.cuda.memory_reserved(),
                             active_training_workers=len(__import__('judgment.runner',fromlist=['_ACTIVE_WORKERS'])._ACTIVE_WORKERS))
                save(folder/'A.release.private.json',release,immutable=True)
                if release['allocated_bytes'] or release['reserved_bytes'] or release['active_training_workers']:
                    raise ValueError('A_resources_not_released')
            samples=wait_start_samples(snapshot,timeout=min(30.,remaining_trial_seconds(overall_start,time.monotonic())))
            save(arm_folder/'start-headroom.private.json',dict(limit_bytes=int(2.75*1024**3),samples=samples),immutable=True)
            preflight(config)
            verified = validate_replay_files(config)
            if sha(initial_weight) != initial_sha:
                raise ValueError('initial_weight_changed')
            save(arm_folder / 'approved.config.private.json', config.values, immutable=True)
            print(json.dumps({'stage': 'training', 'arm': arm, **verified}, ensure_ascii=False), flush=True)
            arm_start = time.monotonic()
            with _worker_limits(config, arm_folder) as resources:
                trained = run_training(config, load_real_bundle(config, roles=('train', 'selection'))).values
                save(folder / f'{arm}.training.private.json', trained, immutable=True)
                if not trained.get('trained') or trained.get('optimizer_updates_observed') != 88:
                    save(folder / 'failure.private.json', dict(arm=arm, training=trained, final_test_guard=guard))
                    raise ValueError('ab_training_not_verified')
                measurement = measure(root, folder, arm, config, Path(trained['run_dir']) / 'output')
                disk = final_storage_check(config, arm_folder)
                arms[arm] = dict(training=trained, measurement=measurement, resources=resources,
                                 elapsed_seconds=time.monotonic()-arm_start, disk_bytes_observed=disk,
                                 initial_weight_sha256=initial_sha)
            save(folder / f'{arm}.result.private.json', arms[arm], immutable=True)
            print(json.dumps({'stage': 'arm_complete', 'arm': arm, 'optimizer': 88,
                              'elapsed_seconds': arms[arm]['elapsed_seconds']}), flush=True)
        if arms['A']['training']['before'] != arms['B']['training']['before']:
            raise ValueError('initial_tensor_mismatch')
        if before != {str(p): sha(p) for p in source_paths(root)} or sha(initial_weight) != initial_sha:
            raise ValueError('original_or_initial_weights_changed')
        summary = {'status': 'ab_comparison_complete', 'interpretation': 'combined_selection_label_change_repetition_effect',
                   'arms': arms, 'paired_selection_accuracy_delta': paired_accuracy_interval(root, folder),
                   'source_preserved': True, 'final_test_guard': guard, 'final_test_opened': False,
                   'elapsed_seconds': time.monotonic()-overall_start, 'quality_status': 'not_decided',
                   'global_time_limit_seconds': 1800, 'global_resources': global_resources}
        remaining_trial_seconds(overall_start, time.monotonic())
        save(folder / 'summary.private.json', summary, immutable=True)
    print(json.dumps({'stage': 'complete', 'source_preserved': True, 'final_test_opened': False,
                      'elapsed_seconds': summary['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'precheck', 'run','stored-measure','followup'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--trial-id',help='별도로 승인한 단일 재시도의 새 보존 이름; 기존 증거 재사용/덮어쓰기 금지')
    parser.add_argument('--arm',choices=('A','B'))
    parser.add_argument('--model-dir',type=Path)
    parser.add_argument('--a-run',type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    os.chdir(root)
    sys.path.insert(0, str(root / 'src'))
    if args.command=='prepare':
        if args.trial_id: parser.error('trial-id is for approved run only')
        prepare(root)
    elif args.command=='precheck':
        if args.trial_id:parser.error('trial-id is for approved run only')
        precheck(root)
    elif args.command=='stored-measure':
        if not args.trial_id or not args.arm or not args.model_dir:parser.error('stored-measure requires trial-id/arm/model-dir')
        stored_measure(root,args.trial_id,args.arm,args.model_dir)
    elif args.command=='followup':
        if not args.trial_id or not args.a_run:parser.error('followup requires trial-id/a-run')
        followup(root,args.trial_id,args.a_run)
    else: run(root,trial_id=args.trial_id)
