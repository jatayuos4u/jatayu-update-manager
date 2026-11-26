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
            self.assertIn('--property=KillMode=control-group', command)
            self.assertIn('--property=SendSIGKILL=yes', command)
            self.assertIn('--property=StandardInput=null', command)
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

    def test_signal_killed_helper_records_valid_failed_exit(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run', return_value=Mock(returncode=-9)):
            result = s.run_worker('c'*32, 'refresh', '-', directory=tmp)
            record = json.loads(s.status_path('c'*32, tmp).read_text())
            self.assertEqual(result, 137)
            self.assertEqual((record['state'], record['exit_code']), ('failed', 137))
            from jatayu_update_manager.status_reader import read_status
            self.assertEqual(read_status('c'*32, tmp)['exit_code'], 137)

    def test_write_status_rejects_inconsistent_terminal_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = [('completed', 1), ('failed', 0), ('running', 0),
                   ('failed', -9), ('failed', 256), ('failed', None)]
            for state, code in bad:
                with self.subTest(state=state, code=code), self.assertRaises(ValueError):
                    s.write_status('d'*32, 'refresh', state, code, tmp)

    def test_trusted_directory_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'target'
            target.mkdir()
            link = Path(tmp) / 'link'
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(OSError):
                s.verify_trusted_directory(link)

    def test_trusted_directory_rejects_world_writable_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / 'parent'
            parent.mkdir()
            parent.chmod(0o777)
            with self.assertRaises(OSError):
                s.verify_trusted_directory(parent)

    def test_production_parent_chain_fails_before_state_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / 'parent'
            parent.mkdir()
            parent.chmod(0o777)
            fake_state = parent / 'transactions'
            with patch.object(s, 'STATE_DIR', fake_state), \
                 self.assertRaises(OSError):
                s.prepare_state_directory(fake_state)
            self.assertFalse(fake_state.exists())

    def test_nonproduction_test_directory_does_not_check_host_ancestors(self):
        with tempfile.TemporaryDirectory() as tmp:
            testdir = Path(tmp) / 'isolated'
            self.assertEqual(s.prepare_state_directory(testdir), testdir)
            self.assertTrue(testdir.is_dir())

    def test_root_owned_private_parent_is_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            rootdir = Path(tmp) / 'trusted'
            rootdir.mkdir(mode=0o700)
            if os.geteuid() == 0:
                self.assertEqual(s.verify_trusted_directory(rootdir), rootdir)
            else:
                self.skipTest('Root-only ownership check')

    def test_fresh_install_creates_trusted_state_parent(self):
        if os.geteuid() != 0:
            self.skipTest('Creating root-owned production-style state requires root')
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / 'jatayu-update-manager'
            target = parent / 'transactions'
            self.assertFalse(parent.exists())
            trusted_check = s.verify_trusted_directory
            # The CI host's /tmp is intentionally world-writable; mock
            # its ancestors as trusted while checking the actual test tree.
            def check_test_component(component):
                if component == Path(tmp) or Path(tmp) in component.parents:
                    return trusted_check(component)
                return component
            with patch.object(s, 'STATE_DIR', target), \
                 patch.object(s, 'verify_trusted_directory', side_effect=check_test_component):
                result = s.prepare_state_directory(target)
            self.assertEqual(result, target)
            self.assertTrue(parent.is_dir())
            self.assertEqual(parent.stat().st_uid, 0)
            self.assertFalse(parent.stat().st_mode & 0o022)

    def test_service_launch_cannot_use_process_kill_mode(self):
        """Reject regressions that would orphan APT descendants on stop."""
        from unittest.mock import Mock
        with patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run', return_value=Mock(returncode=0)) as runner:
            s.start_supervised('upgrade', 'a' * 64)
        argv = runner.call_args.args[0]
        self.assertNotIn('--property=KillMode=process', argv)
        self.assertNotIn('--property=KillMode=none', argv)
        self.assertEqual(argv.count('--property=KillMode=control-group'), 1)
        self.assertIn('--property=SendSIGKILL=yes', argv)
        self.assertEqual(argv[argv.index('--')+1], s.WORKER)

    def test_stale_running_transaction_blocks_new_worker_across_ids(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run') as runner:
            s.write_status('a'*32, 'upgrade', 'running', directory=tmp)
            code = s.run_worker('b'*32, 'refresh', '-', directory=tmp)
            self.assertEqual(code, s.UNRESOLVED_EXIT)
            runner.assert_not_called()
            previous = json.loads(s.status_path('a'*32, tmp).read_text())
            current = json.loads(s.status_path('b'*32, tmp).read_text())
            self.assertEqual(previous['state'], 'running')
            self.assertEqual((current['state'], current['exit_code']),
                             ('failed', s.UNRESOLVED_EXIT))

    def test_finished_previous_transaction_allows_new_worker(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run', return_value=Mock(returncode=0)) as runner:
            s.write_status('a'*32, 'refresh', 'completed', 0, directory=tmp)
            self.assertEqual(s.run_worker('b'*32, 'refresh', '-', directory=tmp), 0)
            runner.assert_called_once()
            current = json.loads(s.status_path('b'*32, tmp).read_text())
            self.assertEqual(current['state'], 'completed')

    def test_malformed_journal_blocks_new_worker(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run') as runner:
            (Path(tmp) / ('a'*32+'.json')).write_text('invalid-json')
            self.assertEqual(s.run_worker('b'*32, 'refresh', '-', directory=tmp),
                             s.UNRESOLVED_EXIT)
            runner.assert_not_called()

    def test_symlinked_journal_blocks_new_worker(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run') as runner:
            victim = Path(tmp) / 'unrelated'
            victim.write_text('unrelated')
            (Path(tmp) / ('a'*32+'.json')).symlink_to(victim)
            self.assertEqual(s.run_worker('b'*32, 'refresh', '-', directory=tmp),
                             s.UNRESOLVED_EXIT)
            runner.assert_not_called()
            self.assertEqual(victim.read_text(), 'unrelated')

    def test_duplicate_transaction_id_is_refused_without_helper(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(s.os, 'geteuid', return_value=0), \
             patch.object(s.subprocess, 'run') as runner:
            s.write_status('a'*32, 'refresh', 'running', directory=tmp)
            self.assertEqual(s.run_worker('a'*32, 'refresh', '-', directory=tmp),
                             s.UNRESOLVED_EXIT)
            runner.assert_not_called()
            self.assertEqual(json.loads(s.status_path('a'*32, tmp).read_text())['state'],
                             'failed')

    def test_journal_record_count_limit_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(s, 'MAX_TRANSACTION_RECORDS', 1):
                s.write_status('a'*32, 'refresh', 'completed', 0, directory=tmp)
                s.write_status('b'*32, 'refresh', 'completed', 0, directory=tmp)
                with self.assertRaises(RuntimeError):
                    s.ensure_no_unresolved_transactions(tmp)
