#!/usr/bin/python3
"""Strict checks on the *built .deb*, not just development source files.

No root installation, real APT operation or Polkit authentication is performed.
"""
import argparse
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET

EXPECTED_POLICY = {
    'in.jatayuos.update-manager.manage': '/usr/lib/jatayu-update-manager/privileged-helper',
    'in.jatayuos.update-manager.supervised': '/usr/lib/jatayu-update-manager/supervised-launcher',
    'in.jatayuos.update-manager.recover': '/usr/lib/jatayu-update-manager/recovery-lookup',
}
REQUIRED_BINARIES = set(EXPECTED_POLICY.values())
POLICY_DIR = '/usr/share/polkit-1/actions'


def inspect_package(package):
    package = Path(package).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='jatayu-package-audit-') as temp:
        root = Path(temp)
        # Extracting an untrusted archive is a privileged operation in some
        # environments. CI only audits an archive built from the checked-out PR,
        # using an unprivileged container, and never installs it on a host.
        subprocess.run(['/usr/bin/dpkg-deb', '-x', str(package), str(root)], check=True)
        for expected in REQUIRED_BINARIES:
            path = root / expected.lstrip('/')
            if not path.is_file() or path.is_symlink():
                raise ValueError('Required helper missing or symlink: ' + expected)
            mode = path.stat().st_mode
            if not mode & stat.S_IXUSR or (mode & 0o022) or (mode & 0o6000):
                raise ValueError('Unsafe privileged helper permissions: ' + expected)

        found = set()
        for path in (root / POLICY_DIR.lstrip('/')).glob('in.jatayuos.update-manager*.policy'):
            if path.is_symlink() or not path.is_file():
                raise ValueError('Unsafe Polkit file: ' + str(path))
            mode = path.stat().st_mode
            if (mode & 0o022) or (mode & 0o6000):
                raise ValueError('Writable or setuid Polkit policy: ' + str(path))
            document = ET.parse(path).getroot()
            actions = document.findall('action')
            if len(actions) != 1:
                raise ValueError('Unexpected action count in ' + str(path))
            action = actions[0]
            identity = action.attrib.get('id')
            if identity in found or identity not in EXPECTED_POLICY:
                raise ValueError('Unknown or duplicate Polkit action: ' + str(identity))
            found.add(identity)
            annotations = action.findall('annotate')
            if len(annotations) != 1 or annotations[0].attrib.get('key') != 'org.freedesktop.policykit.exec.path':
                raise ValueError('Unexpected Polkit exec annotations: ' + str(identity))
            if annotations[0].text != EXPECTED_POLICY[identity]:
                raise ValueError('Polkit executable mismatch: ' + str(identity))
            defaults = action.find('defaults')
            if defaults is None:
                raise ValueError('Missing Polkit defaults')
            for key, expected in [('allow_any', 'no'), ('allow_inactive', 'no'), ('allow_active', 'auth_admin')]:
                entry = defaults.find(key)
                if entry is None or entry.text != expected:
                    raise ValueError('Unsafe authorization defaults for ' + str(identity))
        if found != set(EXPECTED_POLICY):
            raise ValueError('Missing installed Polkit actions: ' + repr(set(EXPECTED_POLICY) - found))
        for folder, dirs, filenames in os.walk(root):
            for name in dirs + filenames:
                member = Path(folder) / name
                mode = member.lstat().st_mode
                if mode & 0o6000 or mode & 0o002:
                    raise ValueError('Unsafe setuid/setgid or world writable package entry: ' + str(member))
        print('PASS: installed helpers, Polkit paths, permissions and archive safety verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('package')
    inspect_package(parser.parse_args().package)
