import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

from judgment.contracts import ConfigError
from judgment.telemetry import Telemetry, atomic_json, bounded_save, own_memory, redact_output, gpu_baseline, observe_upstream_stages, drain_output
import io
import importlib.util


TEST_TMP=Path(__file__).resolve().parents[1]/'.work/tmp/telemetry-tests'
TEST_TMP.mkdir(parents=True,exist_ok=True)


class TelemetryTests(unittest.TestCase):
    def test_over_limit_baseline_is_saved_and_refuses_start(self):
        row=dict(Name='synthetic-adapter',DedicatedUsage=6*1024**3+1,SharedUsage=0,TotalCommitted=0)
        value=dict(bytes_used=6*1024**3+1,sampled_epoch=time.time(),scope='windows_gpu_adapter_upper_bound',producer_pid=9,adapters=[row])
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            source=Path(temporary)/'snapshot.json';source.write_text(json.dumps(value))
            target=Path(temporary)/'baseline.private.json'
            with self.assertRaisesRegex(ConfigError,'vram_limit_before_start'): gpu_baseline(str(source),target,limit=6*1024**3)
            self.assertEqual(json.loads(target.read_text())['snapshot']['bytes_used'],6*1024**3+1)

    def test_normal_close_waits_boundedly_for_inflight_sampler(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            t=Telemetry(Path(temporary),role='worker',memory=lambda:{})
            ready=threading.Event();release=threading.Event();original=t._submit
            def submit(kind,value,**kwargs):
                original(kind,value,**kwargs)
                if value.get('event')=='heartbeat': ready.set();release.wait(.6)
            t._submit=submit;t.__enter__()
            self.assertTrue(ready.wait(1.5))
            timer=threading.Timer(.2,release.set);timer.start()
            try: t.__exit__(None,None,None)
            finally: release.set();timer.join()
    def test_host_producer_preserves_adapter_history_and_baseline(self):
        spec=importlib.util.spec_from_file_location('gpu_monitor',Path(__file__).resolve().parents[1]/'docs/monitor_pcwsl_gpu.py')
        monitor=importlib.util.module_from_spec(spec);spec.loader.exec_module(monitor)
        rows=[dict(Name='synthetic-adapter',DedicatedUsage=10,SharedUsage=5,TotalCommitted=20)]
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            output=Path(temporary)/'gpu.private.json';stop=Path(temporary)/'stop'
            with patch.object(monitor.subprocess,'check_output',return_value=json.dumps(rows)), \
                 patch.object(monitor.time,'sleep',side_effect=lambda duration:stop.touch()): monitor.main(output,stop)
            history=output.with_name(output.stem+'.history.private.jsonl')
            values=[json.loads(line) for line in history.read_text().splitlines()]
            self.assertEqual(len(values),1);self.assertEqual(values[0]['adapters'],rows)
            self.assertEqual(values[0]['bytes_used'],20)
            self.assertEqual(gpu_baseline(str(output),Path(temporary)/'before.private.json')['snapshot']['adapters'],rows)

    @unittest.skipIf(os.name=='nt','SIGTERM-ignore 실제 child 검증은 PCWSL POSIX에서 실행')
    def test_sigterm_ignoring_owned_child_is_killed_unrelated_child_survives(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            script='''import subprocess,sys,time
from pathlib import Path
import judgment.runner as r
from judgment.contracts import RunConfig
p=Path(sys.argv[1])
code="import signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path("+repr(str(p/'ready'))+").write_text('ready');time.sleep(30)"
child=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
(p/'child.pid').write_text(str(child.pid))
deadline=time.monotonic()+2
while not (p/'ready').exists() and time.monotonic()<deadline: time.sleep(.01)
assert (p/'ready').exists()
r._ACTIVE_WORKERS.append(child)
r._memory=lambda p:100;r._gpu_memory=lambda p:6*1024**3+1;r._storage_bytes=lambda c,p:100
c=RunConfig({'device':'cuda','resources':{'time_limit_seconds':30,'ram_limit_bytes':1000,'vram_limit_bytes':6*1024**3,'disk_limit_bytes':1000}})
with r._worker_limits(c,p): time.sleep(30)
'''
            env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
            unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
            try:
                result=subprocess.run([sys.executable,'-c',script,temporary],env=env,capture_output=True,timeout=5)
                self.assertEqual(result.returncode,3,result.stderr.decode(errors='replace'))
                pid=int((Path(temporary)/'child.pid').read_text())
                deadline=time.monotonic()+1
                while time.monotonic()<deadline:
                    status=Path(f'/proc/{pid}/status')
                    if not status.exists() or '\nState:\tZ' in status.read_text(): break
                    time.sleep(.01)
                else: self.fail('owned SIGTERM-ignoring child is still running')
                self.assertIsNone(unrelated.poll())
            finally: unrelated.terminate();unrelated.wait(timeout=2)

    def test_heartbeat_preserves_stage_and_memory_before_phase_finishes(self):
        calls={'n':0}
        def memory(): calls['n']+=1;return {'rss_bytes':calls['n']}
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            with Telemetry(Path(temporary),role='worker',memory=memory) as t:
                t.event('model_load',event='enter')
                deadline=time.monotonic()+1.5
                while time.monotonic()<deadline:
                    last=json.loads((Path(temporary)/'worker.progress.private.json').read_text())
                    if last['event']=='heartbeat': break
                    time.sleep(.02)
                else: self.fail('no durable heartbeat')
                self.assertEqual(last['stage'],'model_load')
                self.assertGreaterEqual(last['own_memory']['rss_bytes'],3)
    @unittest.skipUnless(importlib.util.find_spec('torch'),'CPU scalar optimizer hook에는 PyTorch 필요')
    def test_actual_cpu_scalar_step_hook_persists_successful_updates(self):
        import torch
        from judgment.runner import observe_optimizer_steps
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            parameter=torch.nn.Parameter(torch.ones(2));optimizer=torch.optim.AdamW([parameter],lr=1e-4)
            with Telemetry(Path(temporary),role='worker',memory=lambda:{}) as t, observe_optimizer_steps(t) as observed:
                parameter.sum().backward();optimizer.step();optimizer.step()
            last=json.loads((Path(temporary)/'worker.progress.private.json').read_text())
            self.assertEqual(last['completed_optimizer_updates'],2)
            self.assertEqual(observed['by_optimizer']['AdamW'],2)

    def test_normal_worker_process_preserves_redacted_output_and_completed_state(self):
        from judgment.runner import _training_process
        from judgment.contracts import RunConfig
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            root=Path(temporary)
            code='''import sys,json
from pathlib import Path
from judgment.telemetry import Telemetry
p=Path(sys.argv[1])
with Telemetry(p,role='worker',memory=lambda:{'rss_bytes':10}) as t:
 t.event('model_load');t.optimizer_start();t.optimizer_complete();t.optimizer_start();t.optimizer_complete();t.event('worker_complete')
(p/'summary.json').write_text(json.dumps({'trained':True,'optimizer_updates_observed':2}))
print('epoch 1/1 step 16 loss 1.25')
print('PRIVATE_UTTERANCE secret',file=sys.stderr)
'''
            c=RunConfig(dict(device='cuda',canonical_checkout=str(repo),code_revision='synthetic',source_commit='synthetic',
                model_revision='synthetic',seed=13,training={'freeze_encoder':True},resources=dict(time_limit_seconds=10,
                ram_limit_bytes=24*1024**3,vram_limit_bytes=6*1024**3,disk_limit_bytes=30*1024**3,estimated_disk_bytes=1)))
            env=dict(os.environ,PYTHONPATH=str(repo/'src'))
            with patch('judgment.runner._memory',return_value=100),patch('judgment.runner._gpu_memory',return_value=6*1024**3), \
                 patch('judgment.runner._storage_bytes',return_value=100),Telemetry(root,role='parent',memory=lambda:{}) as t:
                result=_training_process(c,root,[sys.executable,'-c',code,str(root)],env,None,t).values
            self.assertTrue(result['trained']);self.assertEqual(result['optimizer_updates_observed'],2)
            output=(root/'worker.output.private.jsonl').read_text()
            self.assertNotIn('PRIVATE_UTTERANCE',output);self.assertNotIn('secret',output)
            self.assertIn('numeric_progress',output)
    def test_upstream_stages_survive_error_and_hooks_restore(self):
        calls=[]
        def load(): calls.append('load')
        def scores(): calls.append('scores')
        def train(): raise RuntimeError('synthetic secret')
        module=types.SimpleNamespace(load_checkpoint=load,calibration_records=scores,train_model=train)
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            with Telemetry(Path(temporary),role='worker',memory=lambda:{}) as t:
                with self.assertRaises(RuntimeError), observe_upstream_stages(t,module=module):
                    module.load_checkpoint();module.calibration_records();module.train_model()
            events=[json.loads(line) for line in (Path(temporary)/'worker.events.private.jsonl').read_text().splitlines()]
            self.assertTrue(any(e['stage']=='before_training_selection' for e in events))
            self.assertEqual(events[-1]['stage'],'train_model');self.assertEqual(events[-1]['event'],'failed')
            self.assertIs(module.train_model,train);self.assertIs(module.load_checkpoint,load)
            self.assertNotIn('synthetic secret',json.dumps(events))

    def test_pipe_draining_records_only_sanitized_lines(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            with Telemetry(Path(temporary),role='parent',memory=lambda:{}) as t:
                thread=drain_output(io.BytesIO(b'PRIVATE=secret\nepoch 1/1 step 8 loss 1.25\n'),t,'stdout')
                thread.join(1);self.assertFalse(thread.is_alive())
            content=(Path(temporary)/'worker.output.private.jsonl').read_text()
            self.assertNotIn('PRIVATE',content);self.assertNotIn('secret',content)
            self.assertIn('numeric_progress',content)

    def test_stop_recording_exception_cannot_prevent_owned_termination(self):
        from judgment.runner import _stop_owned
        owned=types.SimpleNamespace(poll=lambda:None,terminate=unittest.mock.Mock(),kill=unittest.mock.Mock())
        with patch('judgment.runner.bounded_save',side_effect=OSError('secret')), \
             patch('judgment.runner._ACTIVE_WORKERS',[owned]), patch('judgment.runner.os._exit',side_effect=SystemExit(3)):
            with self.assertRaises(SystemExit): _stop_owned(Path('unused'),{},'vram_limit')
        owned.terminate.assert_called_once()
        owned.kill.assert_called_once()
    def test_normal_completion_persists_phase_success_count_and_memory(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            t = Telemetry(Path(temporary), role='worker', arm='A', memory=lambda: {'rss_bytes': 10})
            with t:
                with t.phase('model_load'): pass
                t.optimizer_start(); t.optimizer_complete()
                t.event('complete')
            last=json.loads((Path(temporary)/'worker.progress.private.json').read_text())
            self.assertEqual(last['stage'], 'complete')
            self.assertEqual(last['completed_optimizer_updates'], 1)
            self.assertEqual(last['optimizer_state'], 'completed')
            self.assertEqual(last['own_memory']['rss_bytes'], 10)

    def test_inflight_update_is_not_counted_completed(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            with Telemetry(Path(temporary), role='worker', memory=lambda: {}) as t:
                t.optimizer_start(); t.optimizer_complete(); t.optimizer_start()
            last=json.loads((Path(temporary)/'worker.progress.private.json').read_text())
            self.assertEqual(last['completed_optimizer_updates'], 1)
            self.assertEqual(last['optimizer_state'], 'in_progress')

    def test_unknown_worker_output_and_secret_are_never_written_verbatim(self):
        secret='PRIVATE_UTTERANCE=민원 원문; API_KEY=sk-secret'
        for line in (secret, 'RuntimeError: '+secret, 'epoch 1/1 step 8 loss 1.25 '+secret):
            self.assertNotIn(secret, json.dumps(redact_output(line)))
            self.assertNotIn('sk-secret', json.dumps(redact_output(line)))
        self.assertEqual(redact_output('epoch 1/1 step 8 loss 1.25')['step'], 8)
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            with Telemetry(Path(temporary), role='parent', memory=lambda: {}) as t:
                t.output('stderr',secret); t.output('stdout','epoch 1/1 step 8 loss 1.25')
            content=(Path(temporary)/'worker.output.private.jsonl').read_text()
            self.assertNotIn('민원', content); self.assertNotIn('sk-secret', content)
            self.assertIn('redacted',content)
            if os.name != 'nt': self.assertEqual((Path(temporary)/'worker.output.private.jsonl').stat().st_mode & 0o777,0o600)

    def test_no_new_gpu_context_and_allocator_fields_are_not_added_together(self):
        cuda=types.SimpleNamespace(is_initialized=lambda:False,
            memory_allocated=lambda: (_ for _ in ()).throw(AssertionError('new context')))
        with patch.dict(sys.modules, {'torch':types.SimpleNamespace(cuda=cuda)}):
            self.assertIsNone(own_memory(lambda pid: 50)['gpu_allocated_bytes'])
        cuda=types.SimpleNamespace(is_initialized=lambda:True,memory_allocated=lambda:20,
            memory_reserved=lambda:40,max_memory_allocated=lambda:30,max_memory_reserved=lambda:60)
        with patch.dict(sys.modules, {'torch':types.SimpleNamespace(cuda=cuda)}):
            observed=own_memory(lambda pid: 50)
            self.assertEqual(observed['gpu_allocated_bytes'],20)
            self.assertEqual(observed['gpu_reserved_bytes'],40)
            self.assertEqual(observed['rss_bytes'],50)

    def test_failed_recording_does_not_hide_failure_or_destroy_previous_record(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            target=Path(temporary)/'saved.json';atomic_json(target,{'old':True})
            with patch('judgment.telemetry.os.replace',side_effect=OSError('secret message')):
                with self.assertRaises(OSError): atomic_json(target,{'old':False})
            self.assertEqual(json.loads(target.read_text()),{'old':True})
            with patch('judgment.telemetry.atomic_json',side_effect=OSError('secret')):
                with self.assertRaisesRegex(ConfigError,'telemetry_unavailable'):
                    with Telemetry(Path(temporary),role='worker',memory=lambda:{}) as t: t.event('model_load')

    def test_hung_record_write_has_a_bounded_wait(self):
        gate=threading.Event()
        with patch('judgment.telemetry.atomic_json',side_effect=lambda *a: gate.wait(2)):
            start=time.monotonic()
            self.assertFalse(bounded_save(Path('unused'),{'reason':'vram_limit'},timeout=.03))
            self.assertLess(time.monotonic()-start,.25)
        gate.set()

    def test_baseline_binds_fresh_adapter_details_without_gpu_query(self):
        row=dict(Name='adapter-0',DedicatedUsage=10,SharedUsage=5,TotalCommitted=20)
        snapshot=dict(bytes_used=20,sampled_epoch=time.time(),scope='windows_gpu_adapter_upper_bound',producer_pid=9,adapters=[row])
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            source=Path(temporary)/'snapshot.json';source.write_text(json.dumps(snapshot))
            result=gpu_baseline(str(source),Path(temporary)/'baseline.private.json')
            self.assertEqual(result['snapshot']['adapters'],[row])
            snapshot['bytes_used']=19;source.write_text(json.dumps(snapshot))
            with self.assertRaises(ConfigError): gpu_baseline(str(source),Path(temporary)/'other.json')

    def test_forced_limit_stop_keeps_last_completed_state(self):
        self.run_forced_stop(False)

    def test_hung_stop_recording_still_exits_and_terminates_only_owned_worker(self):
        self.run_forced_stop(True)

    def run_forced_stop(self, hang):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temporary:
            script='''import sys,time,json
from pathlib import Path
from judgment.telemetry import Telemetry
from judgment.contracts import RunConfig
import judgment.runner as r
import judgment.telemetry as telemetry
root=Path(sys.argv[1])
with Telemetry(root,role='worker',memory=lambda:{'rss_bytes':100}) as t:
    t.event('train_model');t.optimizer_start();t.optimizer_complete();t.optimizer_start()
class Owned:
    def poll(self): return None
    def terminate(self): (root/'owned_terminated').write_text('yes')
    def kill(self): (root/'owned_killed').write_text('yes')
r._ACTIVE_WORKERS.append(Owned())
r._memory=lambda p:100
def gpu(p):
    r._GPU_OBSERVATIONS.snapshot={'bytes_used':6*1024**3+1,'sampled_epoch':123.,'adapters':[{'Name':'synthetic-original','DedicatedUsage':6*1024**3+1,'SharedUsage':0,'TotalCommitted':0}]}
    (root/'newer-snapshot.json').write_text(json.dumps({'sampled_epoch':999.}))
    return 6*1024**3+1
r._gpu_memory=gpu
r._storage_bytes=lambda c,p:100
if sys.argv[2]=='hang': telemetry.atomic_json=lambda *a,**kw: time.sleep(20)
c=RunConfig({'device':'cuda','resources':{'time_limit_seconds':30,'ram_limit_bytes':1000,'vram_limit_bytes':6*1024**3,'disk_limit_bytes':1000}})
with r._worker_limits(c,root): time.sleep(20)
'''
            env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
            start=time.monotonic()
            result=subprocess.run([sys.executable,'-c',script,temporary,'hang' if hang else 'ok'],env=env,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,3,result.stderr.decode(errors='replace'))
            self.assertLess(time.monotonic()-start,4)
            self.assertTrue((Path(temporary)/'owned_terminated').exists())
            self.assertTrue((Path(temporary)/'owned_killed').exists())
            last=json.loads((Path(temporary)/'worker.progress.private.json').read_text())
            self.assertEqual(last['completed_optimizer_updates'],1)
            self.assertEqual(last['optimizer_state'],'in_progress')
            if not hang:
                stop=json.loads((Path(temporary)/'limit_failure.json').read_text())
                self.assertEqual(stop['reason'],'vram_limit')
                self.assertEqual(stop['worker_progress']['completed_optimizer_updates'],1)
                self.assertIsNone(stop['exact_final_optimizer_updates'])
                self.assertEqual(stop['trigger']['gpu_snapshot']['sampled_epoch'],123.)
                self.assertEqual(stop['trigger']['gpu_snapshot']['adapters'][0]['Name'],'synthetic-original')
                self.assertEqual(stop['trigger']['gpu_upper_bound_bytes'],6*1024**3+1)
                self.assertEqual(stop['trigger']['limits']['vram_limit_bytes'],6*1024**3)
