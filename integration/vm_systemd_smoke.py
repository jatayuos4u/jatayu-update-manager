#!/usr/bin/python3
"""Disposable Debian 13 VM-only systemd smoke test. NEVER invokes apt/dpkg."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

PROGRAM = ('import pathlib,sys,time; time.sleep(1.5); '
           'pathlib.Path(sys.argv[1]).write_text("finished", encoding="ascii")')


def allowed_vm():
    try:
        values = dict(line.split('=', 1) for line in
                      Path('/etc/os-release').read_text().splitlines() if '=' in line)
        if values.get('ID', '').strip('"') != 'debian' or values.get('VERSION_ID', '').strip('"') != '13':
            return False
        result = subprocess.run(['/usr/bin/systemd-detect-virt', '--vm', '--quiet'],
                                capture_output=True, timeout=5, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def service_command(unit, marker):
    prefix = 'jatayu-mock-smoke-'
    token = unit[len(prefix):]
    if not unit.startswith(prefix) or len(token) != 32 or any(ch not in '0123456789abcdef' for ch in token):
        raise ValueError('Invalid mock service name')
    return ['/usr/bin/systemd-run', '--system', '--unit=' + unit, '--collect',
            '--property=Type=exec', '--property=User=root',
            '--property=WorkingDirectory=/', '--',
            '/usr/bin/python3', '-c', PROGRAM, str(marker)]


def run_smoke():
    if os.geteuid() != 0 or not allowed_vm():
        raise RuntimeError('Refusing execution outside a root-run Debian 13 VM')
    with tempfile.TemporaryDirectory(prefix='jatayu-vm-smoke-') as tmp:
        marker = Path(tmp) / 'completed'
        unit = 'jatayu-mock-smoke-' + uuid.uuid4().hex
        command = service_command(unit, marker)
        controller_code = ('import subprocess,sys,time; '
                           'subprocess.run(sys.argv[1:],check=True,timeout=15); '
                           'print("LAUNCHED",flush=True); time.sleep(30)')
        controller = subprocess.Popen(
            ['/usr/bin/python3', '-c', controller_code, *command],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            if controller.stdout.readline().strip() != 'LAUNCHED':
                raise RuntimeError('Transient mock service failed to launch')
            controller.kill()
            controller.wait(timeout=5)
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline and not marker.exists():
                time.sleep(0.05)
            if not marker.exists() or marker.read_text() != 'finished':
                raise RuntimeError('Mock service did not complete after controller exit')
            return {'result': 'passed', 'unit': unit, 'controller': 'killed',
                    'worker': 'completed', 'apt_touched': False}
        finally:
            if controller.poll() is None:
                controller.kill()
                controller.wait(timeout=5)
            controller.stdout.close()
            controller.stderr.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    if not args.execute:
        print('DRY RUN: no systemd service started.')
        return 0
    if os.environ.get('JATAYU_VM_SMOKE_ACK') != 'YES':
        print('Refusing: explicit disposable VM acknowledgment is required.', file=sys.stderr)
        return 2
    try:
        print(json.dumps(run_smoke(), sort_keys=True))
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print('VM smoke test failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
