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


def atomic_json(path, value, *, publish_before_sync=False, timing=None):
    started=time.perf_counter();last=started
    def mark(name):
        nonlocal last
        now=time.perf_counter()
        if timing is not None:timing[name]=now-last
        last=now
    path=Path(path)
    temporary=path.with_name(path.name+f'.tmp-{os.getpid()}-{threading.get_ident()}')
    try:
        serialized=json.dumps(value,ensure_ascii=True,allow_nan=False);mark('serialize')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        mark('open')
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(serialized);mark('write')
            stream.flush();mark('flush')
            if not publish_before_sync: os.fsync(stream.fileno())
            mark('fsync')
        mark('close')
        os.replace(temporary,path)
        mark('replace')
        if publish_before_sync:
            # 중단 packet만 먼저 공개한다. sync 완료를 기다리느라 상한 종료를 늦추지 않는다.
            fd=os.open(path,os.O_RDWR)
            try: os.fsync(fd)
            finally: os.close(fd)
    finally:
        try: temporary.unlink()
        except FileNotFoundError: pass
        mark('cleanup')
        if timing is not None:timing['total']=time.perf_counter()-started


def append_json(path,value,*,sync=True):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=True,allow_nan=False)+'\n')
        stream.flush()
        if sync:os.fsync(stream.fileno())


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
        self.failure_once=threading.Lock();self.failure_record=None;self.failure_fd=None;self.inflight_operation=None
        self.timing_fd=None;self.delay_fd=None;self.delayed=threading.Event();self.delay_count=0

    def fail(self,operation,error=None):
        self.failed.set()  # 별도 로그 I/O를 기다리며 중단을 늦추지 않는다.
        with self.failure_once:
            if self.failure_record is not None:return
            row=dict(operation=operation,exception_type=type(error).__name__ if error else 'TimeoutError' if operation=='submit.wait_timeout' else 'ConfigError',
                errno=getattr(error,'errno',None),error_code=operation,stage=self.state.get('stage'),
                sampled_epoch=time.time(),pid=os.getpid(),inflight_operation=self.inflight_operation,
                completed_optimizer_updates=self.state.get('completed_optimizer_updates'))
            frames=[];tb=getattr(error,'__traceback__',None)
            while tb is not None:
                frames.append(tb.tb_frame.f_code.co_name);tb=tb.tb_next
            row['exception_calls']=frames[-8:]  # 원문·locals·경로·예외 message 없음.
            self.failure_record=row
            payload=(json.dumps(row,ensure_ascii=True)+'\n').encode()
            fd=self.failure_fd
        def write():
            try:
                if fd is not None:os.write(fd,payload)
            except OSError:pass
            finally:
                if fd is not None:
                    try:os.close(fd)
                    except OSError:pass
                self.failure_fd=None
        emergency=threading.Thread(target=write,daemon=True);emergency.start();emergency.join(.02)

    def _sample(self):
        while not self.stop_sampling.wait(.5):
            try: self.event(None,event='heartbeat')
            except Exception as e:self.fail('sampler.event',e);return

    def _writer(self):
        while True:
            item=self.queue.get()
            if item is None: return
            kind,value,done=item
            timing={};writer_start=time.perf_counter()
            try:
                self.inflight_operation='writer.append_json'
                if kind=='output': append_json(self.folder/'worker.output.private.jsonl',value)
                else:
                    # heartbeat history는 flush, 최신 snapshot은 기존 durable fsync 유지.
                    if value.get('event')=='heartbeat':append_json(self.folder/(self.role+'.events.private.jsonl'),value,sync=False)
                    else:append_json(self.folder/(self.role+'.events.private.jsonl'),value)
                    self.inflight_operation='writer.atomic_json'
                    if self.timing_fd is None:atomic_json(self.folder/(self.role+'.progress.private.json'),value)
                    else:atomic_json(self.folder/(self.role+'.progress.private.json'),value,timing=timing)
            except Exception as e:self.fail(self.inflight_operation,e)
            finally:
                if self.timing_fd is not None:
                    row=dict(kind=kind,stage=value.get('stage'),sequence=value.get('sequence'),atomic=timing,
                        lock_wait=value.get('lock_wait_seconds'),queue_wait=writer_start-getattr(done,'enqueued_at',writer_start),
                        writer_total=time.perf_counter()-writer_start,sampled_epoch=time.time())
                    try:os.write(self.timing_fd,(json.dumps(row)+'\n').encode())
                    except OSError:pass
                self.inflight_operation=None;done.set()

    def _submit(self,kind,value,*,wait=True):
        if self.failed.is_set(): raise ConfigError('telemetry_unavailable')
        done=threading.Event()
        done.enqueued_at=time.perf_counter()
        try: self.queue.put_nowait((kind,value,done))
        except queue.Full:
            self.fail('submit.queue_full');raise ConfigError('telemetry_unavailable') from None
        if wait:self._wait_record(done)
        return done

    def _wait_record(self,done):
        if not done.wait(self.timeout):
            self.delayed.set();self.delay_count+=1
            if self.delay_count==1:
                row=dict(classification='progress_delay',operation='submit.wait_timeout',exception_type='TimeoutError',
                    stage=self.state.get('stage'),inflight_operation=self.inflight_operation,sampled_epoch=time.time())
                try:fd=os.dup(self.delay_fd) if self.delay_fd is not None else None
                except OSError:fd=None
                def note():
                    try:
                        if fd is not None:os.write(fd,(json.dumps(row)+'\n').encode())
                    except OSError:pass
                    finally:
                        if fd is not None:
                            try:os.close(fd)
                            except OSError:pass
                thread=threading.Thread(target=note,daemon=True);thread.start();thread.join(.02)
        if self.failed.is_set():raise ConfigError('telemetry_unavailable')

    def event(self,stage,*,event='state',position=None,error_type=None):
        try:memory=self.memory()
        except Exception as e:self.fail('event.memory',e);raise
        if event=='heartbeat' and self.stop_sampling.is_set(): return
        lock_start=time.perf_counter()
        with self.lock:
            self.state.update(stage=stage or self.state['stage'],event=event,sequence=self.state['sequence']+1,
                sampled_epoch=time.time(),monotonic_seconds=time.monotonic(),own_memory=memory)
            if position is not None: self.state['encoded_exposure_position']=position
            if self.timing_fd is not None:self.state['lock_wait_seconds']=time.perf_counter()-lock_start
            if error_type is not None:
                self.state['error_type']=error_type if error_type in ('RuntimeError','ValueError','TypeError','ConfigError','InputError','ModelError','OSError','MemoryError') else 'redacted_exception'
            done=self._submit('state',dict(self.state),wait=False)
        self._wait_record(done)  # queue 순서 보존, I/O 대기 중 state lock 해제.

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
        self.failure_fd=os.open(self.folder/'telemetry.failure.min.private.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        self.delay_fd=os.open(self.folder/'telemetry.delay.min.private.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        if os.environ.get('JUDGMENT_TELEMETRY_TIMING')=='1':
            self.timing_fd=os.open(self.folder/'writer.timings.private.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        self.thread.start()
        try: self.event('started')
        except BaseException:
            try: self.queue.put_nowait(None)
            except queue.Full: pass
            if self.delay_fd is not None:os.close(self.delay_fd);self.delay_fd=None
            if self.timing_fd is not None and not self.thread.is_alive():os.close(self.timing_fd);self.timing_fd=None
            # 실패 진단 daemon과 writer가 종료 전에 FD를 사용한다. process 종료로 회수한다.
            raise
        _ACTIVE.append(self);self.sampler.start();return self

    def __exit__(self,exc_type,exc,tb):
        if self in _ACTIVE: _ACTIVE.remove(self)
        self.stop_sampling.set();self.sampler.join(self.timeout)
        try: self.queue.put_nowait(None)
        except queue.Full:self.fail('close.queue_full')
        self.thread.join(self.timeout)
        if not self.thread.is_alive() and self.timing_fd is not None:os.close(self.timing_fd);self.timing_fd=None
        if self.delay_fd is not None:os.close(self.delay_fd);self.delay_fd=None
        if self.thread.is_alive() or self.sampler.is_alive():self.fail('close.thread_timeout')
        if self.failure_record is None and self.failure_fd is not None:os.close(self.failure_fd);self.failure_fd=None
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
        except Exception as e:telemetry.fail('drain_output',e)
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
