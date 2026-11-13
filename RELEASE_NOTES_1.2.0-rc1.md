# Jatayu Update Manager 1.2.0 RC1

**Status: pre-release / testing only**  
**Target:** Debian 13 (Trixie), KDE Plasma  
**Repository:** https://github.com/jatayuos4u/jatayu-update-manager  
**Version tag to create:** `v1.2.0-rc1`

## Highlights

- KDE-compatible PyQt6 update dashboard
- English and Hindi interface translations
- Translated update status, empty states, package search, and saved last-successful-check timestamp
- Lists installed and candidate versions for available APT upgrades
- Restricted Polkit-authorized helper for refreshing and upgrading APT packages
- APT history view and an operation log

## Download and installation

The release-candidate Debian package is produced by the Debian 13 GitHub Actions workflow. Download the artifact `jatayu-update-manager-debian13` from the successful workflow at:

https://github.com/jatayuos4u/jatayu-update-manager/actions/runs/43374285781

Unzip the workflow artifact to obtain `jatayu-update-manager_1.2.0-1_all.deb`.

Install on a disposable JatayuOS test system:

```bash
sudo apt install ./jatayu-update-manager_1.2.0-1_all.deb
jatayu-update-manager
```

## Important limitations

- This is a **release candidate**, not a stable or security-audited updater.
- The GitHub Actions build and unit tests passed on Debian 13, but privileged real-world package upgrades still require testing on JatayuOS.
- Upgrade uses a fixed APT safe-upgrade command; this is not a Debian release upgrade or Flatpak update manager.
- Updates can require restarts. Do not interrupt dpkg or kill the privileged helper while packages are being configured.
- Do not include this RC package in a public stable ISO until release tests are completed.

## Release QA

Track test requirements and results at:

https://github.com/jatayuos4u/jatayu-update-manager/issues/2

## Source and license

Source code is available in this repository under the MIT license. Confirm maintainer contact, copyright attribution, and release packaging before stable publication.
