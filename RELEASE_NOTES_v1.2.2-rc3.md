# Jatayu Update Manager 1.2.2 RC3 — Testing pre-release

**Release category: pre-release / testing, not stable.**

## What's fixed

- Detects safe upgrades that need new dependency packages, including Linux kernel image upgrades.
- Uses `apt-get -s --with-new-pkgs --no-remove upgrade` for the read-only available-updates view.
- Uses the matching `--with-new-pkgs --no-remove` policy for the unprivileged confirmation preview and Polkit-authorized privileged upgrade.
- Does not permit planned package removals and does not turn on `full-upgrade`.
- Corrects empty-state messages in English and Hindi to avoid claiming that *all* kinds of updates are unavailable.

## Verification

- Debian 13 CI run: https://github.com/jatayuos4u/jatayu-update-manager/actions/runs/45934689197
- 27 unit tests passed, 1 skipped. Debian package `jatayu-update-manager_1.2.2~rc3-1_all.deb` built.
- On a JatayuOS laptop, both `linux-image-6.12.118+deb13-amd64` and `linux-image-amd64` were detected and shown in the installation confirmation.
- The user installed both packages; APT/dpkg integrity checks passed, and the machine booted into `6.12.118+deb13-amd64`.

## Installation

Download the CI artifact from the link above, extract the ZIP, verify `SHA256SUMS`, and run:

```sh
sudo apt install ./jatayu-update-manager_1.2.2~rc3-1_all.deb
```

## Known limitations / release blockers

The normal updater still launches privileged APT through GUI-owned QProcess. Unexpected GUI termination during a live upgrade has not been demonstrated safe; the privileged plan re-simulation does not provide an atomic guarantee against concurrent package changes. Real Polkit, locking, interrupted-dpkg, and GUI-crash fault-injection tests in a disposable Debian 13 VM are outstanding. See `SECURITY_AUDIT_2026-11-25.md` and the separate experimental 1.2.3 PR #7. **Do not label this build stable or bundle it by default into the public ISO.**
