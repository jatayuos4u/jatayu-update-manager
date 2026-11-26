#!/usr/bin/python3
"""VM-only adapter to run the REAL Jatayu worker with a FAKE helper.

Must never be installed into the Debian package or enabled on a workstation.
"""
import os
import stat
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from jatayu_update_manager import supervisor
from vm_systemd_smoke import allowed_vm


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if os.geteuid() != 0 or not allowed_vm():
        raise RuntimeError('VM-only worker refused outside root-run Debian 13 VM')
    if len(args) != 3:
        raise ValueError('Requires transaction ID, test directory and mock helper')
    identifier, directory_arg, helper_arg = args
    # Check original paths *before* resolving. Resolving first erases the
    # evidence that an attacker-provided mock helper is a symlink.
    raw_directory = Path(directory_arg)
    raw_helper = Path(helper_arg)
    if raw_directory.is_symlink() or raw_helper.is_symlink():
        raise ValueError('Symlink test paths are forbidden')
    directory = raw_directory.resolve(strict=True)
    helper = raw_helper.resolve(strict=True)
    if (not directory.is_dir() or directory.is_symlink()
            or helper.parent != directory or helper.name != 'mock-helper'):
        raise ValueError('Mock helper must live inside isolated test directory')
    dstat = directory.stat()
    hstat = helper.stat()
    if (not stat.S_ISDIR(dstat.st_mode) or dstat.st_mode & 0o077
            or dstat.st_uid != 0):
        raise ValueError('Test directory must be root-private and root-owned')
    if (not stat.S_ISREG(hstat.st_mode) or hstat.st_nlink != 1
            or hstat.st_uid != 0 or hstat.st_mode & 0o077
            or not hstat.st_mode & stat.S_IXUSR):
        raise ValueError('Mock helper must be root-only, executable and regular')
    supervisor.validate_request(identifier, 'refresh', '-')
    # This changes only the imported module's local constant in this process;
    # the production privileged-helper and APT binaries are never invoked.
    supervisor.HELPER = str(helper)
    return supervisor.run_worker(identifier, 'refresh', '-', directory=directory)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print('VM worker test refused: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
