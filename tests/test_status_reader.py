"""Read-only status retrieval, tamper handling and recovery classification."""
import json
from pathlib import Path
import tempfile
import unittest

from jatayu_update_manager import status_reader as s
from jatayu_update_manager.supervisor import write_status


class StatusReaderTests(unittest.TestCase):
    def test_completed_record_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            identifier = 'a' * 32
            write_status(identifier, 'refresh', 'completed', 0, directory=tmp)
            status = s.read_status(identifier, directory=tmp)
            self.assertEqual(status['id'], identifier)
            self.assertEqual(s.classify_status(status), 'completed')

    def test_reject_invalid_transaction_identifier(self):
        with self.assertRaises(s.InvalidStatus):
            s.read_status('../arbitrary')

    def test_symlink_record_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            identifier = 'b' * 32
            target = Path(tmp) / 'target'
            target.write_text('{}')
            (Path(tmp) / (identifier + '.json')).symlink_to(target)
            with self.assertRaises(OSError):
                s.read_status(identifier, directory=tmp)

    def test_oversized_record_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            identifier = 'b' * 32
            (Path(tmp) / (identifier + '.json')).write_bytes(b' ' * (s.MAX_STATUS_BYTES + 1))
            with self.assertRaises(s.InvalidStatus):
                s.read_status(identifier, directory=tmp)

    def test_invalid_record_identity_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            identifier = 'a' * 32
            write_status(identifier, 'refresh', 'running', directory=tmp)
            path = Path(tmp) / (identifier + '.json')
            record = json.loads(path.read_text())
            record['id'] = 'b' * 32
            path.write_text(json.dumps(record))
            with self.assertRaises(s.InvalidStatus):
                s.read_status(identifier, directory=tmp)

    def test_interrupted_after_reboot_is_not_reported_success(self):
        record = {'state': 'running', 'boot_id': 'a' * 36}
        self.assertEqual(s.classify_status(record, 'b' * 36), 'interrupted_unknown')

    def test_same_boot_running_is_unverified(self):
        record = {'state': 'running', 'boot_id': 'a' * 36}
        self.assertEqual(s.classify_status(record, 'a' * 36), 'running_unverified')

    def test_missing_boot_id_never_claims_crash_or_completion(self):
        record = {'state': 'running', 'boot_id': 'unavailable'}
        self.assertEqual(s.classify_status(record, 'b' * 36), 'running_unverified')

    def test_world_writable_record_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            identifier = 'a' * 32
            write_status(identifier, 'refresh', 'completed', 0, directory=tmp)
            path = Path(tmp) / (identifier + '.json')
            path.chmod(0o666)
            with self.assertRaises(s.InvalidStatus):
                s.read_status(identifier, directory=tmp)

    def test_failed_status_not_reclassified(self):
        with tempfile.TemporaryDirectory() as tmp:
            identifier = 'c' * 32
            write_status(identifier, 'upgrade', 'failed', 75, directory=tmp)
            self.assertEqual(s.classify_status(s.read_status(identifier, tmp)), 'failed')

    def test_systemd_unit_active_only_for_expected_worker(self):
        from unittest.mock import Mock
        from jatayu_update_manager.supervisor import WORKER
        identifier = 'a' * 32
        stdout = ('LoadState=loaded\nActiveState=active\n'
                  'ExecStart={ path=' + WORKER + ' ; argv[]=' + WORKER
                  + ' ' + identifier + ' refresh - ; }\n').encode()
        runner = Mock(return_value=Mock(returncode=0, stdout=stdout))
        self.assertEqual(s.check_worker_unit(identifier, runner), 'active')
        self.assertEqual(runner.call_args.args[0][-1],
                         'jatayu-update-' + identifier + '.service')

    def test_systemd_unknown_when_unit_executable_differs(self):
        from unittest.mock import Mock
        identifier = 'a' * 32
        stdout = ('LoadState=loaded\nActiveState=active\n'
                  'ExecStart={ path=/bin/false ; argv[]=/bin/false '
                  + identifier + ' ; }\n').encode()
        runner = Mock(return_value=Mock(returncode=0, stdout=stdout))
        self.assertEqual(s.check_worker_unit(identifier, runner), 'unknown')

    def test_systemd_unavailable_does_not_claim_interrupted(self):
        from unittest.mock import Mock
        identifier = 'a' * 32
        runner = Mock(side_effect=OSError('unavailable'))
        self.assertEqual(s.check_worker_unit(identifier, runner), 'unknown')
        record = {'state': 'running', 'boot_id': 'a' * 36}
        self.assertEqual(s.reconcile_status(identifier, record,
                         unit_state='unknown', current_boot='a' * 36), 'running_unverified')

    def test_stale_running_and_inactive_unit_is_unknown_outcome(self):
        identifier = 'a' * 32
        record = {'state': 'running', 'boot_id': 'a' * 36}
        self.assertEqual(s.reconcile_status(identifier, record,
                         unit_state='inactive', current_boot='a' * 36), 'interrupted_unknown')

    def test_active_unit_confirms_worker_not_upgrade_success(self):
        identifier = 'a' * 32
        record = {'state': 'running', 'boot_id': 'a' * 36}
        self.assertEqual(s.reconcile_status(identifier, record,
                         unit_state='active', current_boot='a' * 36), 'running_confirmed')
