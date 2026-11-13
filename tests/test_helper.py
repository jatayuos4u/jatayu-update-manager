import pathlib
import subprocess
import unittest

HELPER = pathlib.Path(__file__).resolve().parents[1] / 'helper' / 'privileged-helper'

class HelperTests(unittest.TestCase):
    def test_invalid_action_never_executes_apt(self):
        # Running as an unprivileged account is required for this test.
        if __import__('os').geteuid() == 0:
            self.skipTest('Run test as non-root')
        proc = subprocess.run(['/usr/bin/python3', str(HELPER), 'arbitrary-command'], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
