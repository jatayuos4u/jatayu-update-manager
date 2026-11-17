import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import pathlib
import subprocess
import unittest
from unittest.mock import patch, Mock

from jatayu_update_manager.transaction import parse_simulation, SimulationError

HELPER_PATH = pathlib.Path(__file__).resolve().parents[1] / 'helper' / 'privileged-helper'

def load_helper():
    spec = importlib.util.spec_from_loader('jatayu_privileged_helper', SourceFileLoader('jatayu_privileged_helper', str(HELPER_PATH)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class SimulationTests(unittest.TestCase):
    def test_install_plan_digest_is_stable(self):
        x = parse_simulation('Reading package lists...\nInst foo [1] (2 Debian)\nConf foo (2 Debian)\n')
        self.assertEqual(len(x.installs), 1)
        self.assertEqual(len(x.digest), 64)

    def test_plan_changes_digest(self):
        x = parse_simulation('Inst foo [1] (2 Debian)\nConf foo (2 Debian)\n')
        y = parse_simulation('Inst foo [1] (3 Debian)\nConf foo (3 Debian)\n')
        self.assertNotEqual(x.digest, y.digest)

    def test_removal_is_blocked(self):
        with self.assertRaises(SimulationError):
            parse_simulation('Inst foo [1] (2 Debian)\nRemv bar [1]\n')

    def test_empty_plan_is_blocked(self):
        with self.assertRaises(SimulationError):
            parse_simulation('0 upgraded, 0 newly installed, 0 to remove')

class PrivilegeTests(unittest.TestCase):
    def test_unprivileged_execution_rejected(self):
        helper = load_helper()
        with patch.object(helper.os, 'geteuid', return_value=1000):
            self.assertEqual(helper.main(['refresh']), 1)

    def test_invalid_args_rejected_as_root(self):
        helper = load_helper()
        with patch.object(helper.os, 'geteuid', return_value=0):
            self.assertEqual(helper.main(['upgrade', 'bad']), 2)
            self.assertEqual(helper.main(['something-else']), 2)

    def test_changed_plan_rejected_without_running_upgrade(self):
        helper = load_helper()
        with patch.object(helper.os, 'geteuid', return_value=0), \
             patch.object(helper, 'preview', return_value=parse_simulation('Inst a [1] (2)\n')), \
             patch.object(helper.subprocess, 'run') as runner:
            self.assertEqual(helper.main(['upgrade', '0'*64]), 4)
            runner.assert_not_called()

    def test_apparently_valid_upgrade_uses_fixed_argv(self):
        helper = load_helper()
        preview = parse_simulation('Inst a [1] (2)\n')
        with patch.object(helper.os, 'geteuid', return_value=0), \
             patch.object(helper, 'preview', return_value=preview), \
             patch.object(helper.subprocess, 'run', return_value=Mock(returncode=0)) as runner:
            self.assertEqual(helper.main(['upgrade', preview.digest]), 0)
            cmd = runner.call_args.args[0]
            self.assertEqual(cmd[0], '/usr/bin/apt-get')
            self.assertIn('--no-remove', cmd)
            self.assertEqual(runner.call_args.kwargs.get('cwd'), '/')
            self.assertEqual(runner.call_args.kwargs.get('env'), helper.ENV)
