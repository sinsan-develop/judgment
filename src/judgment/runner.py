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
from .contracts import RunConfig, RunEvidence, Report, ConfigError, validate_run_config
from .data import to_laya_row, connected_groups, bundle_digest


def resource_budget(resources, *, free_bytes):
    # baseline 캐시/데이터 예상량 + upstream latest와 최종본의 동시 점유.
    required = resources['estimated_disk_bytes'] + 2*resources['checkpoint_bytes']
    if required > resources['disk_limit_bytes'] or required > free_bytes: raise ConfigError('disk_budget')
    return required


def preflight(config):
    if config.values.get('mode') == 'fixture':
        return Report({'mode':'fixture','training_allowed':False,'download_allowed':False,'gate':'G1_required',
                       'python':sys.version.split()[0], 'status':'offline_fixture_ready'})
    c = validate_run_config(config.values, real=True).values
    bound = {k:v for k,v in c.items() if k != 'approval'}
    digest = hashlib.sha256(json.dumps(bound,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if c['approval'].get('scope_digest') != digest: raise ConfigError('approval_scope_mismatch')
    if Path(c['canonical_checkout']).resolve() != Path.cwd().resolve(): raise ConfigError('canonical_checkout')
    try:
        head = subprocess.check_output(['git','rev-parse','HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError): raise ConfigError('code_revision') from None
    if c['code_revision'] != head: raise ConfigError('code_revision')
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
        handle = api.OpenProcess(0x1000|0x10,False,pid)
        if not handle: raise ConfigError('memory_monitor_unavailable')
        try:
            c = Counters(); c.cb = ctypes.sizeof(c)
            ok = ctypes.WinDLL('psapi').GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb)
            if not ok: raise ConfigError('memory_monitor_unavailable')
            return c.WorkingSetSize
        finally: api.CloseHandle(handle)
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'): return int(line.split()[1])*1024
    except OSError: raise ConfigError('memory_monitor_unavailable') from None
    raise ConfigError('memory_monitor_unavailable')


def _gpu_memory(pid):
    try:
        out = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True,stderr=subprocess.DEVNULL,timeout=5)
        total = 0
        for line in out.splitlines():
            parts = line.split(',')
            if parts[0].strip() == str(pid): total += int(parts[1].strip())*1024*1024
        return total
    except (OSError, ValueError, subprocess.SubprocessError): raise ConfigError('vram_monitor_unavailable') from None


def run_training(config, splits):
    if config.values.get('mode') == 'fixture':
        train, selection = training_rows(splits)
        return RunEvidence({'status':'fixture_only','trained':False,'optimizer_called':False,
                            'train_rows':len(train),'selection_rows':len(selection),'data_kind':'synthetic',
                            'quality_status':'not_decided','gate':'G1_required'})
    preflight(config)
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
    env = dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    start = time.monotonic(); peak_ram = peak_vram = 0; failure = None
    proc = subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        while proc.poll() is None:
            ram = _memory(proc.pid); vram = _gpu_memory(proc.pid) if c['device'] == 'cuda' else 0
            peak_ram,peak_vram = max(peak_ram,ram),max(peak_vram,vram)
            disk = sum(p.stat().st_size for p in run_dir.rglob('*') if p.is_file())
            if time.monotonic()-start > c['resources']['time_limit_seconds']: failure = 'time_limit'
            elif ram > c['resources']['ram_limit_bytes']: failure = 'ram_limit'
            elif vram > c['resources'].get('vram_limit_bytes',float('inf')): failure = 'vram_limit'
            elif disk + c['resources']['estimated_disk_bytes'] > c['resources']['disk_limit_bytes']: failure = 'disk_limit'
            if failure: break
            time.sleep(.2)
    except ConfigError as e: failure = e.code
    finally:
        if proc.poll() is None: proc.terminate()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    summary_path = run_dir/'summary.json'
    result = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else {'trained':False}
    if failure or proc.returncode != 0: result = {'trained':False,'status':'failed','reason':failure or 'worker_failed'}
    result.update(peak_ram_bytes=peak_ram,peak_vram_bytes=peak_vram,elapsed_seconds=time.monotonic()-start,
                  code_revision=c['code_revision'],source_commit=c['source_commit'],model_revision=c['model_revision'],seed=c['seed'],
                  training_scope='head_only' if c['training']['freeze_encoder'] else 'encoder_and_head',
                  optimizer_updates_observed=None, optimizer_updates_status='unverified',cleanup='retained_local_only_pending_review')
    (run_dir/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return RunEvidence(result)


def training_worker(config_path):
    from .laya_adapter import LayaAdapter, offline
    c = validate_run_config(json.loads(config_path.read_text(encoding='utf-8')),real=True)
    v = c.values; run_dir = config_path.parent
    with offline():
        adapter = LayaAdapter.from_local(Path(v['model_dir']),source_commit=v['source_commit'],model_revision=v['model_revision'],device=v['device'])
        # 실제 tokenize 검사를 모든 학습/selection 행에 수행한 후에만 optimizer로 전달한다.
        from .contracts import validate_request
        for role in ('train','selection'):
            for line in (run_dir/(role+'.jsonl')).read_text(encoding='utf-8').splitlines():
                row = json.loads(line); q = row['questions']['decision']; state = json.loads(row['state'])
                req = validate_request({'utterance':state['current_utterance'],'question':q['instructions'],
                                        'context':state['past_dialogue'],'candidates':[{'id':k,'description':d} for k,d in q['criteria'].items() if k != '__judgment_abstain__']})
                adapter.audit(req)
        before = _tensor_manifest(Path(v['model_dir'])/'model.safetensors')
        # upstream은 학습 모델을 직접 로드한다. 검사 모델은 먼저 해제해 중복 GPU 점유를 피한다.
        del adapter.backend.model
        import gc; gc.collect()
        import torch
        if v['device'] == 'cuda': torch.cuda.empty_cache()
        summary = adapter.finetune(run_dir/'train.jsonl',run_dir/'selection.jsonl',run_dir/'output',config=c)
        after = _tensor_manifest(run_dir/'output'/'model.safetensors')
        result = assess_weight_change(before,after)
        # 가중치 변화를 측정했어도 실제 reload/optimizer 관측이 없으면 완료 증거는 미확인이다.
        result.update(status='weight_change_measured_reload_pending' if result['trained'] else 'no_weight_change',
                      loss_history=summary.get('epoch_loss'), trained=False, weight_changed=result['trained'],
                      reload_verified=False, python=sys.version.split()[0])
        (run_dir/'summary.json').write_text(json.dumps(result),encoding='utf-8')


def load_fixture_bundle():
    from .data import normalize_row, split_groups
    path = Path(__file__).resolve().parents[2]/'tests'/'fixtures'/'synthetic_ko.jsonl'
    # src/judgment → repo root is parents[2].
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    mapping = {k:k for k in ('example_id','source_id','conversation_id','duplicate_group','request','gold_id','tags')}
    return split_groups(tuple(normalize_row(r,mapping) for r in rows),ratios=dict(train=.4,calibration=.2,selection=.2,test=.2),seed=13)
