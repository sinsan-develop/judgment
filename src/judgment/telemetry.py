"""원문 없는 로컬 관측. 기록 I/O를 상한 종료의 무제한 대기로 만들지 않는다."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
from .contracts import ConfigError

_ACTIVE=[]


def current_telemetry():
    return _ACTIVE[-1] if _ACTIVE else None


def atomic_json(path, value, *, publish_before_sync=False):
    path=Path(path)
    temporary=path.with_name(path.name+f'.tmp-{os.getpid()}-{threading.get_ident()}')
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=True,allow_nan=False);stream.flush()
            if not publish_before_sync: os.fsync(stream.fileno())
        os.replace(temporary,path)
        if publish_before_sync:
            # 중단 packet만 먼저 공개한다. sync 완료를 기다리느라 상한 종료를 늦추지 않는다.
            fd=os.open(path,os.O_RDWR)
            try: os.fsync(fd)
            finally: os.close(fd)
    finally:
        try: temporary.unlink()
        except FileNotFoundError: pass


def append_json(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=True,allow_nan=False)+'\n')
        stream.flush();os.fsync(stream.fileno())


def bounded_save(path,value,*,timeout=.05,publish_before_sync=False):
    def write():
        payload=value() if callable(value) else value
        if publish_before_sync: atomic_json(path,payload,publish_before_sync=True)
        else: atomic_json(path,payload)
    return bounded_call(write,timeout=timeout)


def bounded_call(operation,*,timeout=.05):
    finished=threading.Event();success=[]
    def write():
        try:
            operation();success.append(True)
        except Exception: pass
        finally: finished.set()
    threading.Thread(target=write,daemon=True).start()
    finished.wait(timeout)
    return bool(success)


def own_memory(rss):
    try: resident=rss(os.getpid())
    except Exception: resident=None
    result=dict(rss_bytes=resident,gpu_scope='pytorch_allocator_only',gpu_status='not_initialized',
                gpu_allocated_bytes=None,gpu_reserved_bytes=None,gpu_peak_allocated_bytes=None,gpu_peak_reserved_bytes=None)
    torch=sys.modules.get('torch')
    if torch is None: return result
    try:
        if not torch.cuda.is_initialized(): return result
        result.update(gpu_status='observed',gpu_allocated_bytes=torch.cuda.memory_allocated(),
            gpu_reserved_bytes=torch.cuda.memory_reserved(),gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved())
    except Exception: result['gpu_status']='unavailable'
    return result


def redact_output(line):
    # whitelist된 전체 문장만 숫자로 보존한다. 임의 stderr/traceback/원문은 저장하지 않는다.
    match=re.fullmatch(r'epoch ([0-9]+)/([0-9]+) step ([0-9]+) loss ([0-9.eE+\-]+)',line.strip())
    mean=re.fullmatch(r'epoch ([0-9]+)/([0-9]+) mean loss ([0-9.eE+\-]+)',line.strip())
    try:
        if match and math.isfinite(float(match[4])):
            return dict(kind='numeric_progress',epoch=int(match[1]),epochs=int(match[2]),step=int(match[3]),loss=float(match[4]))
        if mean and math.isfinite(float(mean[3])):
            return dict(kind='numeric_mean_loss',epoch=int(mean[1]),epochs=int(mean[2]),loss=float(mean[3]))
    except (ValueError,OverflowError): pass
    for name in ('RuntimeError','ValueError','TypeError','ConfigError','InputError','ModelError','OSError','MemoryError'):
        if line.startswith(name+':'): return dict(kind='redacted',exception_type=name,content='omitted')
    return dict(kind='redacted',content='omitted')


def gpu_baseline(snapshot_path,output,*,limit=None):
    from .gpu_snapshot import validate_gpu_snapshot,parse_adapter_memory
    snapshot=json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
    validate_gpu_snapshot(snapshot)
    rows=snapshot.get('adapters')
    if not isinstance(rows,list) or not rows or any(not isinstance(r.get('Name'),str) or not r['Name'] for r in rows):
        raise ConfigError('gpu_baseline_unavailable')
    if parse_adapter_memory(rows)!=snapshot['bytes_used']: raise ConfigError('gpu_baseline_unavailable')
    result=dict(captured_epoch=time.time(),scope='host_all_gpu_adapter_upper_bound',snapshot=snapshot,start_limit_bytes=limit)
    if not bounded_save(output,result,timeout=1.): raise ConfigError('telemetry_unavailable')
    if limit is not None and snapshot['bytes_used']>limit: raise ConfigError('vram_limit_before_start')
    return result


def stop_evidence(folder,observations):
    result=dict(observations,exact_final_optimizer_updates=None,stop_record_durability='best_effort_before_forced_exit')
    for role in ('worker','parent'):
        try:
            path=Path(folder)/(role+'.progress.private.json')
            if path.stat().st_size>65536: raise ValueError('progress_size')
            value=json.loads(path.read_text(encoding='utf-8'))
            result[role+'_progress']=value
            result[role+'_progress_age_seconds']=max(0,time.time()-value['sampled_epoch'])
        except (OSError,ValueError,KeyError,TypeError): result[role+'_progress']=None
    return result


class Telemetry:
    def __init__(self,folder,*,role,arm=None,memory=None,timeout=1.):
        self.folder=Path(folder);self.role=role;self.timeout=timeout
        if memory is None:
            def memory():
                from .runner import _memory
                return own_memory(_memory)
        self.memory=memory;self.queue=queue.Queue(maxsize=256);self.failed=threading.Event()
        self.lock=threading.RLock();self.stop_sampling=threading.Event()
        self.state=dict(role=role,run_id=self.folder.name,arm=arm,pid=os.getpid(),sequence=0,
            completed_optimizer_updates=0,optimizer_state='not_started',stage='started')
        self.thread=threading.Thread(target=self._writer,daemon=True)
        self.sampler=threading.Thread(target=self._sample,daemon=True)

    def _sample(self):
        while not self.stop_sampling.wait(.5):
            try: self.event(None,event='heartbeat')
            except Exception: self.failed.set();return

    def _writer(self):
        while True:
            item=self.queue.get()
            if item is None: return
            kind,value,done=item
            try:
                if kind=='output': append_json(self.folder/'worker.output.private.jsonl',value)
                else:
                    append_json(self.folder/(self.role+'.events.private.jsonl'),value)
                    atomic_json(self.folder/(self.role+'.progress.private.json'),value)
            except Exception: self.failed.set()
            finally: done.set()

    def _submit(self,kind,value,*,wait=True):
        if self.failed.is_set(): raise ConfigError('telemetry_unavailable')
        done=threading.Event()
        try: self.queue.put_nowait((kind,value,done))
        except queue.Full:
            self.failed.set();raise ConfigError('telemetry_unavailable') from None
        if wait and (not done.wait(self.timeout) or self.failed.is_set()):
            self.failed.set();raise ConfigError('telemetry_unavailable')

    def event(self,stage,*,event='state',position=None,error_type=None):
        memory=self.memory()
        if event=='heartbeat' and self.stop_sampling.is_set(): return
        with self.lock:
            self.state.update(stage=stage or self.state['stage'],event=event,sequence=self.state['sequence']+1,
                sampled_epoch=time.time(),monotonic_seconds=time.monotonic(),own_memory=memory)
            if position is not None: self.state['encoded_exposure_position']=position
            if error_type is not None:
                self.state['error_type']=error_type if error_type in ('RuntimeError','ValueError','TypeError','ConfigError','InputError','ModelError','OSError','MemoryError') else 'redacted_exception'
            self._submit('state',dict(self.state))

    @contextmanager
    def phase(self,stage):
        self.event(stage,event='enter')
        try: yield
        except BaseException as error:
            try: self.event(stage,event='failed',error_type=type(error).__name__)
            except ConfigError: pass
            raise
        else: self.event(stage,event='exit')

    def optimizer_start(self):
        with self.lock: self.state['optimizer_state']='in_progress'
        self.event('optimizer_step',event='enter')

    def optimizer_complete(self):
        with self.lock:
            self.state['completed_optimizer_updates']+=1;self.state['optimizer_state']='completed'
        self.event('optimizer_step',event='exit')

    def output(self,stream,line):
        self._submit('output',dict(stream=stream,sampled_epoch=time.time(),**redact_output(line)),wait=False)

    def __enter__(self):
        self.folder.mkdir(exist_ok=True)
        self.thread.start()
        try: self.event('started')
        except BaseException:
            try: self.queue.put_nowait(None)
            except queue.Full: pass
            raise
        _ACTIVE.append(self);self.sampler.start();return self

    def __exit__(self,exc_type,exc,tb):
        if self in _ACTIVE: _ACTIVE.remove(self)
        self.stop_sampling.set();self.sampler.join(self.timeout)
        try: self.queue.put_nowait(None)
        except queue.Full: self.failed.set()
        self.thread.join(self.timeout)
        if exc_type is None and (self.thread.is_alive() or self.sampler.is_alive() or self.failed.is_set()): raise ConfigError('telemetry_unavailable')


def drain_output(pipe,telemetry,stream):
    def read():
        buffered=b''
        try:
            while True:
                chunk=pipe.read(1024)
                if not chunk: break
                buffered+=chunk
                while b'\n' in buffered:
                    line,buffered=buffered.split(b'\n',1);telemetry.output(stream,line.decode('utf-8',errors='replace'))
                if len(buffered)>4096:
                    telemetry.output(stream,'');buffered=b''
            if buffered: telemetry.output(stream,buffered.decode('utf-8',errors='replace'))
        except Exception: telemetry.failed.set()
        finally: pipe.close()
    thread=threading.Thread(target=read,daemon=True);thread.start();return thread


@contextmanager
def observe_upstream_stages(telemetry,*,module=None):
    if telemetry is None:
        yield;return
    if module is None:
        import laya.train as module
    originals={name:getattr(module,name) for name in ('load_checkpoint','calibration_records','train_model')}
    trained={'entered':False}
    def load(*args,**kwargs):
        with telemetry.phase('finetune_model_load'): return originals['load_checkpoint'](*args,**kwargs)
    def scores(*args,**kwargs):
        stage='after_training_evaluation' if trained['entered'] else 'before_training_selection'
        with telemetry.phase(stage): return originals['calibration_records'](*args,**kwargs)
    def train(*args,**kwargs):
        trained['entered']=True
        with telemetry.phase('train_model'): return originals['train_model'](*args,**kwargs)
    module.load_checkpoint=load;module.calibration_records=scores;module.train_model=train
    try: yield
    finally:
        for name,function in originals.items(): setattr(module,name,function)
