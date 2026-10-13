import json
import unittest
from pathlib import Path
from unittest.mock import patch
from judgment.contracts import ConfigError
from judgment.gpu_snapshot import parse_adapter_memory, read_gpu_snapshot
from judgment.runner import _gpu_memory, preflight
from judgment.contracts import RunConfig, SOURCE_COMMIT, validate_run_config
import hashlib


class GpuSnapshotTests(unittest.TestCase):
    def test_shared_image_charge_rejects_negative_bool_or_noninteger(self):
        c = dict(mode='real', approval={'gate': 'G1', 'confirmed': True}, canonical_checkout='synthetic',
                 model_dir='model', model_revision='a'*40, source_commit=SOURCE_COMMIT, device='cuda',
                 work_dir='work', seed=13, code_revision='b'*40, data_manifest={}, split_paths={}, training={},
                 resources={k: 10 for k in ('disk_limit_bytes', 'estimated_disk_bytes', 'ram_limit_bytes',
                                            'time_limit_seconds', 'checkpoint_bytes', 'vram_limit_bytes')})
        for invalid in (-1, True, 1.5, '100'):
            c['resources']['shared_runtime_image_bytes'] = invalid
            with self.assertRaisesRegex(ConfigError, 'shared_runtime_image_bytes'): validate_run_config(c, real=True)

    def test_snapshot_binding_rejects_unapproved_or_missing_override(self):
        for approved, actual in ((None, 'unapproved.json'), ('approved.json', None), ('approved.json', 'other.json')):
            c = {'mode': 'real', 'resources': {}}
            if approved: c['resources']['gpu_memory_snapshot_path'] = approved
            digest = hashlib.sha256(json.dumps(c, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            c['approval'] = {'scope_digest': digest}
            env = {} if actual is None else {'JUDGMENT_GPU_MEMORY_SNAPSHOT': actual}
            with patch.dict('os.environ', env, clear=True), patch('judgment.runner.validate_run_config', return_value=RunConfig(c)):
                with self.assertRaisesRegex(ConfigError, 'vram_monitor_binding'): preflight(RunConfig(c))
    def test_all_adapters_use_committed_or_resident_upper_bound(self):
        rows = [{'DedicatedUsage': 10, 'SharedUsage': 5, 'TotalCommitted': 30},
                {'DedicatedUsage': 20, 'SharedUsage': 10, 'TotalCommitted': 25}]
        self.assertEqual(parse_adapter_memory(rows), 60)

    def test_missing_negative_bool_or_empty_counter_blocks(self):
        for rows in ([], [{}], [{'DedicatedUsage': -1, 'SharedUsage': 0, 'TotalCommitted': 2}],
                     [{'DedicatedUsage': True, 'SharedUsage': 0, 'TotalCommitted': 2}]):
            with self.assertRaises(ConfigError): parse_adapter_memory(rows)

    def test_stale_future_or_wrong_scope_snapshot_is_not_zero(self):
        good = dict(bytes_used=100, sampled_epoch=100., scope='windows_gpu_adapter_upper_bound', producer_pid=12)
        with patch.object(Path, 'read_text', return_value=json.dumps(good)):
            self.assertEqual(read_gpu_snapshot(Path('synthetic.json'), now=105.), 100)
            for now in (120., 90.):
                with self.assertRaises(ConfigError): read_gpu_snapshot(Path('synthetic.json'), now=now)
        with patch.object(Path, 'read_text', return_value=json.dumps(dict(good, scope='process_only'))):
            with self.assertRaises(ConfigError): read_gpu_snapshot(Path('synthetic.json'), now=105.)
        for value in ([], dict(good, producer_pid=True)):
            with patch.object(Path, 'read_text', return_value=json.dumps(value)):
                with self.assertRaises(ConfigError): read_gpu_snapshot(Path('synthetic.json'), now=105.)

    def test_approved_snapshot_does_not_initialize_torch_or_run_nvidia(self):
        with patch.dict('os.environ', {'JUDGMENT_GPU_MEMORY_SNAPSHOT': 'synthetic.json'}), \
             patch('judgment.gpu_snapshot.read_gpu_snapshot', return_value=500), \
             patch('judgment.runner.subprocess.check_output', side_effect=AssertionError('must not create another GPU context')):
            self.assertEqual(_gpu_memory(123), 500)
