"""Read-only, fail-closed parser for supervised transaction status.

No writes, no privilege escalation and no assumption that 'running' means
APT is still active. The GUI may use this after a verified authorization bridge
returns a transaction ID.
"""
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from .supervisor import STATE_DIR, WORKER, boot_id, status_path

MAX_STATUS_BYTES = 4096
_ID = re.compile(r'[0-9a-f]{32}\Z')
_BOOT = re.compile(r'[0-9a-f-]{36}\Z')


class InvalidStatus(ValueError):
    pass


def read_status(identifier, directory=STATE_DIR):
    """Read a bounded atomic status record without following file symlinks.

    This API intentionally does not create state directories or mutate files.
    A caller must only trust root-owned records in production.
    """
    if not _ID.fullmatch(identifier):
        raise InvalidStatus('Invalid transaction identifier')
    folder = Path(directory)
    details = folder.lstat()
    if not stat.S_ISDIR(details.st_mode) or (details.st_mode & 0o022):
        raise InvalidStatus('Unsafe transaction status directory')
    if folder == STATE_DIR and details.st_uid != 0:
        raise InvalidStatus('Transaction status directory is not root-owned')
    fd = os.open(status_path(identifier, folder),
                 os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise InvalidStatus('Unsafe transaction status file')
        if metadata.st_mode & 0o022:
            raise InvalidStatus('Transaction status file is writable by other users')
        if folder == STATE_DIR and metadata.st_uid != 0:
            raise InvalidStatus('Transaction status file is not root-owned')
        if metadata.st_size > MAX_STATUS_BYTES:
            raise InvalidStatus('Transaction status exceeds size limit')
        raw = os.read(fd, MAX_STATUS_BYTES + 1)
        if len(raw) > MAX_STATUS_BYTES:
            raise InvalidStatus('Transaction status exceeds size limit')
    finally:
        os.close(fd)
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise InvalidStatus('Invalid transaction status format') from exc
    if not isinstance(data, dict):
        raise InvalidStatus('Transaction status must be an object')
    if set(data) != {'id', 'action', 'state', 'exit_code', 'updated_utc', 'boot_id'}:
        raise InvalidStatus('Transaction status has unexpected fields')
    if data['id'] != identifier or data['action'] not in ('refresh', 'upgrade'):
        raise InvalidStatus('Transaction status identity is invalid')
    if data['state'] not in ('running', 'completed', 'failed'):
        raise InvalidStatus('Transaction status state is invalid')
    code = data['exit_code']
    if data['state'] == 'running':
        if code is not None:
            raise InvalidStatus('Running transaction cannot have a final exit code')
    elif type(code) is not int or code < 0 or code > 255:
        raise InvalidStatus('Final transaction exit code is invalid')
    if data['state'] == 'completed' and code != 0:
        raise InvalidStatus('Completed transaction must exit successfully')
    if data['state'] == 'failed' and code == 0:
        raise InvalidStatus('Failed transaction must have a nonzero exit code')
    if not isinstance(data['updated_utc'], str) or len(data['updated_utc']) > 40:
        raise InvalidStatus('Invalid status timestamp')
    if not isinstance(data['boot_id'], str) or (
            data['boot_id'] != 'unavailable' and not _BOOT.fullmatch(data['boot_id'])):
        raise InvalidStatus('Invalid boot identifier')
    return data


def classify_status(data, current_boot=None):
    """Return a conservative UI label; never infer completion from a stale record."""
    if data['state'] in ('completed', 'failed'):
        return data['state']
    if current_boot is None:
        current_boot = boot_id()
    if (current_boot != 'unavailable' and data['boot_id'] != 'unavailable'
            and current_boot != data['boot_id']):
        return 'interrupted_unknown'
    return 'running_unverified'


SYSTEMCTL = '/usr/bin/systemctl'
MAX_SYSTEMD_REPLY = 4096


def check_worker_unit(identifier, runner=subprocess.run):
    """Return active/inactive/unknown for exactly this systemd transaction unit.

    Status is intentionally tri-state: a failed query must never be mistaken
    for evidence of an interrupted transaction. Only the systemd system
    manager can establish the live state; user-controlled status JSON cannot.
    """
    if not _ID.fullmatch(identifier):
        raise InvalidStatus('Invalid transaction ID')
    unit = 'jatayu-update-' + identifier + '.service'
    argv = [SYSTEMCTL, '--system', '--no-pager', 'show',
            '--property=LoadState', '--property=ActiveState',
            '--property=ExecStart', unit]
    try:
        result = runner(argv, check=False, capture_output=True,
                        timeout=2, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
    except (OSError, subprocess.TimeoutExpired):
        return 'unknown'
    if len(result.stdout) > MAX_SYSTEMD_REPLY:
        return 'unknown'
    try:
        fields = {}
        for line in result.stdout.decode('utf-8').splitlines():
            key, separator, value = line.partition('=')
            if not separator or key in fields:
                return 'unknown'
            fields[key] = value
        if set(fields) != {'LoadState', 'ActiveState', 'ExecStart'}:
            return 'unknown'
    except UnicodeDecodeError:
        return 'unknown'
    if fields['LoadState'] == 'not-found':
        # systemd --collect removes transient units after they finish.
        # Accept a missing unit only when systemctl explicitly returned
        # a consistent unloaded, inactive record. Some versions return 1.
        if (result.returncode in (0, 1) and
                fields['ActiveState'] == 'inactive' and
                not fields['ExecStart'].strip()):
            return 'inactive'
        return 'unknown'
    if result.returncode != 0 or fields['LoadState'] != 'loaded':
        return 'unknown'
    # Check the actual configured executable and argv, not merely whether
    # these strings appear somewhere in unrelated systemd metadata.
    execstart = fields['ExecStart']
    expected_prefix = 'path=' + WORKER + ' ; argv[]=' + WORKER + ' ' + identifier + ' '
    if expected_prefix not in execstart:
        return 'unknown'
    if fields['ActiveState'] == 'active':
        return 'active'
    if fields['ActiveState'] in ('inactive', 'failed'):
        return 'inactive'
    return 'unknown'


def reconcile_status(identifier, record, unit_state=None, current_boot=None):
    """Classify running state using boot ID and verified systemd unit state.

    A disappeared unit is *not* automatically a completed APT operation.
    """
    state = classify_status(record, current_boot=current_boot)
    if state != 'running_unverified':
        return state
    if unit_state is None:
        unit_state = check_worker_unit(identifier)
    if unit_state == 'active':
        return 'running_confirmed'
    if unit_state == 'inactive':
        return 'interrupted_unknown'
    return 'running_unverified'
