import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from judgment.contracts import RunConfig
from judgment import runner,telemetry,__main__ as cli


class WorkerRuntimeTests(unittest.TestCase):
    def test_precheck_and_training_share_interpreter_cwd_and_modules(self):
        root=Path(__file__).parents[1].resolve();c=RunConfig({'canonical_checkout':str(root)})
        command,env,cwd=runner.worker_invocation(c,root/'.work/run')
        check,check_env,check_cwd=runner.worker_invocation(c,root/'.work/run',precheck_only=True)
        self.assertEqual(command[0],sys.executable)
        self.assertEqual(check[:-1],command);self.assertEqual(check[-1],'--precheck-only')
        self.assertEqual(env,check_env);self.assertEqual(cwd,check_cwd)
        self.assertEqual(cwd,str(root))
        self.assertEqual(env['PYTHONPATH'],os.pathsep.join((str(root/'src'),str(root/'.work/upstream/laya'))))

    def test_traceback_is_preserved_with_secret_values_masked(self):
        line='Traceback (most recent call last):\n  File "/workspace/module.py", line 12\nModuleNotFoundError: laya API_TOKEN=sentinel-private-value'
        with patch.dict(os.environ,{'API_TOKEN':'sentinel-private-value'}):
            result=telemetry.secret_safe_output(line)
        self.assertNotIn('sentinel-private-value',result)
        self.assertIn('Traceback (most recent call last):',result)
        self.assertIn('ModuleNotFoundError: laya',result)
        self.assertIn('line 12',result)

    def test_real_private_output_preserves_exception_kind_and_trace(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]/'.work') as tmp:
            with telemetry.Telemetry(Path(tmp),role='parent',memory=lambda:{},preserve_output=True) as t:
                t.output('stderr','Traceback (most recent call last):')
                t.output('stderr',"ModuleNotFoundError: No module named 'laya'")
                t.event('model_load',event='failed',error_type='ModuleNotFoundError')
            output=(Path(tmp)/'worker.output.private.jsonl').read_text()
            self.assertIn('Traceback (most recent call last):',output)
            self.assertIn("No module named 'laya'",output)
            row=json.loads((Path(tmp)/'parent.progress.private.json').read_text())
            self.assertEqual(row['error_type'],'ModuleNotFoundError')

    def test_worker_value_error_propagates_for_traceback(self):
        with patch.object(sys,'argv',['judgment','_train-worker','--config','synthetic']),patch.object(cli,'training_worker',side_effect=ValueError('synthetic')):
            with self.assertRaises(ValueError):cli.main()
