"""Mock-only preflight for isolated systemd harness. Does not run systemd."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'integration/vm_systemd_smoke.py'


def load():
    spec = importlib.util.spec_from_file_location('vm_smoke', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VmSmokeTests(unittest.TestCase):
    def test_default_dry_run(self):
        module = load()
        with patch.object(module, 'run_smoke') as worker:
            self.assertEqual(module.main([]), 0)
            worker.assert_not_called()

    def test_requires_explicit_ack(self):
        module = load()
        with patch.dict(module.os.environ, {}, clear=True), \
             patch.object(module, 'run_smoke') as worker:
            self.assertEqual(module.main(['--execute']), 2)
            worker.assert_not_called()

    def test_rejects_unprivileged_or_non_vm(self):
        module = load()
        with patch.object(module.os, 'geteuid', return_value=1000):
            with self.assertRaises(RuntimeError):
                module.run_smoke()
        with patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module, 'allowed_vm', return_value=False):
            with self.assertRaises(RuntimeError):
                module.run_smoke()

    def test_fixed_mock_command_never_invokes_apt(self):
        module = load()
        argv = module.service_command('jatayu-mock-smoke-' + 'a'*32, '/tmp/mock')
        self.assertEqual(argv[0], '/usr/bin/systemd-run')
        self.assertIn('--property=User=root', argv)
        self.assertIn('write_text("finished"', argv[-2])
        self.assertNotIn('/usr/bin/apt', ' '.join(argv))
        self.assertNotIn('/usr/bin/dpkg', ' '.join(argv))
        with self.assertRaises(ValueError):
            module.service_command('jatayu-update-' + 'a'*32, '/tmp/mock')

    def test_ci_never_runs_live_vm_test(self):
        workflow = (ROOT / '.github/workflows/debian-13-ci.yml').read_text()
        self.assertNotIn('vm_systemd_smoke.py --execute', workflow)
