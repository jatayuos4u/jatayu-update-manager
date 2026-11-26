"""No real APT invocation: supervised backend behavior tests."""
import fcntl
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from jatayu_update_manager import supervisor as s


class SupervisorTests(unittest.TestCase):
    def test_request_allowlist(self):
        transaction = 'a' * 32
        s.validate_request(transaction, 'refresh', '-')
        s.validate_request(transaction, 'upgrade', 'b' * 64)
        for action, digest in (('shell', '-'), ('refresh', 'b' * 64), ('upgrade', '-')):
            with self.assertRaises(ValueError):
                s.validate_request(transaction, action, digest)
        with self.assertRaises(ValueError):
            s.validate_request('../bad', 'refresh', '-')

    def test_status_record_atomic_final_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            transaction = 'a' * 32
            s.write_status(transaction, 'refresh', 'running', directory=tmp)
            final = s.write_status(transaction, 'refresh', 'completed', 0, directory=tmp)
            self.assertEqual(json.loads(s.status_path(transaction, tmp).read_text()), final)
            self.assertEqual(s.status_path(transaction, tmp).stat().st_mode & 0o777, 0o644)
            self.assertFalse(list(Path(tmp).glob('*.tmp')))

    def test_status_rejects_symlink_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / 'real'
            real.mkdir()
            link = Path(tmp) / 'link'
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(OSError):
                s.write_status('a' * 32, 'refresh', 'running', directory=link)

    def test_root_worker_failure_status_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run', return_value=Mock(returncode=100)) as runner:
            code = s.run_worker('a' * 32, 'refresh', '-', directory=tmp)
            self.assertEqual(code, 100)
            status = json.loads(s.status_path('a' * 32, tmp).read_text())
            self.assertEqual((status['state'], status['exit_code']), ('failed', 100))
            self.assertEqual(runner.call_args.args[0], [s.HELPER, 'refresh'])

    def test_unprivileged_worker_rejected(self):
        with patch.object(s.os, 'geteuid', return_value=1000):
            with self.assertRaises(PermissionError):
                s.run_worker('a' * 32, 'refresh', '-')

    def test_supervised_start_requires_root(self):
        with patch.object(s.os, 'geteuid', return_value=1000):
            with self.assertRaises(PermissionError):
                s.start_supervised('refresh')

    def test_supervised_start_uses_fixed_argv_without_shell(self):
        with patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run', return_value=Mock(returncode=0)) as runner:
            transaction = s.start_supervised('refresh')
            command = runner.call_args.args[0]
            self.assertEqual(command[0], '/usr/bin/systemd-run')
            self.assertIn('--system', command)
            self.assertIn(s.WORKER, command)
            self.assertEqual(command[-3:], [transaction, 'refresh', '-'])
            self.assertTrue(runner.call_args.kwargs['check'])

    def test_singleflight_lock_releases_after_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with s.single_transaction(tmp) as acquired:
                self.assertTrue(acquired)
            with s.single_transaction(tmp) as acquired:
                self.assertTrue(acquired)

    def test_two_workers_cannot_overlap(self):
        """Cross-process flock proof; never starts real APT."""
        with tempfile.TemporaryDirectory() as tmp:
            with s.single_transaction(tmp) as first:
                self.assertTrue(first)
                # Mock worker root check; second process is distinct.
                code = (
                    'import sys; '
                    'from jatayu_update_manager import supervisor as s; '
                    'with_lock = s.single_transaction(sys.argv[1]); '
                    'value = with_lock.__enter__(); print(value, flush=True); '
                    'with_lock.__exit__(None, None, None)'
                )
                env = dict(os.environ)
                # Existing test runner runs with PYTHONPATH=src.
                result = subprocess.run(
                    ['/usr/bin/python3', '-c', code, tmp],
                    capture_output=True, text=True, timeout=5, env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), 'False')
            with s.single_transaction(tmp) as released:
                self.assertTrue(released)

    def test_busy_worker_never_invokes_helper(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run') as runner:
            with s.single_transaction(tmp):
                code = s.run_worker('b' * 32, 'refresh', '-', directory=tmp)
            self.assertEqual(code, s.BUSY_EXIT)
            runner.assert_not_called()
            record = json.loads(s.status_path('b' * 32, tmp).read_text())
            self.assertEqual((record['state'], record['exit_code']), ('failed', s.BUSY_EXIT))

    def test_status_has_boot_and_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = s.write_status('a' * 32, 'refresh', 'running', directory=tmp)
            self.assertIn('boot_id', data)
            self.assertIn('updated_utc', data)

    def test_unsafe_world_writable_status_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'unsafe'
            directory.mkdir(mode=0o777)
            directory.chmod(0o777)
            with self.assertRaises(OSError):
                s.write_status('a' * 32, 'refresh', 'running', directory=directory)
