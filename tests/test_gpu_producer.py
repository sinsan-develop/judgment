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
            with patch.object(producer.subprocess,'check_output',return_value='[{"DedicatedUsage":1,"SharedUsage":0,"TotalCommitted":1}]'),patch.object(producer,'atomic_json',side_effect=denied):
                with self.assertRaisesRegex(RuntimeError,'snapshot_recording_failed'):producer.main(output,stop)
            row=json.loads((Path(tmp)/'gpu.failures.private.jsonl').read_text())
            self.assertEqual((row['failure_kind'],row['errno'],row['stop_seen']),('exception',13,True))
            self.assertNotIn('private text',str(row))
