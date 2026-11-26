"""No APT or systemd: root-owned handoff recovery and validation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jatayu_update_manager import handoff
from jatayu_update_manager import supervisor


class HandoffTests(unittest.TestCase):
    def test_atomic_handoff_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handoff.os, 'geteuid', return_value=0):
            handoff.write_handoff(1000, 'a'*32, 'pending', tmp)
            handoff.write_handoff(1000, 'a'*32, 'submitted', tmp)
            self.assertEqual(handoff.read_handoff(1000, tmp),
                             {'uid': 1000, 'id': 'a'*32, 'phase': 'submitted'})
            self.assertFalse(list(Path(tmp).glob('.handoff-*')))

    def test_handoff_rejects_wrong_account(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handoff.os, 'geteuid', return_value=0):
            handoff.write_handoff(1000, 'a'*32, 'pending', tmp)
            with self.assertRaises(FileNotFoundError):
                handoff.read_handoff(1001, tmp)

    def test_handoff_refuses_symlink_and_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = handoff.handoff_path(1000, tmp)
            destination = Path(tmp)/'target'
            destination.write_text('{}')
            location.symlink_to(destination)
            with self.assertRaises(OSError):
                handoff.read_handoff(1000, tmp)
            location.unlink()
            location.write_text(json.dumps({'uid': 2000, 'id': 'a'*32,
                                           'phase': 'submitted'}))
            with self.assertRaises(ValueError):
                handoff.read_handoff(1000, tmp)

    def test_root_required_to_write_handoff(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handoff.os, 'geteuid', return_value=1000):
            with self.assertRaises(PermissionError):
                handoff.write_handoff(1000, 'a'*32, 'pending', tmp)

    def test_start_records_pending_before_launch_and_submitted_after(self):
        events = []
        from unittest.mock import Mock
        with patch.object(supervisor.os, 'geteuid', return_value=0), \
             patch.object(handoff, 'handoff_launch_lock', return_value=__import__('contextlib').nullcontext()), \
             patch.object(handoff, 'ensure_no_unresolved_handoff'), \
             patch.object(handoff, 'write_handoff',
                          side_effect=lambda uid, ident, state: events.append(state)), \
             patch.object(supervisor.subprocess, 'run', return_value=Mock(returncode=0)) as launch:
            ident = supervisor.start_supervised('refresh', owner_uid=1000)
            self.assertEqual(len(ident), 32)
            self.assertEqual(events, ['pending', 'submitted'])
            launch.assert_called_once()

    def test_unknown_launch_keeps_recovery_locator(self):
        with patch.object(supervisor.os, 'geteuid', return_value=0), \
             patch.object(handoff, 'handoff_launch_lock', return_value=__import__('contextlib').nullcontext()), \
             patch.object(handoff, 'ensure_no_unresolved_handoff'), \
             patch.object(handoff, 'write_handoff') as track, \
             patch.object(supervisor.subprocess, 'run', side_effect=OSError('no service')):
            with self.assertRaises(OSError):
                supervisor.start_supervised('refresh', owner_uid=1000)
            self.assertEqual([call.args[2] for call in track.call_args_list],
                             ['pending', 'launch_unknown'])

    def test_pending_handoff_blocks_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handoff.os, 'geteuid', return_value=0):
            handoff.write_handoff(1000, 'a'*32, 'pending', tmp)
            with self.assertRaises(RuntimeError):
                with patch('jatayu_update_manager.status_reader.check_worker_unit',
                       return_value='inactive'):
                handoff.ensure_no_unresolved_handoff(1000, tmp)
            self.assertEqual(handoff.read_handoff(1000, tmp)['id'], 'a'*32)

    def test_completed_handoff_allows_next_launch(self):
        from jatayu_update_manager.supervisor import write_status
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handoff.os, 'geteuid', return_value=0):
            handoff.write_handoff(1000, 'a'*32, 'submitted', tmp)
            write_status('a'*32, 'refresh', 'completed', 0, directory=tmp)
            handoff.ensure_no_unresolved_handoff(1000, tmp)

    def test_unresolved_handoff_blocks_service_launch(self):
        with patch.object(supervisor.os, 'geteuid', return_value=0), \
             patch.object(handoff, 'handoff_launch_lock',
                          return_value=__import__('contextlib').nullcontext()), \
             patch.object(handoff, 'ensure_no_unresolved_handoff',
                          side_effect=RuntimeError('unresolved')), \
             patch.object(supervisor.subprocess, 'run') as runner:
            with self.assertRaises(RuntimeError):
                supervisor.start_supervised('refresh', owner_uid=1000)
            runner.assert_not_called()

    def test_singleflight_handoff_lock_acquired_and_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            with handoff.handoff_launch_lock(1000, tmp):
                with self.assertRaises(BlockingIOError):
                    with handoff.handoff_launch_lock(1000, tmp):
                        pass
            with handoff.handoff_launch_lock(1000, tmp):
                pass

    def test_terminal_record_but_active_unit_blocks_overwrite(self):
        from jatayu_update_manager.supervisor import write_status
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handoff.os, 'geteuid', return_value=0):
            handoff.write_handoff(1000, 'e'*32, 'submitted', tmp)
            write_status('e'*32, 'refresh', 'completed', 0, directory=tmp)
            for state in ('active', 'unknown'):
                with self.subTest(service=state), \
                     patch('jatayu_update_manager.status_reader.check_worker_unit',
                           return_value=state), \
                     self.assertRaises(RuntimeError):
                    handoff.ensure_no_unresolved_handoff(1000, tmp)

    def test_terminal_record_and_inactive_unit_allows_new_request(self):
        from jatayu_update_manager.supervisor import write_status
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handoff.os, 'geteuid', return_value=0):
            handoff.write_handoff(1000, 'f'*32, 'submitted', tmp)
            write_status('f'*32, 'refresh', 'failed', 100, directory=tmp)
            with patch('jatayu_update_manager.status_reader.check_worker_unit',
                       return_value='inactive'):
                handoff.ensure_no_unresolved_handoff(1000, tmp)
