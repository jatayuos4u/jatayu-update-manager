#!/usr/bin/python3
"""VM-only adapter to run the REAL Jatayu worker with a FAKE helper.

Must never be installed into the Debian package or enabled on a workstation.
"""
import os
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
    directory = Path(directory_arg).resolve(strict=True)
    helper = Path(helper_arg).resolve(strict=True)
    if not directory.is_dir() or helper.parent != directory:
        raise ValueError('Mock helper must live inside isolated test directory')
    if helper.name != 'mock-helper' or not helper.is_file() or helper.is_symlink():
        raise ValueError('Only isolated mock-helper is permitted')
    if directory.stat().st_mode & 0o077:
        raise ValueError('Test directory must be root-private')
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
