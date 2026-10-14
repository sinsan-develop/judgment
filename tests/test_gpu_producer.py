import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('producer', Path(__file__).parents[1]/'docs/monitor_pcwsl_gpu.py')
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


class ProducerTests(unittest.TestCase):
    def test_torn_slot_fallback_stale_rejection_and_limit_value(self):
        import json
        from judgment.gpu_snapshot import read_gpu_snapshot
        from judgment.contracts import ConfigError
        with tempfile.TemporaryDirectory(dir=producer.ROOT/'.work') as tmp:
            output=Path(tmp)/'gpu.json';now=time.time()
            row=dict(sampled_epoch=now,bytes_used=6*1024**3+1,scope='windows_gpu_adapter_upper_bound',producer_pid=1)
            Path(str(output)+'.slot0').write_text(json.dumps(row))
            Path(str(output)+'.slot1').write_text('{')
            self.assertEqual(read_gpu_snapshot(output,now=now),6*1024**3+1)
            with self.assertRaises(ConfigError):read_gpu_snapshot(output,now=now+16)
    def test_live_publish_does_not_depend_on_replace(self):
        from judgment.gpu_snapshot import read_gpu_value
        with tempfile.TemporaryDirectory(dir=producer.ROOT/'.work') as tmp:
            output=Path(tmp)/'gpu.json'
            row=dict(sampled_epoch=time.time(),bytes_used=1,scope='windows_gpu_adapter_upper_bound',producer_pid=1)
            with patch('os.replace',side_effect=OSError('replace stalled')):
                producer.publish_live_snapshot(output,row)
            self.assertEqual(read_gpu_value(output)['bytes_used'],1)
    def test_live_snapshot_and_history_do_not_wait_for_fsync(self):
        with tempfile.TemporaryDirectory(dir=producer.ROOT/'.work') as tmp:
            output=Path(tmp)/'gpu.json'
            with patch('judgment.telemetry.os.fsync',side_effect=lambda fd:time.sleep(.2)) as sync:
                result=producer.record_operation(lambda:producer.publish_live_snapshot(output,{'bytes_used':1}),timeout=.05)
                self.assertIsNone(result['failure_kind'])
                producer.append_json(Path(tmp)/'history.jsonl',{'bytes_used':1},sync=False)
                sync.assert_not_called()
            self.assertTrue(any(Path(tmp).glob('gpu.json.slot*')))

    def test_stop_during_query_does_not_publish(self):
        with tempfile.TemporaryDirectory(dir=producer.ROOT/'.work') as tmp:
            output=Path(tmp)/'gpu.json';stop=Path(tmp)/'stop'
            def query(*a, **k):
                stop.touch()
                return '[{"DedicatedUsage":1,"SharedUsage":0,"TotalCommitted":1}]'
            with patch.object(producer.subprocess,'check_output',side_effect=query):
                producer.main(output,stop)
            self.assertFalse(output.exists())

    def test_exception_and_timeout_are_distinct_and_bounded(self):
        def denied(): raise PermissionError(13,'private text')
        result=producer.record_operation(denied,timeout=.05)
        self.assertEqual(result['failure_kind'],'exception')
        self.assertEqual(result['exception_type'],'PermissionError')
        self.assertEqual(result['errno'],13)
        self.assertNotIn('private text',str(result))
        start=time.monotonic()
        result=producer.record_operation(lambda:time.sleep(.2),timeout=.02)
        self.assertEqual(result['failure_kind'],'timeout')
        self.assertLess(time.monotonic()-start,.15)

    def test_real_write_failure_is_not_hidden_by_stop(self):
        import json
        with tempfile.TemporaryDirectory(dir=producer.ROOT/'.work') as tmp:
            output=Path(tmp)/'gpu.json';stop=Path(tmp)/'stop'
            def denied(*a,**k):
                stop.touch()
                raise PermissionError(13,'private text')
            with patch.object(producer.subprocess,'check_output',return_value='[{"DedicatedUsage":1,"SharedUsage":0,"TotalCommitted":1}]'),patch.object(producer,'publish_live_snapshot',side_effect=denied):
                with self.assertRaisesRegex(RuntimeError,'snapshot_recording_failed'):producer.main(output,stop)
            row=json.loads((Path(tmp)/'gpu.failures.private.jsonl').read_text())
            self.assertEqual((row['failure_kind'],row['errno'],row['stop_seen']),('exception',13,True))
            self.assertNotIn('private text',str(row))
