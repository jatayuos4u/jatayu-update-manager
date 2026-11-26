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
             patch.object(handoff, 'write_handoff',
                          side_effect=lambda uid, ident, state: events.append(state)), \
             patch.object(supervisor.subprocess, 'run', return_value=Mock(returncode=0)) as launch:
            ident = supervisor.start_supervised('refresh', owner_uid=1000)
            self.assertEqual(len(ident), 32)
            self.assertEqual(events, ['pending', 'submitted'])
            launch.assert_called_once()

    def test_unknown_launch_keeps_recovery_locator(self):
        with patch.object(supervisor.os, 'geteuid', return_value=0), \
             patch.object(handoff, 'write_handoff') as track, \
             patch.object(supervisor.subprocess, 'run', side_effect=OSError('no service')):
            with self.assertRaises(OSError):
                supervisor.start_supervised('refresh', owner_uid=1000)
            self.assertEqual([call.args[2] for call in track.call_args_list],
                             ['pending', 'launch_unknown'])
