"""Privileged supervised launcher: no real systemd or APT calls."""
import importlib.util
from importlib.machinery import SourceFileLoader
import pathlib
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / 'helper' / 'supervised-launcher'


def load_launcher():
    spec = importlib.util.spec_from_loader(
        'jatayu_supervised_launcher',
        SourceFileLoader('jatayu_supervised_launcher', str(LAUNCHER_PATH)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LauncherTests(unittest.TestCase):
    def test_only_exact_refresh_or_hex_upgrade_allowed(self):
        launcher = load_launcher()
        self.assertEqual(launcher.validate_args(['refresh']), ('refresh', '-'))
        self.assertEqual(launcher.validate_args(['upgrade', 'a' * 64]), ('upgrade', 'a' * 64))
        for args in ([], ['upgrade'], ['refresh', 'extra'], ['shell'],
                     ['upgrade', 'A' * 64], ['upgrade', '../../etc/passwd'],
                     ['upgrade', 'a' * 63], ['upgrade', 'a' * 64, '--property=User=root']):
            with self.subTest(args=args), self.assertRaises(ValueError):
                launcher.validate_args(args)

    def test_no_privilege_cannot_start_transaction(self):
        launcher = load_launcher()
        with patch.object(launcher.os, 'geteuid', return_value=1000), \
             patch.object(launcher, 'start_supervised') as runner:
            self.assertEqual(launcher.main(['refresh']), 1)
            runner.assert_not_called()

    def test_invalid_request_never_launches_service(self):
        launcher = load_launcher()
        with patch.object(launcher.os, 'geteuid', return_value=0), \
             patch.object(launcher, 'start_supervised') as runner:
            self.assertEqual(launcher.main(['upgrade', '--shell']), 2)
            runner.assert_not_called()

    def test_authorized_launch_emits_only_transaction_locator(self):
        launcher = load_launcher()
        with patch.object(launcher.os, 'geteuid', return_value=0), \
             patch.dict(launcher.os.environ, {'PKEXEC_UID': '1000'}), \
             patch.object(launcher, 'start_supervised', return_value='b' * 32) as runner, \
             patch('builtins.print') as output:
            self.assertEqual(launcher.main(['upgrade', 'c' * 64]), 0)
            runner.assert_called_once_with('upgrade', 'c' * 64, owner_uid=1000)
            output.assert_called_once_with('TRANSACTION_ID=' + 'b' * 32, flush=True)

    def test_failed_systemd_launch_is_not_reported_success(self):
        launcher = load_launcher()
        with patch.object(launcher.os, 'geteuid', return_value=0), \
             patch.object(launcher, 'start_supervised', side_effect=OSError('service failed')):
            self.assertEqual(launcher.main(['refresh']), 3)

    def test_polkit_policy_is_tied_to_dedicated_installed_executable(self):
        import xml.etree.ElementTree as ET
        xml = (ROOT / 'polkit/in.jatayuos.update-manager.supervised.policy').read_text()
        root = ET.fromstring(xml)
        actions = root.findall('action')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].attrib['id'], 'in.jatayuos.update-manager.supervised')
        self.assertEqual(root.find('.//annotate').text,
                         '/usr/lib/jatayu-update-manager/supervised-launcher')
        defaults = root.find('.//defaults')
        self.assertEqual(defaults.find('allow_any').text, 'no')
        self.assertEqual(defaults.find('allow_inactive').text, 'no')
        self.assertEqual(defaults.find('allow_active').text, 'auth_admin')
        rules = (ROOT / 'debian/rules').read_text()
        self.assertIn('helper/supervised-launcher', rules)
        self.assertIn('in.jatayuos.update-manager.supervised.policy', rules)

    def test_missing_caller_identity_rejects_launch(self):
        launcher = load_launcher()
        with patch.object(launcher.os, 'geteuid', return_value=0), \
             patch.dict(launcher.os.environ, {}, clear=True), \
             patch.object(launcher, 'start_supervised') as runner:
            self.assertEqual(launcher.main(['refresh']), 3)
            runner.assert_not_called()

    def test_unresolved_handoff_gives_safe_error(self):
        launcher = load_launcher()
        with patch.object(launcher.os, 'geteuid', return_value=0), \
             patch.dict(launcher.os.environ, {'PKEXEC_UID': '1000'}), \
             patch.object(launcher, 'start_supervised',
                          side_effect=RuntimeError('previous transaction unresolved')):
            self.assertEqual(launcher.main(['refresh']), 3)
