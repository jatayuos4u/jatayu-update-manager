"""Mocked detection tests; never install packages."""
import unittest
from unittest.mock import MagicMock, Mock, patch
from jatayu_update_manager import core


class AvailableUpdatesTests(unittest.TestCase):
    def test_kernel_dependency_and_metapackage_are_both_listed(self):
        pkgs = {
            'linux-image-6.12.118+deb13-amd64':
                Mock(installed=None, candidate=Mock(version='6.12.118-1')),
            'linux-image-amd64':
                Mock(installed=Mock(version='6.12.111-1'),
                     candidate=Mock(version='6.12.118-1')),
        }
        cache = MagicMock()
        cache.__contains__.side_effect = lambda name: name in pkgs
        cache.__getitem__.side_effect = lambda name: pkgs[name]
        plan = ('Inst linux-image-6.12.118+deb13-amd64 (6.12.118-1 Debian)\n'
                'Inst linux-image-amd64 [6.12.111-1] (6.12.118-1 Debian)\n'
                'Conf linux-image-amd64 (6.12.118-1 Debian)\n')
        with patch.object(core.subprocess, 'run',
                          return_value=Mock(returncode=0, stdout=plan, stderr='')) as runner, \
             patch.object(core.apt, 'Cache', return_value=cache):
            result = core.available_updates()
        self.assertEqual(result, [
            ('linux-image-6.12.118+deb13-amd64', '—', '6.12.118-1'),
            ('linux-image-amd64', '6.12.111-1', '6.12.118-1')])
        self.assertEqual(runner.call_args.args[0],
            ['/usr/bin/apt-get', '-s', '--with-new-pkgs', '--no-remove', 'upgrade'])

    def test_empty_upgrade_plan(self):
        with patch.object(core.subprocess, 'run', return_value=Mock(
                 returncode=0, stdout='0 upgraded, 0 newly installed\n', stderr='')), \
             patch.object(core.apt, 'Cache') as cache:
            self.assertEqual(core.available_updates(), [])
            cache.assert_not_called()

    def test_simulation_failure_is_not_reported_as_no_updates(self):
        with patch.object(core.subprocess, 'run', return_value=Mock(
                returncode=100, stdout='', stderr='broken dependencies')):
            with self.assertRaisesRegex(RuntimeError, 'simulation failed'):
                core.available_updates()

    def test_removal_plan_is_rejected(self):
        with patch.object(core.subprocess, 'run', return_value=Mock(
                returncode=0, stdout='Inst foo (2)\nRemv bar [1]\n', stderr='')):
            with self.assertRaisesRegex(RuntimeError, 'removals'):
                core.available_updates()

    def test_preview_is_bounded(self):
        with patch.object(core.subprocess, 'run', return_value=Mock(
                returncode=0, stdout='X'*(core.MAX_PREVIEW+1), stderr='')):
            with self.assertRaisesRegex(RuntimeError, 'output limit'):
                core.available_updates()
