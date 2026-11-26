"""Fault-injection tests: isolated fake helper, no apt/dpkg/systemd invocation.

Proves the worker's process and status journal can outlive a killed controller
in a process model. Does NOT claim a real root systemd service was exercised.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from jatayu_update_manager.status_reader import read_status, reconcile_status


WORKER_CODE = "import sys\nfrom unittest.mock import patch\nfrom jatayu_update_manager import supervisor as s\ndirectory, helper, identifier = sys.argv[1:]\nwith patch.object(s.os, 'geteuid', return_value=0):\n    with patch.object(s, 'HELPER', helper):\n        sys.exit(s.run_worker(identifier, 'refresh', '-', directory=directory))\n"
CONTROLLER_CODE = "import subprocess\nimport sys\nimport time\ndirectory, helper, identifier, worker = sys.argv[1:]\nsubprocess.Popen([sys.executable, '-c', worker, directory, helper, identifier],\n                 start_new_session=True, stdin=subprocess.DEVNULL,\n                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,\n                 close_fds=True)\nprint('started', flush=True)\ntime.sleep(30)\n"


class CrashIsolationTests(unittest.TestCase):
    def wait_for(self, predicate, timeout=6):
        limit = time.monotonic() + timeout
        while time.monotonic() < limit:
            try:
                if predicate():
                    return True
            except (FileNotFoundError, ValueError):
                pass
            time.sleep(0.025)
        return False

    def test_worker_finishes_after_controller_is_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            helper = directory / 'mock-helper'
            helper.write_text('#!/usr/bin/python3\n'
                              'import time\n'
                              'time.sleep(0.8)\n')
            helper.chmod(0o755)
            identifier = 'a' * 32
            environment = dict(os.environ)
            controller = subprocess.Popen(
                [sys.executable, '-c', CONTROLLER_CODE,
                 tmp, str(helper), identifier, WORKER_CODE],
                env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            try:
                self.assertEqual(controller.stdout.readline().strip(), 'started')
                statusfile = directory / (identifier + '.json')
                self.assertTrue(self.wait_for(
                    lambda: statusfile.exists() and
                    json.loads(statusfile.read_text())['state'] == 'running'),
                    'Worker never began; inspect isolated environment')
                controller.kill()
                controller.wait(timeout=3)
                self.assertTrue(self.wait_for(
                    lambda: json.loads(statusfile.read_text())['state'] == 'completed'),
                    'Detached worker did not finish')
                record = read_status(identifier, directory=directory)
                self.assertEqual(record['exit_code'], 0)
                self.assertEqual(reconcile_status(identifier, record), 'completed')
            finally:
                if controller.poll() is None:
                    controller.kill()
                    controller.wait(timeout=3)
                controller.stdout.close()
                controller.stderr.close()

    def test_unfinished_record_is_not_success(self):
        record = {'state': 'running', 'boot_id': 'b' * 36}
        self.assertEqual(
            reconcile_status('c' * 32, record, current_boot='b' * 36,
                             unit_state='inactive'),
            'interrupted_unknown')
