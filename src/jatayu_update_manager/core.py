"""Read-only APT information using the same safe plan as installation."""
import re
import subprocess
import apt

APT = '/usr/bin/apt-get'
MAX_PREVIEW = 1_000_000
SAFE_UPGRADE_ARGS = ['--with-new-pkgs', '--no-remove', 'upgrade']


def available_updates():
    """Include upgrades requiring new dependencies, e.g. Linux kernel images."""
    result = subprocess.run(
        [APT, '-s', *SAFE_UPGRADE_ARGS],
        check=False, capture_output=True, text=True, timeout=120,
        env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
             'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'})
    if result.returncode:
        raise RuntimeError('APT upgrade simulation failed: ' + result.stderr[-500:])
    if len(result.stdout) > MAX_PREVIEW:
        raise RuntimeError('APT upgrade simulation exceeded the output limit.')
    names = []
    seen = set()
    for line in result.stdout.splitlines():
        if line.startswith('Remv '):
            raise RuntimeError('APT proposed removals; the upgrade plan was blocked.')
        if not line.startswith('Inst '):
            continue
        match = re.match(r'^Inst\s+(\S+)(?:\s|$)', line)
        if match is None:
            raise RuntimeError('Malformed package name in APT simulation.')
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            names.append(name)
    if not names:
        return []
    cache = apt.Cache()
    cache.open(None)
    updates = []
    for name in names:
        if name not in cache:
            raise RuntimeError('APT simulation package missing from cache: ' + name)
        pkg = cache[name]
        if not pkg.candidate:
            raise RuntimeError('APT candidate missing for ' + name)
        current = pkg.installed.version if pkg.installed else '—'
        updates.append((name, current, pkg.candidate.version))
    return sorted(updates, key=lambda row: row[0].lower())


def recent_history(path='/var/log/apt/history.log', limit=60):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        return ''.join(lines[-limit:]).strip() or 'No recent APT history.'
    except (OSError, PermissionError):
        return 'APT history is unavailable.'
