"""Tests of dedicated per-user recovery lookup without real pkexec."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'helper' / 'recovery-lookup'


def load():
    spec = importlib.util.spec_from_loader('recovery_lookup', SourceFileLoader('recovery_lookup', str(PATH)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RecoveryLookupTests(unittest.TestCase):
    def test_only_own_pkexec_uid_is_looked_up(self):
        app = load()
        with patch.object(app.os, 'geteuid', return_value=0), \
             patch.dict(app.os.environ, {'PKEXEC_UID': '1000'}), \
             patch.object(app, 'read_handoff',
                          return_value={'id': 'a'*32, 'uid': 1000, 'phase': 'submitted'}) as reader, \
             patch('builtins.print') as print_line:
            self.assertEqual(app.main([]), 0)
            reader.assert_called_once_with(1000)
            print_line.assert_called_once_with('RECOVERY_ID=' + 'a'*32, flush=True)

    def test_rejects_user_supplied_ids_and_paths(self):
        app = load()
        with patch.object(app.os, 'geteuid', return_value=0), \
             patch.object(app, 'read_handoff') as reader:
            self.assertEqual(app.main(['1001']), 2)
            self.assertEqual(app.main(['../../root']), 2)
            reader.assert_not_called()

    def test_no_root_or_missing_identity_fails_closed(self):
        app = load()
        with patch.object(app.os, 'geteuid', return_value=1000), \
             patch.object(app, 'read_handoff') as reader:
            self.assertEqual(app.main([]), 1)
            reader.assert_not_called()
        with patch.object(app.os, 'geteuid', return_value=0), \
             patch.dict(app.os.environ, {}, clear=True), \
             patch.object(app, 'read_handoff') as reader:
            self.assertEqual(app.main([]), 3)
            reader.assert_not_called()

    def test_corrupt_private_handoff_not_disclosed(self):
        app = load()
        with patch.object(app.os, 'geteuid', return_value=0), \
             patch.dict(app.os.environ, {'PKEXEC_UID': '1000'}), \
             patch.object(app, 'read_handoff', side_effect=ValueError('malformed')):
            self.assertEqual(app.main([]), 3)

    def test_policy_bound_to_exact_recovery_executable(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring((PATH.parents[1] / 'polkit/in.jatayuos.update-manager.recover.policy').read_text())
        actions = root.findall('action')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].attrib['id'], 'in.jatayuos.update-manager.recover')
        self.assertEqual(root.find('.//annotate').text,
                         '/usr/lib/jatayu-update-manager/recovery-lookup')
        defaults = root.find('.//defaults')
        self.assertEqual([defaults.find(key).text for key in ('allow_any','allow_inactive','allow_active')],
                         ['no','no','auth_admin'])
