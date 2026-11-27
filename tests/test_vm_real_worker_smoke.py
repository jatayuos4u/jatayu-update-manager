"""Test real-worker VM harness safety gates without calling systemd/APT."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / 'integration'


def load(name):
    with patch.object(sys, 'path', [str(INTEGRATION), *sys.path]):
        # vm_systemd_smoke is an import dependency of the gated VM scripts.
        spec = importlib.util.spec_from_file_location(name, INTEGRATION / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class RealWorkerVmHarnessTests(unittest.TestCase):
    def test_default_is_no_op(self):
        runner = load('vm_real_worker_smoke')
        with patch.object(runner, 'run_case') as real_worker:
            self.assertEqual(runner.main([]), 0)
            real_worker.assert_not_called()

    def test_requires_vm_ack(self):
        runner = load('vm_real_worker_smoke')
        with patch.dict(runner.os.environ, {}, clear=True), \
             patch.object(runner, 'run_case') as real_worker:
            self.assertEqual(runner.main(['--execute']), 2)
            real_worker.assert_not_called()

    def test_service_command_points_only_at_mock_vm_entry(self):
        runner = load('vm_real_worker_smoke')
        command = runner.build_service_command('b'*32, Path('/tmp/isolate'))
        self.assertEqual(command[0], '/usr/bin/systemd-run')
        self.assertIn('vm_mock_transaction_worker.py', command[-4])
        self.assertEqual(command[-2], '/tmp/isolate')
        self.assertEqual(command[-1], '/tmp/isolate/mock-helper')
        self.assertNotIn('privileged-helper', ' '.join(command))
        self.assertNotIn('apt-get', ' '.join(command))
        with self.assertRaises(ValueError):
            runner.build_service_command('../../bad', '/tmp/isolate')

    def test_real_worker_safety_gate_rejects_desktop(self):
        entry = load('vm_mock_transaction_worker')
        with patch.object(entry.os, 'geteuid', return_value=1000), \
             patch.object(entry, 'allowed_vm') as vm:
            with self.assertRaises(RuntimeError):
                entry.main(['b'*32, '/tmp', '/tmp/mock-helper'])
            vm.assert_not_called()

    def test_ci_never_runs_vm_workload(self):
        workflow = (ROOT / '.github/workflows/debian-13-ci.yml').read_text()
        self.assertNotIn('vm_real_worker_smoke.py --execute', workflow)

    def test_mock_adapter_rejects_symlinked_helper(self):
        import tempfile
        entry = load('vm_mock_transaction_worker')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fake = directory / 'real-helper'
            fake.write_text('#!/usr/bin/python3\n')
            fake.chmod(0o700)
            (directory / 'mock-helper').symlink_to(fake)
            with patch.object(entry.os, 'geteuid', return_value=0), \
                 patch.object(entry, 'allowed_vm', return_value=True), \
                 patch.object(entry.supervisor, 'run_worker') as worker, \
                 self.assertRaises(ValueError):
                entry.main(['a'*32, str(directory), str(directory / 'mock-helper')])
            worker.assert_not_called()

    def test_mock_adapter_rejects_symlinked_directory(self):
        import tempfile
        entry = load('vm_mock_transaction_worker')
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / 'real'
            original.mkdir()
            (original / 'mock-helper').write_text('#!/usr/bin/python3\n')
            link = Path(tmp) / 'shortcut'
            link.symlink_to(original, target_is_directory=True)
            with patch.object(entry.os, 'geteuid', return_value=0), \
                 patch.object(entry, 'allowed_vm', return_value=True), \
                 patch.object(entry.supervisor, 'run_worker') as worker, \
                 self.assertRaises(ValueError):
                entry.main(['a'*32, str(link), str(link / 'mock-helper')])
            worker.assert_not_called()

    def test_mock_adapter_rejects_world_readable_directory(self):
        import tempfile
        entry = load('vm_mock_transaction_worker')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            helper = directory / 'mock-helper'
            helper.write_text('#!/usr/bin/python3\n')
            helper.chmod(0o700)
            directory.chmod(0o755)
            with patch.object(entry.os, 'geteuid', return_value=0), \
                 patch.object(entry, 'allowed_vm', return_value=True), \
                 patch.object(entry.supervisor, 'run_worker') as worker, \
                 self.assertRaises(ValueError):
                entry.main(['a'*32, tmp, str(helper)])
            worker.assert_not_called()
