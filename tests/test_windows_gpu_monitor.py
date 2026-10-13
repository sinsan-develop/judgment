"""WDDM의 프로세스별 N/A를 0으로 숨기지 않는 상한 감시."""
import unittest
from unittest.mock import patch
from judgment.runner import _gpu_memory
from judgment.contracts import ConfigError


class WindowsGpuMonitorTests(unittest.TestCase):
    def test_windows_uses_device_total_as_conservative_upper_bound(self):
        with patch('judgment.runner.os.name','nt'),patch('judgment.runner.subprocess.check_output',return_value='2048\n') as query:
            self.assertEqual(_gpu_memory(123),2048*1024**2)
            self.assertIn('--query-gpu=memory.used',query.call_args.args[0])

    def test_unavailable_total_still_blocks(self):
        with patch('judgment.runner.os.name','nt'),patch('judgment.runner.subprocess.check_output',return_value='N/A\n'):
            with self.assertRaisesRegex(ConfigError,'vram_monitor_unavailable'):
                _gpu_memory(123)
