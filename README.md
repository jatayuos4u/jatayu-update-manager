# Jatayu Update Manager

**Jatayu Update Manager 1.2.0** is a PyQt6 graphical APT update manager for [JatayuOS](https://jatayuos.in), based on Debian 13 Trixie and KDE Plasma.

> **Status: release candidate / testing only.** The UI has been tested on JatayuOS, but privileged real-package upgrades, cancellation, lock handling, and offline failure paths require verification before a stable public release.

## Features

- English and Hindi interface with saved language preference
- Displays APT safe-upgrade candidates and installed/available versions
- Explicit refresh of package lists via Polkit
- Confirm-before-upgrade; no arbitrary shell command execution
- Update history and operation log
- Dark/light palette, translated empty states and package search
- Remembers the time of the last **successful refresh**

## Requirements

Debian 13 (Trixie), Python 3, PyQt6, python3-apt, APT, Polkit/pkexec, and a working desktop Polkit authentication agent.

## Build a Debian package

On Debian 13 / JatayuOS:

```bash
sudo apt update
sudo apt install --no-install-recommends build-essential debhelper dh-python dpkg-dev python3 python3-apt python3-pyqt6 pkexec polkitd
dpkg-buildpackage -us -uc -b
```

The package is written to the parent directory, e.g. `../jatayu-update-manager_1.2.0-1_all.deb`.

## Install and run

```bash
sudo apt install ../jatayu-update-manager_1.2.0-1_all.deb
jatayu-update-manager
```

Run tests without root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src helper scripts
```

## Scope and limitations

- Refresh executes `apt-get update`, and install uses `apt-get -y --no-remove upgrade` via a fixed Polkit helper.
- This is **not** a full distribution upgrade, Flatpak manager, or security-update classifier.
- APT may hold back packages. Package listings rely on APT metadata.
- The displayed progress bar is indeterminate; detailed operation output is available in the log.
- The GUI cannot cancel an ongoing upgrade. Do not kill dpkg during package configuration.
- History reads only `/var/log/apt/history.log`, not rotated logs.
- The project does not yet provide an official signed JatayuOS APT package repository.

## Security

The GUI runs without root. The Polkit helper authorizes only the fixed actions `refresh` and `upgrade`. Do not substitute unauthenticated repositories, run the UI with sudo, or publish this package as stable without isolated VM integration testing.

## Development

- `src/jatayu_update_manager/`: Qt GUI, update information and translations
- `helper/`: restricted privileged APT helper
- `polkit/`: authorization policy
- `debian/`: Debian package build files
- `tests/`: initial unit/smoke tests

## License

MIT. See [LICENSE](LICENSE) and [debian/copyright](debian/copyright). The maintainer email in `debian/control` should be confirmed by the JatayuOS maintainers before final publication.

## Project

- Website: https://jatayuos.in
- Main OS repository: https://github.com/jatayuos4u/jatayuos
- Update Manager: https://github.com/jatayuos4u/jatayu-update-manager
