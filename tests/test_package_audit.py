"""Isolated package-audit behavior: no real system package is installed."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageAuditSourceTests(unittest.TestCase):
    def test_workflow_audits_the_actual_built_deb(self):
        workflow = (ROOT / '.github/workflows/debian-13-ci.yml').read_text()
        self.assertIn('scripts/audit_deb.py ../jatayu-update-manager_1.2.3~alpha21-1_all.deb', workflow)
        self.assertIn('dpkg-buildpackage -us -uc -b', workflow)
        self.assertLess(workflow.index('dpkg-buildpackage -us -uc -b'),
                        workflow.index('scripts/audit_deb.py ../jatayu-update-manager_1.2.3~alpha21-1_all.deb'))

    def test_packaged_policy_helpers_in_rules(self):
        rules = (ROOT / 'debian/rules').read_text()
        for helper in ('privileged-helper', 'supervised-launcher', 'recovery-lookup'):
            self.assertIn('install -m 755 helper/' + helper, rules)
        for policy in ('in.jatayuos.update-manager.policy',
                       'in.jatayuos.update-manager.supervised.policy',
                       'in.jatayuos.update-manager.recover.policy'):
            self.assertIn('install -m 644 polkit/' + policy, rules)
