# Jatayu Update Manager

[![Candidate](https://img.shields.io/badge/testing-1.2.2--rc3-orange)](https://github.com/jatayuos4u/jatayu-update-manager/actions/runs/45934689197)
[![Debian](https://img.shields.io/badge/Debian-13%20Trixie-blue)](https://www.debian.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Jatayu Update Manager 1.2.2 RC3 (testing candidate)** is a PyQt6 graphical APT update manager for [JatayuOS](https://jatayuos.in), based on Debian 13 Trixie and KDE Plasma.

> [!WARNING]
> **Pre-release / Testing (v1.2.2-rc3 candidate):** Not yet approved for production systems or inclusion in the stable JatayuOS ISO. The app still requires independent transaction supervision and concurrent APT/dpkg integration tests; see SECURITY_AUDIT_2026-11-25.md. Try it on a disposable VM or backed-up test system.

## Download Jatayu Update Manager

**[⬇ Download RC3 candidate (.deb in GitHub Actions artifact)](https://github.com/jatayuos4u/jatayu-update-manager/actions/runs/45934689197)** — expand *Artifacts*, download `jatayu-update-manager-1.2.2-rc3-kernel-fix-test` and extract the ZIP. This is a temporary test artifact, **not** an official GitHub Release asset.

Previous published testing build: [RC2 release](https://github.com/jatayuos4u/jatayu-update-manager/releases/tag/v1.2.2-rc2).

- [Read RC3 candidate release notes](RELEASE_NOTES_v1.2.2-rc3.md)
- The RC3 artifact contains `SHA256SUMS` beside its `.deb` file.
- [See all releases](https://github.com/jatayuos4u/jatayu-update-manager/releases)

### Install the downloaded package

Open Konsole in the folder containing the downloaded `.deb` file, then run:

```bash
sudo apt install ./jatayu-update-manager_1.2.2~rc3-1_all.deb
jatayu-update-manager
```

To verify the downloaded file, place `SHA256SUMS` alongside the `.deb` and run `sha256sum -c SHA256SUMS` before installation.

## Final security review

See [25 November 2026 security audit](SECURITY_AUDIT_2026-11-25.md). **RC3 remains a pre-release candidate**: crash-safe transaction supervision and concurrent package-manager tests are release blockers. Do not ship as stable or bundle in the public ISO yet.

## RC3 functional verification

On 27 November 2026, a JatayuOS Debian 13 laptop was observed detecting both the new Linux 6.12.118 image and its metapackage upgrade, showing them in the confirmation preview, installing them successfully, generating initramfs and GRUB entries, and booting the new kernel. Post-install `dpkg --audit` reported no problems and `apt-get check` succeeded. These results confirm the specific missing-kernel-update fix, **not** GUI-crash safety or a complete independent security audit.

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

The package is written to the parent directory, e.g. `../jatayu-update-manager_1.2.2~rc3-1_all.deb`.

## Test and run from source

Run tests without root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src helper scripts
```

## Scope and limitations

- Refresh executes `apt-get update`, and install uses `apt-get -y --with-new-pkgs --no-remove upgrade` via a fixed Polkit helper. The same removal-free plan is used for discovery and preview.
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


## 1.2.1 security hardening

Version 1.2.1 RC1 is published for testing. It adds a simulated APT transaction review; the privileged helper re-simulates the exact installation plan and rejects mismatches or removals. UI closing is blocked while commands run, but process-crash durability is not guaranteed. Integration tests on an actual JatayuOS VM remain required.
