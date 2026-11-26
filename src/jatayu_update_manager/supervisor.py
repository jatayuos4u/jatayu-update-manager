"""Development-only backend: root-owned, systemd-supervised APT worker.

Not wired into the GUI in alpha2. Intended to establish privilege boundaries,
persistent final status and tests without changing the functioning RC2 path.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

STATE_DIR = Path('/var/lib/jatayu-update-manager/transactions')
WORKER = '/usr/lib/jatayu-update-manager/transaction-worker'
HELPER = '/usr/lib/jatayu-update-manager/privileged-helper'
SYSTEMD_RUN = '/usr/bin/systemd-run'
_ID = re.compile(r'[0-9a-f]{32}\Z')
_DIGEST = re.compile(r'[0-9a-f]{64}\Z')


def validate_request(identifier, action, digest):
    if not _ID.fullmatch(identifier):
        raise ValueError('Invalid transaction ID')
    if action == 'refresh' and digest == '-':
        return
    if action == 'upgrade' and _DIGEST.fullmatch(digest):
        return
    raise ValueError('Invalid transaction request')


def status_path(identifier, directory=STATE_DIR):
    if not _ID.fullmatch(identifier):
        raise ValueError('Invalid transaction ID')
    return Path(directory) / (identifier + '.json')


def write_status(identifier, action, state, exit_code=None, directory=STATE_DIR):
    """Atomically replace a bounded, root-created status record."""
    validate_request(identifier, action, '-' if action == 'refresh' else '0' * 64)
    if state not in ('running', 'completed', 'failed'):
        raise ValueError('Invalid state')
    if exit_code is not None and (not isinstance(exit_code, int) or isinstance(exit_code, bool)):
        raise ValueError('Invalid exit code')
    directory = Path(directory)
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    # Production worker must run as root; reject status-directory symlinks.
    if directory.is_symlink():
        raise OSError('Refusing symlink status directory')
    record = {'id': identifier, 'action': action, 'state': state, 'exit_code': exit_code}
    fd, tmp = tempfile.mkstemp(prefix='.status-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            os.fchmod(output.fileno(), 0o644)
            json.dump(record, output, separators=(',', ':'), sort_keys=True)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, status_path(identifier, directory))
        dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return record


def start_supervised(action, digest='-'):
    """Only a root-authorized launcher may call this. Returns transaction ID."""
    if os.geteuid() != 0:
        raise PermissionError('Root authorization required')
    identifier = uuid.uuid4().hex
    validate_request(identifier, action, digest)
    unit = 'jatayu-update-' + identifier
    command = [
        SYSTEMD_RUN, '--system', '--unit=' + unit, '--collect',
        '--property=Type=exec', '--property=User=root',
        '--property=WorkingDirectory=/', '--',
        WORKER, identifier, action, digest,
    ]
    # A system service is independent of the desktop's QProcess lifetime.
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    return identifier


def run_worker(identifier, action, digest, directory=STATE_DIR):
    """Launched by systemd, not directly by the user desktop process."""
    if os.geteuid() != 0:
        raise PermissionError('Root worker required')
    validate_request(identifier, action, digest)
    write_status(identifier, action, 'running', directory=directory)
    cmd = [HELPER, action] + ([digest] if action == 'upgrade' else [])
    try:
        result = subprocess.run(cmd, check=False, cwd='/', timeout=None)
        code = result.returncode
    except OSError:
        code = 1
    write_status(identifier, action, 'completed' if code == 0 else 'failed',
                 exit_code=code, directory=directory)
    return code
