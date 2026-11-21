# Jatayu Update Manager 1.2.2 RC1

**Pre-release / Testing — not a stable or security-certified release**

Jatayu Update Manager provides a bilingual (English/Hindi), KDE Plasma-compatible graphical interface for Debian 13 APT upgrades.

## What's new in 1.2.2 RC1
- Expanded **Available updates** section with a more compact summary dashboard.
- **Expand updates list / Show dashboard** toggle for reviewing many package updates.
- Denser package rows and full version strings on hover.
- Professional **About** dialog, bilingual **Help**, **Report an issue**, and **License & credits**.
- Attribution in About and Credits: **Creator — Anup Kumar Yadav**; Developer — JatayuOS Team.
- New dedicated orange Update Manager SVG icon, installed for KDE application launcher, taskbar, window title and dialogs.
- Consistent Qt/desktop identity for KDE Plasma 6.
- Existing APT/Polkit update handling and security checks retained from 1.2.1.

## Package and installation

**Debian 13 / JatayuOS testing build:** `jatayu-update-manager_1.2.2~rc1-1_all.deb`

Download the .deb package and SHA256SUMS from this release. Check the download integrity with `sha256sum -c SHA256SUMS`, then install:

```bash
sudo apt install ./jatayu-update-manager_1.2.2~rc1-1_all.deb
jatayu-update-manager
```

KDE Plasma users may need to unpin an older launcher and pin the installed launcher again after updating.

## Testing and security caveat

Automated Debian 13 build, Python unit tests, and selected security checks run in CI. This release candidate has received positive JatayuOS desktop testing of layout and icon behavior.

However, full crash-safe privileged transaction supervision, APT/dpkg interruption recovery, exhaustive lock contention and offline/network testing, and release supply-chain controls remain open. **Do not declare the package stable or distribute it in a stable ISO until these requirements are completed.**

Security follow-up: https://github.com/jatayuos4u/jatayu-update-manager/issues/4

Source: https://github.com/jatayuos4u/jatayu-update-manager
Website: https://jatayuos.in
License: MIT
