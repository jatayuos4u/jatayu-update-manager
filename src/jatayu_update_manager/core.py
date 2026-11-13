"""Read-only APT package information; no privileged commands here."""
import apt


def available_updates():
    cache = apt.Cache()
    cache.open(None)
    cache.upgrade(dist_upgrade=False)
    results = []
    for pkg in cache.get_changes():
        if not pkg.is_upgradable or not pkg.installed or not pkg.candidate:
            continue
        results.append((pkg.name, pkg.installed.version, pkg.candidate.version))
    return sorted(results, key=lambda x: x[0].lower())


def recent_history(path='/var/log/apt/history.log', limit=60):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        return ''.join(lines[-limit:]).strip() or 'No recent APT history.'
    except (OSError, PermissionError):
        return 'APT history is unavailable.'
