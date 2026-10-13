import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('overlay', Path(__file__).resolve().parents[1] / 'docs/prepare_rocm_overlay.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


class OverlayBoundaryTests(unittest.TestCase):
    def test_wrong_venv_or_runtime_cannot_install_or_create_files(self):
        expected = str(overlay.ROOT / '.work/venv')
        cases = [(expected, expected, (3, 12, 3), '2.13.0+rocm7.2'),
                 ('/other/venv', '/base', (3, 12, 3), '2.13.0+rocm7.2'),
                 (expected, '/base', (3, 14, 0), '2.13.0+rocm7.2'),
                 (expected, '/base', (3, 12, 3), '2.10.0+cu128')]
        for prefix, base, version, torch in cases:
            with patch.object(overlay.sys, 'prefix', prefix), patch.object(overlay.sys, 'base_prefix', base), \
                 patch.object(overlay.sys, 'version_info', version), patch.object(overlay.importlib.metadata, 'version', return_value=torch), \
                 patch.object(overlay.subprocess, 'run') as install, patch.object(Path, 'mkdir') as mkdir:
                with self.assertRaisesRegex(ValueError, 'dedicated_venv|runtime_version'): overlay.run()
                install.assert_not_called(); mkdir.assert_not_called()
