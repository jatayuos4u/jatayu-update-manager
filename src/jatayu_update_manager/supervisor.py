"""Development-only backend: root-owned, systemd-supervised APT worker.

Supervised refresh remains developer-only; normal update buttons are unchanged. Intended to establish privilege boundaries,
persistent final status and tests without changing the functioning RC2 path.
"""
import fcntl
import json
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import uuid

STATE_DIR = Path('/var/lib/jatayu-update-manager/transactions')
WORKER = '/usr/lib/jatayu-update-manager/transaction-worker'
HELPER = '/usr/lib/jatayu-update-manager/privileged-helper'
SYSTEMD_RUN = '/usr/bin/systemd-run'
LAUNCH_ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
BUSY_EXIT = 75
LOCK_FILENAME = '.transaction.lock'
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


def verify_trusted_directory(path):
    """Reject symlinked, non-root-owned or untrusted writable parent dirs.

    Used only for the fixed production hierarchy; temporary isolated test
    directories intentionally have different ownership and ancestor policies.
    No chown, unlink or permission mutation is performed by this check.
    """
    path = Path(path)
    details = path.lstat()  # lstat rejects symlinks instead of following them
    if not stat.S_ISDIR(details.st_mode):
        raise OSError('Unsafe transaction directory component')
    if details.st_uid != 0 or details.st_mode & 0o022:
        raise OSError('Untrusted transaction directory ownership or permissions')
    return path


def verify_production_state_parents(directory):
    """Check every directory leading to the fixed root-owned state path.

    A root-owned, non-writable parent tree makes the later open/create safer
    against unprivileged path substitution. This is not an atomic openat2
    RESOLVE_BENEATH guarantee and requires VM review before production.
    """
    directory = Path(directory)
    if directory != STATE_DIR:
        return
    for component in reversed(list(directory.parents)):
        try:
            verify_trusted_directory(component)
        except FileNotFoundError:
            # Fresh installs may lack /var/lib/jatayu-update-manager.
            # All ancestors have already been validated in path order.
            component.mkdir(mode=0o711)
            verify_trusted_directory(component)
    # The final directory may not exist on first launch; its parent has
    # been validated or safely created under trusted ancestors.


def prepare_state_directory(directory):
    """Reject root status locations writable by untrusted users."""
    directory = Path(directory)
    verify_production_state_parents(directory)
    # Searchable but not listable by unprivileged users: exact transaction
    # IDs may still be inspected read-only. The per-UID handoff stays root-only.
    directory.mkdir(mode=0o711, parents=True, exist_ok=True)
    details = directory.lstat()
    if not stat.S_ISDIR(details.st_mode) or (details.st_mode & 0o022):
        raise OSError('Unsafe transaction state directory')
    # A production worker runs as root. Existing state must also be root-owned.
    if os.geteuid() == 0 and details.st_uid != 0:
        raise OSError('Transaction state directory is not root-owned')
    # Only adjust the canonical production directory. Preserve test fixtures.
    if directory == STATE_DIR and os.geteuid() == 0 and details.st_mode & 0o044:
        directory.chmod(stat.S_IMODE(details.st_mode) & ~0o044)
    return directory


@contextmanager
def single_transaction(directory=STATE_DIR):
    """OS-enforced lock, held by the worker across helper/APT execution.

    Unlike dpkg's own lock, this never needs to be acquired by apt-get.
    Contention fails closed. The kernel releases the lock if the worker dies.
    """
    directory = prepare_state_directory(directory)
    path = directory / LOCK_FILENAME
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    locked = False
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise OSError('Unsafe transaction lock file')
        if os.geteuid() == 0 and metadata.st_uid != 0:
            raise OSError('Transaction lock file is not root-owned')
        if metadata.st_mode & 0o077:
            raise OSError('Transaction lock permissions are too open')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        if locked:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def write_status(identifier, action, state, exit_code=None, directory=STATE_DIR):
    """Atomically replace a bounded, root-created status record."""
    validate_request(identifier, action, '-' if action == 'refresh' else '0' * 64)
    if state not in ('running', 'completed', 'failed'):
        raise ValueError('Invalid state')
    if state == 'running':
        if exit_code is not None:
            raise ValueError('Running status cannot have an exit code')
    elif type(exit_code) is not int or not 0 <= exit_code <= 255:
        raise ValueError('Terminal status must have a valid exit code')
    if state == 'completed' and exit_code != 0:
        raise ValueError('A completed transaction requires exit code zero')
    if state == 'failed' and exit_code == 0:
        raise ValueError('Failed transactions require a nonzero exit code')
    directory = prepare_state_directory(directory)
    record = {'id': identifier, 'action': action, 'state': state, 'exit_code': exit_code,
              'updated_utc': datetime.now(timezone.utc).isoformat(),
              'boot_id': boot_id()}
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


