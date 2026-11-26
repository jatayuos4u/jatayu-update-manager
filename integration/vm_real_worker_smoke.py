#!/usr/bin/python3
"""Disposable Debian 13 VM ONLY: actual worker + mock helper under systemd.

The real supervisor.run_worker writes its actual journal, holds its actual
single-flight lock and processes a fake helper. NEVER calls apt/dpkg/pkexec.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from vm_systemd_smoke import allowed_vm

ENTRY = Path(__file__).resolve().with_name('vm_mock_transaction_worker.py')
LAUNCH = '/usr/bin/systemd-run'
PYTHON = '/usr/bin/python3'


def build_service_command(identifier, directory):
    from pathlib import Path
    if len(identifier) != 32 or any(char not in '0123456789abcdef' for char in identifier):
        raise ValueError('Bad mock transaction ID')
    directory = Path(directory)
    return [
        LAUNCH, '--system',
        '--unit=jatayu-worker-mock-' + identifier,
        '--collect', '--property=Type=exec', '--property=User=root',
        '--property=WorkingDirectory=/', '--',
        PYTHON, str(ENTRY), identifier,
        str(directory), str(directory / 'mock-helper'),
    ]


def wait_for(predicate, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.04)
    return False


def run_case(exit_code):
    """Return observed actual supervisor status; real helper is never used."""
    if os.geteuid() != 0 or not allowed_vm():
        raise RuntimeError('Requires root in disposable Debian 13 VM')
    if exit_code not in (0, 42):
        raise ValueError('Only fixed fake exit codes are allowed')
    with tempfile.TemporaryDirectory(prefix='jatayu-worker-mock-') as temp:
        directory = Path(temp)
        helper = directory / 'mock-helper'
        helper.write_text(
            '#!/usr/bin/python3\nimport sys,time\n'
            'time.sleep(2)\nsys.exit(' + str(exit_code) + ')\n',
            encoding='utf-8')
        helper.chmod(0o700)
        identifier = uuid.uuid4().hex
        command = build_service_command(identifier, directory)
        controller_program = (
            'import subprocess,sys,time; '
            'subprocess.run(sys.argv[1:],check=True,timeout=15); '
            'print("LAUNCHED",flush=True); time.sleep(30)'
        )
        controller = subprocess.Popen(
            [PYTHON, '-c', controller_program, *command],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True,
        )
        try:
            if controller.stdout.readline().strip() != 'LAUNCHED':
                raise RuntimeError('Mock transient service failed to start')
            status_path = directory / (identifier + '.json')
            if not wait_for(lambda:
                    json.loads(status_path.read_text())['state'] == 'running'):
                raise RuntimeError('Real supervisor did not record running state')
            controller.kill()
            controller.wait(timeout=5)
            if not wait_for(lambda: json.loads(status_path.read_text())['state'] in
                    ('completed', 'failed')):
                raise RuntimeError('Supervisor did not finish after controller death')
            from sys import path
            path.insert(0, str(ENTRY.parents[1] / 'src'))
            from jatayu_update_manager.status_reader import read_status
            status = read_status(identifier, directory=directory)
            expected_state = 'completed' if exit_code == 0 else 'failed'
            if status['state'] != expected_state or status['exit_code'] != exit_code:
                raise RuntimeError('Final worker status/exit code mismatch')
            return {'case': 'mock-success' if exit_code == 0 else 'mock-failure',
                    'result': 'passed', 'state': status['state'],
                    'exit_code': status['exit_code'],
                    'controller': 'killed', 'apt_touched': False}
        finally:
            if controller.poll() is None:
                controller.kill()
                controller.wait(timeout=5)
            controller.stdout.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    if not args.execute:
        print('DRY RUN: no systemd worker started, no APT called.')
        return 0
    if os.environ.get('JATAYU_VM_WORKER_ACK') != 'YES':
        print('Refusing: missing disposable VM test acknowledgement', file=sys.stderr)
        return 2
    try:
        if os.geteuid() != 0 or not allowed_vm():
            raise RuntimeError('Not running as root in Debian 13 VM')
        results = [run_case(0), run_case(42)]
        print(json.dumps({'results': results, 'apt_touched': False}, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print('VM worker smoke test failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
