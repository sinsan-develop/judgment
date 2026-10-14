"""다운로드 없는 preflight·fixture와 G1 승인 후의 bounded Native 실행."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import threading
from contextlib import contextmanager, nullcontext
from .contracts import RunConfig, RunEvidence, Report, ConfigError, validate_run_config
from .data import to_laya_row, connected_groups, bundle_digest
from .telemetry import bounded_save, stop_evidence, Telemetry, current_telemetry, drain_output, gpu_baseline, observe_upstream_stages

_ACTIVE_WORKERS=[]  # 이 process가 시작한 학습 worker만 중단한다.
_GPU_OBSERVATIONS=threading.local()


def _resource_trigger(c,ram,vram,disk,elapsed):
    return dict(decision_epoch=time.time(),decision_monotonic=time.monotonic(),ram_bytes=ram,
        gpu_upper_bound_bytes=vram,disk_bytes=disk,elapsed_seconds=elapsed,
        limits={k:c['resources'][k] for k in ('time_limit_seconds','ram_limit_bytes','disk_limit_bytes','vram_limit_bytes') if k in c['resources']},
        gpu_snapshot=getattr(_GPU_OBSERVATIONS,'snapshot',None))


def _stop_owned(run_dir,observations,reason,trigger=None):
    # 진단 write/read/fsync가 멈추거나 예외여도 종료 경로는 반드시 실행한다.
    try:
        current=current_telemetry()
        progress_folder=current.folder if current is not None else run_dir
        bounded_save(run_dir/'limit_failure.json',lambda:stop_evidence(progress_folder,dict(observations,reason=reason,trigger=trigger)))
    finally:
        for child in tuple(_ACTIVE_WORKERS):
            try:
                if child.poll() is None:
                    try: child.terminate()
                    finally: child.kill()
            except OSError: pass
        os._exit(3)


def resource_budget(resources, *, free_bytes):
    # baseline 캐시/데이터 예상량 + upstream latest와 최종본의 동시 점유.
    required = resources['estimated_disk_bytes'] + 2*resources['checkpoint_bytes']
    if required > resources['disk_limit_bytes'] or required > free_bytes: raise ConfigError('disk_budget')
    return required


def final_resource_check(resources, *, artifact_bytes):
    if artifact_bytes+resources['estimated_disk_bytes'] > resources['disk_limit_bytes']: raise ConfigError('disk_limit')


def preflight(config):
    if config.values.get('mode') == 'fixture':
        return Report({'mode':'fixture','training_allowed':False,'download_allowed':False,'gate':'G1_required',
                       'python':sys.version.split()[0], 'status':'offline_fixture_ready'})
    c = validate_run_config(config.values, real=True).values
    bound = {k:v for k,v in c.items() if k != 'approval'}
    digest = hashlib.sha256(json.dumps(bound,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if c['approval'].get('scope_digest') != digest: raise ConfigError('approval_scope_mismatch')
    snapshot = c.get('resources',{}).get('gpu_memory_snapshot_path')
    if os.environ.get('JUDGMENT_GPU_MEMORY_SNAPSHOT') != snapshot:
        raise ConfigError('vram_monitor_binding')
    if Path(c['canonical_checkout']).resolve() != Path.cwd().resolve(): raise ConfigError('canonical_checkout')
    try:
        head = subprocess.check_output(['git','rev-parse','HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError): raise ConfigError('code_revision') from None
    if c['code_revision'] != head: raise ConfigError('code_revision')
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True,stderr=subprocess.DEVNULL)
    if dirty.strip(): raise ConfigError('dirty_checkout')
    loaded_source = Path(os.path.abspath(__file__))
    expected_source = Path(os.path.abspath(c['canonical_checkout']))/'src'/'judgment'/'runner.py'
    if loaded_source != expected_source: raise ConfigError('noncanonical_import')
    model_dir, work_dir = Path(c['model_dir']).resolve(), Path(c['work_dir']).resolve()
    if not model_dir.is_dir() or not work_dir.is_dir(): raise ConfigError('missing_local_resource')
    if work_dir == model_dir or model_dir in work_dir.parents or work_dir in model_dir.parents: raise ConfigError('storage_overlap')
    if len(set(str(Path(p).resolve()) for p in c['split_paths'].values())) != 4: raise ConfigError('split_overlap')
    required = resource_budget(c['resources'],free_bytes=shutil.disk_usage(work_dir).free)
    manifest = c['data_manifest']
    if not isinstance(manifest,dict) or any(not manifest.get(k) for k in ('source','version','terms_link','transform_version','checks','file_digests')):
        raise ConfigError('data_manifest')
    checks = manifest['checks']
    if checks.get('split_intersection') != 0 or checks.get('pii') != 'passed' or checks.get('terms') != 'approved' or checks.get('missing_labels') != 0:
        raise ConfigError('data_checks')
    # 실제 AMP dtype는 upstream 자동 선택이므로 G1의 확인값과 일치하기 전 허용하지 않는다.
    if c['training']['precision'] != 'fp32': raise ConfigError('precision_requires_real_adapter_verification')
    return Report({'mode':'real','training_allowed':True,'download_allowed':False,'required_disk_bytes':required,
                   'gate':'G1_scope_matched','python':sys.version.split()[0]})


def training_arguments(config, train_path, selection_path, output_dir):
    c = config.values; t = c['training']
    return {'data':str(train_path),'output_dir':str(output_dir),'device':c['device'],
            'config':{'epochs':t['epochs'],'micro_batch':t['micro_batch'],'grad_accum':t['grad_accum'],
                      'encoder_lr':t['encoder_lr'],'head_lr':t['head_lr'],'freeze_encoder':t['freeze_encoder'],
                      'amp':t['precision'] != 'fp32','seed':c['seed'],'loss':'soft-ce','shuffle_options':('choice',),
                      'calib_frac':0,'calib_max':0,'eval_data':str(selection_path)}}


def training_rows(splits):
    # calibration/test의 파일이나 행을 열지 않는다.
    train, selection = splits.parts['train'], splits.parts['selection']
    groups = connected_groups(tuple(train)+tuple(selection))
    train_ids = {e.example_id for e in train}
    for group in groups:
        if any(e.example_id in train_ids for e in group) and any(e.example_id not in train_ids for e in group): raise ConfigError('split_overlap')
    return tuple(to_laya_row(e) for e in train), tuple(to_laya_row(e) for e in selection)


def assess_weight_change(before, after):
    if set(before) != set(after) or any(before[k]['shape'] != after[k]['shape'] for k in before): raise ConfigError('tensor_structure_changed')
    changed = sum(before[k]['digest'] != after[k]['digest'] for k in before)
    return {'trained':changed > 0,'changed_tensors':changed,'parameter_count':sum(v['numel'] for v in before.values()),
            'before':before,'after':after}


@contextmanager
def observe_optimizer_steps(telemetry=None):
    from torch.optim.optimizer import register_optimizer_step_post_hook, register_optimizer_step_pre_hook
    observed={'count':0,'by_optimizer':{}}
    def on_step(optimizer,args,kwargs):
        name=type(optimizer).__name__;observed['count']+=1
        observed['by_optimizer'][name]=observed['by_optimizer'].get(name,0)+1
        if telemetry is not None and name=='AdamW': telemetry.optimizer_complete()
    def before_step(optimizer,args,kwargs):
        if telemetry is not None and type(optimizer).__name__=='AdamW': telemetry.optimizer_start()
    handle=register_optimizer_step_post_hook(on_step)
    pre_handle=register_optimizer_step_pre_hook(before_step) if telemetry is not None else None
    try: yield observed
    finally:
        handle.remove()
        if pre_handle is not None: pre_handle.remove()


def completed_training_evidence(change,*,optimizer_updates,reload_verified,encoder_changed):
    trained=bool(change['trained'] and optimizer_updates>0 and reload_verified and encoder_changed==0)
    return dict(change,trained=trained,weight_changed=bool(change['trained']),reload_verified=reload_verified,
                encoder_changed_tensors=encoder_changed,optimizer_updates_observed=optimizer_updates,
                optimizer_updates_status='observed',status='trained_pipeline_verified' if trained else 'incomplete_training_evidence')


def training_jsonl_digest(path):
    canonical='\n'.join(json.dumps(json.loads(line),sort_keys=True,ensure_ascii=False)
                        for line in path.read_text(encoding='utf-8').splitlines())
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_upstream_execution(config,summary,*,observed_steps=None):
    import math
    counts=config.values['data_manifest']['counts'];t=config.values['training']
    selection=summary.get('eval_items',summary.get('eval_valid_items'))
    if summary.get('train_items')!=counts['train'] or selection!=counts['selection'] or summary.get('calibration_items')!=0 or summary.get('skipped') or summary.get('eval_skipped'):
        raise ConfigError('upstream_item_mismatch')
    expected=math.ceil(math.ceil(counts['train']/t['micro_batch'])/t['grad_accum'])*t['epochs']
    if observed_steps is not None and observed_steps!=expected: raise ConfigError('optimizer_count_mismatch')
    return expected


def _tensor_manifest(path):
    from safetensors import safe_open
    result = {}
    with safe_open(str(path),framework='pt',device='cpu') as file:
        for name in file.keys():
            tensor = file.get_tensor(name)
            digest = hashlib.sha256(tensor.contiguous().view(-1).view(__import__('torch').uint8).numpy().tobytes()).hexdigest()
            result[name] = {'shape':list(tensor.shape),'digest':digest,'numel':tensor.numel()}
    return result


def _memory(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)] + [(n,ctypes.c_size_t) for n in
                      ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        api = ctypes.WinDLL('kernel32',use_last_error=True)
        api.OpenProcess.restype = wintypes.HANDLE
        api.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        memory_api = ctypes.WinDLL('psapi')
        memory_api.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        memory_api.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = api.OpenProcess(0x1000|0x10,False,pid)
        if not handle: raise ConfigError('memory_monitor_unavailable')
        try:
            c = Counters(); c.cb = ctypes.sizeof(c)
            ok = memory_api.GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb)
            if not ok: raise ConfigError('memory_monitor_unavailable')
            return c.WorkingSetSize
        finally: api.CloseHandle(handle)
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'): return int(line.split()[1])*1024
    except OSError: raise ConfigError('memory_monitor_unavailable') from None
    raise ConfigError('memory_monitor_unavailable')


def _gpu_memory(pid):
    _GPU_OBSERVATIONS.snapshot=None
    snapshot = os.environ.get('JUDGMENT_GPU_MEMORY_SNAPSHOT')
    if snapshot:
        from .gpu_snapshot import read_gpu_snapshot
        observation={}
        value=read_gpu_snapshot(snapshot,observation=observation)
        _GPU_OBSERVATIONS.snapshot=observation or None
        return value
    try:
        if os.name == 'nt':
            # WDDM은 process memory를 N/A로 반환한다. 전체 device 합계는
            # 해당 실행 점유의 보수적 상한이며 다른 process 사용도 포함한다.
            out = subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,stderr=subprocess.DEVNULL,timeout=5)
            values=[int(line.strip()) for line in out.splitlines() if line.strip()]
            if not values or any(v<0 for v in values): raise ValueError('unavailable_total')
            return sum(values)*1024*1024
        out = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True,stderr=subprocess.DEVNULL,timeout=5)
        total = 0
        for line in out.splitlines():
            parts = line.split(',')
            if parts[0].strip() == str(pid): total += int(parts[1].strip())*1024*1024
        return total
    except (OSError, ValueError, subprocess.SubprocessError): raise ConfigError('vram_monitor_unavailable') from None


def _storage_bytes(config,run_dir):
    c=config.values
    if c.get('canonical_checkout'):
        root=Path(c['canonical_checkout']);paths=(root/'.work').rglob('*')
        archive=root/'docs'/'한국어대화_new_260226.zip'
        total=(archive.stat().st_size if archive.is_file() else 0)+c['resources'].get('shared_runtime_image_bytes',0)
    else:
        paths=run_dir.rglob('*');total=c['resources']['estimated_disk_bytes']
    for path in paths:
        try:
            if path.is_file(): total+=path.stat().st_size
        except FileNotFoundError: pass  # 임시 파일 rename과 감시 사이의 경합.
    return total


def final_storage_check(config,run_dir):
    measured=_storage_bytes(config,run_dir)
    if measured>config.values['resources']['disk_limit_bytes']: raise ConfigError('disk_limit')
    return measured


def run_training(config, splits):
    if config.values.get('mode') == 'fixture':
        train, selection = training_rows(splits)
        return RunEvidence({'status':'fixture_only','trained':False,'optimizer_called':False,
                            'train_rows':len(train),'selection_rows':len(selection),'data_kind':'synthetic',
                            'quality_status':'not_decided','gate':'G1_required'})
    preflight(config)
    from .replay import validate_replay_files
    replay_verified = validate_replay_files(config)
    c = config.values
    train, selection = training_rows(splits)
    for role in ('train','selection'):
        if bundle_digest(splits.parts[role]) != c['data_manifest']['file_digests'].get(role): raise ConfigError('data_digest_mismatch')
    run_dir = Path(c['work_dir']) / ('run-'+uuid.uuid4().hex)
    run_dir.mkdir()  # 기존 사용자 산출물을 덮어쓰지 않는 단일 실행 폴더.
    for role,rows in (('train',train),('selection',selection)):
        (run_dir/(role+'.jsonl')).write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
    (run_dir/'config.json').write_text(json.dumps(c,ensure_ascii=False),encoding='utf-8')
    cmd = [sys.executable,'-m','judgment','_train-worker','--config',str(run_dir/'config.json')]
    env = dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',
               PYTHONPATH=str(Path(c['canonical_checkout'])/'src'))
    snapshot=c['resources'].get('gpu_memory_snapshot_path')
    if snapshot: gpu_baseline(snapshot,run_dir/'gpu.before-worker.private.json')
    with Telemetry(run_dir,role='parent',arm=c.get('experiment',{}).get('arm')) as telemetry:
        return _training_process(config,run_dir,cmd,env,replay_verified,telemetry)


def _training_process(config,run_dir,cmd,env,replay_verified,telemetry):
    c=config.values
    start = time.monotonic(); peak_ram = peak_vram = 0; failure = None;trigger=None
    telemetry.event('worker_launch',event='enter')
    proc = subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    _ACTIVE_WORKERS.append(proc)
    drains=[drain_output(proc.stdout,telemetry,'stdout'),drain_output(proc.stderr,telemetry,'stderr')]
    try:
        while proc.poll() is None:
            ram = _memory(proc.pid)+_memory(os.getpid()); vram = _gpu_memory(proc.pid) if c['device'] == 'cuda' else 0
            peak_ram,peak_vram = max(peak_ram,ram),max(peak_vram,vram)
            disk = _storage_bytes(config,run_dir)
            trigger=_resource_trigger(c,ram,vram,disk,time.monotonic()-start)
            if time.monotonic()-start > c['resources']['time_limit_seconds']: failure = 'time_limit'
            elif ram > c['resources']['ram_limit_bytes']: failure = 'ram_limit'
            elif vram > c['resources'].get('vram_limit_bytes',float('inf')): failure = 'vram_limit'
            elif disk > c['resources']['disk_limit_bytes']: failure = 'disk_limit'
            elif telemetry.failed.is_set(): failure='telemetry_unavailable'
            if failure: break
            telemetry.event('worker_running',event='heartbeat')
            time.sleep(.2)
    except ConfigError as e:
        if proc.poll() is None: failure = e.code
    finally:
        try:
            if failure:
                bounded_save(run_dir/'limit_failure.json',lambda:stop_evidence(run_dir,dict(reason=failure,
                    peak_ram_bytes=peak_ram,peak_vram_upper_bound_bytes=peak_vram,elapsed_seconds=time.monotonic()-start,trigger=trigger)))
        finally:
            if proc.poll() is None:
                try: proc.terminate()
                finally:
                    if failure: proc.kill()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        _ACTIVE_WORKERS.remove(proc)
        for thread in drains: thread.join(.1)
    summary_path = run_dir/'summary.json'
    try:
        final_resource_check(c['resources'],artifact_bytes=sum(p.stat().st_size for p in run_dir.rglob('*') if p.is_file()))
        final_storage_check(config,run_dir)
    except ConfigError as e: failure = e.code
    result = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else {'trained':False}
    if failure or proc.returncode != 0: result = dict(result,trained=False,status='failed',reason=failure or result.get('reason','worker_failed'))
    result.update(peak_ram_bytes=peak_ram,peak_vram_bytes=peak_vram,elapsed_seconds=time.monotonic()-start,
                  code_revision=c['code_revision'],source_commit=c['source_commit'],model_revision=c['model_revision'],seed=c['seed'],
                  training_scope='head_only' if c['training']['freeze_encoder'] else 'encoder_and_head',
                  optimizer_updates_observed=result.get('optimizer_updates_observed'),
                  optimizer_updates_status='observed' if result.get('optimizer_updates_observed') is not None else 'unverified',memory_scope='sampled_peak',
                  vram_scope='host_all_gpu_adapter_upper_bound' if os.environ.get('JUDGMENT_GPU_MEMORY_SNAPSHOT') else 'device_total_upper_bound' if os.name=='nt' else 'process',cleanup='retained_local_only_pending_review')
    result.update(run_dir=str(run_dir),peak_ram_scope='parent_and_training_worker',disk_bytes_observed=_storage_bytes(config,run_dir))
    if replay_verified is not None: result['replay_verified'] = replay_verified
    (run_dir/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    try: result['disk_bytes_observed']=final_storage_check(config,run_dir)
    except ConfigError as e:
        result.update(trained=False,status='failed',reason=e.code)
        (run_dir/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return RunEvidence(result)


def training_worker(config_path):
    c = RunConfig(json.loads(config_path.read_text(encoding='utf-8')))
    root=c.values.get('canonical_checkout')
    allowed=root and config_path.parent.resolve().is_relative_to((Path(root)/'.work').resolve())
    recorder=Telemetry(config_path.parent,role='worker',arm=c.values.get('experiment',{}).get('arm')) if allowed else nullcontext(None)
    with recorder as telemetry:
        try: return _training_worker(config_path,c,telemetry)
        except BaseException as error:
            if telemetry:
                try: telemetry.event(None,event='failed',error_type=type(error).__name__)
                except ConfigError: pass
            raise


def _training_worker(config_path,c,telemetry):
    from .laya_adapter import LayaAdapter, offline
    phase=telemetry.phase if telemetry is not None else lambda stage:nullcontext()
    from .replay import install_final_test_guard, validate_replay_files
    final_test_guard = install_final_test_guard(c)
    with phase('worker_preflight'): preflight(c)
    c = validate_run_config(c.values,real=True)
    v = c.values; run_dir = config_path.parent
    replay_verified = validate_replay_files(c, training_jsonl=run_dir/'train.jsonl')
    for role in ('train','selection'):
        if training_jsonl_digest(run_dir/(role+'.jsonl'))!=v['data_manifest']['file_digests'].get(role):
            raise ConfigError('data_digest_mismatch')
    with _worker_limits(c,run_dir), offline():
        with phase('model_load'):
            adapter = LayaAdapter.from_local(Path(v['model_dir']),source_commit=v['source_commit'],model_revision=v['model_revision'],device=v['device'])
        # 실제 tokenize 검사를 모든 학습/selection 행에 수행한 후에만 optimizer로 전달한다.
        from .contracts import validate_request
        probe=None
        if telemetry: telemetry.event('input_audit',event='enter')
        for role in ('train','selection'):
            for line in (run_dir/(role+'.jsonl')).read_text(encoding='utf-8').splitlines():
                row = json.loads(line); q = row['questions']['decision']; state = json.loads(row['state'])
                req = validate_request({'utterance':state['current_utterance'],'question':q['instructions'],
                                        'context':state['past_dialogue'],'candidates':[{'id':k,'description':d} for k,d in q['criteria'].items() if k != '__judgment_abstain__']})
                adapter.audit(req)
                if probe is None: probe=req
        if probe is None: raise ConfigError('empty_training')
        if telemetry: telemetry.event('input_audit',event='exit')
        with phase('base_probe'): base_probe=adapter.score(probe)
        if any(not __import__('math').isfinite(x) for x in base_probe.logits): raise ConfigError('nonfinite_base_logits')
        with phase('initial_tensor_audit'): before = _tensor_manifest(Path(v['model_dir'])/'model.safetensors')
        from laya.train import dry_run,TrainConfig
        with phase('dry_run'):
            plan=dry_run(str(run_dir/'train.jsonl'),str(Path(v['model_dir'])),
                         config=TrainConfig(**training_arguments(c,run_dir/'train.jsonl',run_dir/'selection.jsonl',run_dir/'output')['config']))
        try: expected_updates=validate_upstream_execution(c,plan)
        except ConfigError as e:
            (run_dir/'summary.json').write_text(json.dumps({'trained':False,'status':'blocked','reason':e.code}),encoding='utf-8')
            raise
        # upstream은 학습 모델을 직접 로드한다. 검사 모델은 먼저 해제해 중복 GPU 점유를 피한다.
        if telemetry:
            telemetry.state['expected_optimizer_updates']=expected_updates
            telemetry.event('probe_model_release',event='enter')
        del adapter.backend.model
        import gc; gc.collect()
        import torch
        if v['device'] == 'cuda': torch.cuda.empty_cache()
        if v['device']=='cuda': torch.cuda.reset_peak_memory_stats()
        if telemetry: telemetry.event('probe_model_release',event='exit')
        from .replay import observe_replay_consumption
        replay_context = nullcontext(None)
        if replay_verified is not None:
            replay_manifest = json.loads(Path(v['experiment']['files']['manifest']['path']).read_text(encoding='utf-8'))
            replay_context = observe_replay_consumption(replay_manifest,telemetry=telemetry)
        with observe_upstream_stages(telemetry), observe_optimizer_steps(telemetry) as observed, replay_context as replay_consumption, phase('finetune'):
            summary = adapter.finetune(run_dir/'train.jsonl',run_dir/'selection.jsonl',run_dir/'output',config=c)
        with phase('trained_tensor_audit'): after = _tensor_manifest(run_dir/'output'/'model.safetensors')
        change = assess_weight_change(before,after)
        encoder_changed=sum(before[k]['digest']!=after[k]['digest'] for k in before if k.startswith('encoder.'))
        gc.collect()
        if v['device']=='cuda': torch.cuda.empty_cache()
        provenance=json.loads((Path(v['model_dir'])/'judgment_provenance.json').read_text(encoding='utf-8'))
        artifact_sha=hashlib.file_digest((run_dir/'output'/'model.safetensors').open('rb'),'sha256').hexdigest()
        provenance.update(trained_artifact_sha256=artifact_sha,code_revision=v['code_revision'])
        (run_dir/'output'/'judgment_provenance.json').write_text(json.dumps(provenance),encoding='utf-8')
        with phase('reload_model'): reloaded=LayaAdapter.from_local(run_dir/'output',source_commit=v['source_commit'],model_revision=v['model_revision'],device=v['device'])
        from safetensors.torch import load_file
        stored=load_file(str(run_dir/'output'/'model.safetensors'))
        live=reloaded.backend.model.state_dict()
        reload_verified=set(live)==set(stored) and all(torch.equal(live[k].detach().cpu(),stored[k].to(dtype=live[k].dtype)) for k in stored)
        del stored,live
        with phase('reload_probe'): reload_scores=reloaded.score(probe)
        reload_verified=reload_verified and len(reload_scores.logits)==len(base_probe.logits) and all(__import__('math').isfinite(x) for x in reload_scores.logits)
        result=completed_training_evidence(change,optimizer_updates=observed['by_optimizer'].get('AdamW',0),reload_verified=reload_verified,encoder_changed=encoder_changed)
        try: validate_upstream_execution(c,summary,observed_steps=result['optimizer_updates_observed'])
        except ConfigError as e: result.update(trained=False,status='incomplete_training_evidence',reason=e.code)
        result.update(loss_history=summary.get('epoch_loss'),python=sys.version.split()[0],optimizer_hook=observed,
                      output_weight_sha256=artifact_sha,actual_train_items=summary.get('train_items'),actual_selection_items=summary.get('eval_items'),
                      upstream_skipped=summary.get('skipped'),quality_status='not_decided',pipeline_only=True,
                      cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated() if v['device']=='cuda' else 0,
                      cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved() if v['device']=='cuda' else 0)
        result['expected_optimizer_updates']=expected_updates
        if replay_verified is not None:
            result.update(replay_verified=replay_verified, replay_consumption=replay_consumption,
                          final_test_guard=final_test_guard)
        (run_dir/'summary.json').write_text(json.dumps(result),encoding='utf-8')
        if telemetry: telemetry.event('worker_complete')
    return result


def load_fixture_bundle():
    from .data import normalize_row, split_groups
    path = Path(__file__).resolve().parents[2]/'tests'/'fixtures'/'synthetic_ko.jsonl'
    # src/judgment → repo root is parents[2].
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    mapping = {k:k for k in ('example_id','source_id','conversation_id','duplicate_group','request','gold_id','tags')}
    return split_groups(tuple(normalize_row(r,mapping) for r in rows),ratios=dict(train=.4,calibration=.2,selection=.2,test=.2),seed=13)


def run_fixture_evaluation(splits):
    from .contracts import Scores,ScoredExample,TokenAudit,ABSTAIN_ID
    from .policy import fit_temperatures,select_policy,scored_digest
    from .evaluation import evaluate
    source = Path(__file__).resolve().parents[2]/'tests'/'fixtures'/'synthetic_scores.json'
    logits = json.loads(source.read_text(encoding='utf-8'))
    scored = {}
    labels = {ABSTAIN_ID}
    for role, examples in splits.parts.items():
        rows = []
        for e in examples:
            ids = tuple(c.id for c in e.request.candidates)+(ABSTAIN_ID,)
            labels.update(ids)
            audit = TokenAudit(0,0,10000,20000,len(ids)-1,len(ids),True)
            rows.append(ScoredExample(e,Scores(ids,tuple(logits[e.example_id]),'synthetic-predeclared-logits',audit),role))
        scored[role] = tuple(rows)
    temperatures = fit_temperatures(scored['calibration'],config=dict(temperature_min=.5,temperature_max=2.,steps=7,min_samples=1))
    policy = select_policy(scored['selection'],temperatures,criteria=dict(version='synthetic-only-v1',calibration_digest=scored_digest(scored['calibration']),
                           max_error=1.,min_coverage=0.,min_samples=1,probability_grid=[0.,.5],margin_grid=[0.,.1]))
    r = evaluate(scored['test'],policy,config=dict(labels=sorted(labels),ece_bins=5,seed=13,bootstrap_repeats=20,
                 confidence_level=.95,min_groups=4,counts=[2,5,10,20],tags=['context','negation','correction','honorific','typo','spacing','mixed','indirect','multi_intent','no_answer'])).values
    r.update(status='fixture_evaluation',trained=False,real_evaluation=False,data_kind='synthetic',
             score_source='predeclared_fixture_logits',tokenizer_verified=False,gate='G1_required',policy_version=policy.version)
    return Report(r)


@contextmanager
def _worker_limits(config,run_dir):
    # worker 직접 실행에서도 동일 제한을 적용한다. monitor 없이 optimizer를 실행하지 않는다.
    import threading
    stop = threading.Event(); c = config.values; start = time.monotonic()
    observations={'peak_ram_bytes':0,'peak_vram_upper_bound_bytes':0,'peak_disk_bytes':0,'elapsed_seconds':0}
    def watch():
        while not stop.wait(1.):
            try:
                elapsed=time.monotonic()-start;ram=_memory(os.getpid());vram=_gpu_memory(os.getpid()) if c['device']=='cuda' else 0
                disk=_storage_bytes(config,run_dir)
                trigger=_resource_trigger(c,ram,vram,disk,elapsed)
                observations.update(peak_ram_bytes=max(observations['peak_ram_bytes'],ram),peak_vram_upper_bound_bytes=max(observations['peak_vram_upper_bound_bytes'],vram),peak_disk_bytes=max(observations['peak_disk_bytes'],disk),elapsed_seconds=elapsed)
                reason=('time_limit' if elapsed>c['resources']['time_limit_seconds'] else 'ram_limit' if ram>c['resources']['ram_limit_bytes'] else 'vram_limit' if vram>c['resources'].get('vram_limit_bytes',float('inf')) else 'disk_limit' if disk>c['resources']['disk_limit_bytes'] else None)
                current=current_telemetry()
                if reason is None and current is not None and current.failed.is_set(): reason='telemetry_unavailable'
                if reason:
                    _stop_owned(run_dir,observations,reason,trigger)
            except Exception:
                _stop_owned(run_dir,observations,'resource_monitor_unavailable')
    # 시작 전에 monitor 가용성을 확인한다.
    _memory(os.getpid())
    if c['device'] == 'cuda': _gpu_memory(os.getpid())
    thread = threading.Thread(target=watch,daemon=True); thread.start()
    try: yield observations
    finally:
        stop.set();thread.join(timeout=5);observations['elapsed_seconds']=time.monotonic()-start
        measured=_storage_bytes(config,run_dir)
        observations['peak_disk_bytes']=max(observations['peak_disk_bytes'],measured)
        final_storage_check(config,run_dir)
