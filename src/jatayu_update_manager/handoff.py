"""Conservative per-user handoff record for GUI crash-before-ID-save recovery.

Only a root-authorized launcher writes these records. A reader treats them as
unverified transaction locators, never as proof of APT execution/completion.
"""
import fcntl
import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import tempfile

from .supervisor import STATE_DIR, prepare_state_directory

_ID = re.compile(r'[0-9a-f]{32}\Z')
_MAX = 512


def handoff_path(uid, directory=STATE_DIR):
    if type(uid) is not int or not 0 <= uid <= 4294967295:
        raise ValueError('Invalid account ID')
    return Path(directory) / ('handoff-' + str(uid) + '.json')


def write_handoff(uid, identifier, phase, directory=STATE_DIR):
    """Atomically preserve the locator before asking systemd to start work."""
    if os.geteuid() != 0:
        raise PermissionError('Only root may update a handoff record')
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
        raise ValueError('Invalid transaction ID')
    if phase not in ('pending', 'submitted', 'launch_unknown'):
        raise ValueError('Invalid handoff phase')
    directory = prepare_state_directory(directory)
    dest = handoff_path(uid, directory)
    fd, temp = tempfile.mkstemp(prefix='.handoff-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            # Root-owned and root-readable only. Never expose a caller UID's
            # transaction locator to another unprivileged local account.
            os.fchmod(out.fileno(), 0o600)
            json.dump({'uid': uid, 'id': identifier, 'phase': phase}, out)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, dest)
        fd_dir = os.open(directory, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(fd_dir)
        finally:
            os.close(fd_dir)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_handoff(uid, directory=STATE_DIR):
    """Privileged reader only until an authenticated per-user IPC exists.

    A UID in a filename is not an authorization check. The GUI must not
    directly open root-only recovery files or expose an unauthenticated API.
    """
    if os.geteuid() != 0:
        raise PermissionError('Handoff recovery requires a privileged reader')
    folder = Path(directory)
    mode = folder.lstat()
    if not stat.S_ISDIR(mode.st_mode) or mode.st_mode & 0o022:
        raise ValueError('Unsafe handoff directory')
    if folder == STATE_DIR and mode.st_uid != 0:
        raise ValueError('Handoff directory must be root-owned')
    fd = os.open(handoff_path(uid, folder),
                 os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or st.st_mode & 0o077 or st.st_size > _MAX
                or (folder == STATE_DIR and st.st_uid != 0)):
            raise ValueError('Unsafe handoff file')
        data = os.read(fd, _MAX + 1)
    finally:
        os.close(fd)
    if len(data) > _MAX:
        raise ValueError('Oversized handoff')
    try:
        record = json.loads(data.decode('utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise ValueError('Invalid handoff encoding') from exc
    if (type(record) is not dict or set(record) != {'uid', 'id', 'phase'}
            or type(record['uid']) is not int or record['uid'] != uid
            or type(record['id']) is not str or not _ID.fullmatch(record['id'])
            or record['phase'] not in ('pending', 'submitted', 'launch_unknown')):
        raise ValueError('Invalid handoff content')
    return record


@contextmanager
def handoff_launch_lock(uid, directory=STATE_DIR):
    """Serialize launchers for a user across processes.

    A separate lock file is needed: atomic status-file replacements should
    never replace the inode on which a process holds its flock.
    """
    root = prepare_state_directory(directory)
    handoff_path(uid, root)  # strict type/range validation
    path = root / ('.handoff-launch-' + str(uid) + '.lock')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_mode & 0o077
                or (os.geteuid() == 0 and info.st_uid != 0)):
            raise ValueError('Unsafe handoff launcher lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def ensure_no_unresolved_handoff(uid, directory=STATE_DIR):
    """Fail closed when an earlier handoff has no verified final outcome."""
    try:
        previous = read_handoff(uid, directory)
    except FileNotFoundError:
        return
    from .status_reader import read_status
    try:
        status = read_status(previous['id'], directory=directory)
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise RuntimeError('Previous transaction needs inspection') from exc
    if status['state'] not in ('completed', 'failed'):
        raise RuntimeError('Previous transaction has no final status')
    from .status_reader import check_worker_unit
    # A terminal JSON report is not a service-liveness attestation. Do not
    # overwrite the pointer while its transient systemd unit is still active,
    # or if querying systemd fails and we cannot determine its state.
    if check_worker_unit(previous['id']) != 'inactive':
        raise RuntimeError('Previous transaction service is not confirmed inactive')
    # A terminal record with an inactive worker is still not proof that
    # packages are healthy; users must resolve APT failures separately.