def boot_id():
    """Identify the boot that produced a status record."""
    try:
        value = Path('/proc/sys/kernel/random/boot_id').read_text(encoding='ascii').strip()
        if re.fullmatch(r'[a-f0-9-]{36}', value):
            return value
    except OSError:
        pass
    return 'unavailable'


def start_supervised(action, digest='-', owner_uid=None):
    """Only a root-authorized launcher may call this. Returns transaction ID."""
    if os.geteuid() != 0:
        raise PermissionError('Root authorization required')
    identifier = uuid.uuid4().hex
    validate_request(identifier, action, digest)
    from contextlib import nullcontext
    if owner_uid is not None:
        from .handoff import (write_handoff, handoff_launch_lock,
                              ensure_no_unresolved_handoff)
        guard = handoff_launch_lock(owner_uid)
    else:
        guard = nullcontext()
    with guard:
        if owner_uid is not None:
            ensure_no_unresolved_handoff(owner_uid)
            write_handoff(owner_uid, identifier, 'pending')
        unit = 'jatayu-update-' + identifier
        command = [
            SYSTEMD_RUN, '--system', '--unit=' + unit, '--collect',
            '--property=Type=exec', '--property=User=root',
            '--property=WorkingDirectory=/',
            # Keep helper descendants in the unit's lifecycle. If systemd
            # stops a failed/aborted worker, it must not leave APT children
            # detached outside service management.
            '--property=KillMode=control-group',
            '--property=SendSIGKILL=yes',
            '--property=StandardInput=null', '--',
            WORKER, identifier, action, digest,
        ]
        # A system service is independent of the desktop's QProcess lifetime.
        try:
            subprocess.run(command, check=True, capture_output=True, text=True,
                           timeout=30, cwd='/', env=LAUNCH_ENV)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # A timed-out launch may have reached systemd; never erase the ID.
            if owner_uid is not None:
                write_handoff(owner_uid, identifier, 'launch_unknown')
            raise
        if owner_uid is not None:
            write_handoff(owner_uid, identifier, 'submitted')
        return identifier


def run_worker(identifier, action, digest, directory=STATE_DIR):
    """Launched by systemd, not directly by the user desktop process."""
    if os.geteuid() != 0:
        raise PermissionError('Root worker required')
    validate_request(identifier, action, digest)
    # The lock must be held continuously through preview, install and status
    # completion. Different root worker processes cannot overlap each other.
    with single_transaction(directory) as acquired:
        if not acquired:
            write_status(identifier, action, 'failed', exit_code=BUSY_EXIT, directory=directory)
            return BUSY_EXIT
        write_status(identifier, action, 'running', directory=directory)
        cmd = [HELPER, action] + ([digest] if action == 'upgrade' else [])
        try:
            result = subprocess.run(cmd, check=False, cwd='/', timeout=None)
            code = result.returncode
        except OSError:
            code = 1
        # Python uses negative exit codes for processes killed by signals;
        # translate those to conventional 128+signal before persisting.
        # The status-reader must never see a malformed negative exit code.
        if code < 0:
            code = min(255, 128 - code)
        elif code > 255:
            code = 1
        write_status(identifier, action, 'completed' if code == 0 else 'failed',
                     exit_code=code, directory=directory)
        return code
