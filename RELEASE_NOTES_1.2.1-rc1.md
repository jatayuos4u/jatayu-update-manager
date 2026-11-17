# Jatayu Update Manager 1.2.1 RC1

**Status:** Pre-release / testing · **OS:** Debian 13 (Trixie) · **Desktop:** KDE Plasma 6

## What's new
- Replaced the in-window blue placeholder with the KDE update-manager icon already used in the JatayuOS application menu
- Added review of simulated APT upgrades before authorization
- Added privileged re-check of the proposed transaction plan, rejecting changed plans or package removals
- Improved ordinary window-close protection while updates are active
- Improved process-start failure and stale-check handling
- Added 1.2.1 transaction/security tests, Debian packaging checks and pinned GitHub Actions revisions in CI
- Preserved English and Hindi interface support

## Install (test systems only)

Download `jatayu-update-manager_1.2.1-1_all.deb` and `SHA256SUMS` from this release, then from the directory containing both:

```bash
sha256sum -c SHA256SUMS
sudo apt install ./jatayu-update-manager_1.2.1-1_all.deb
jatayu-update-manager
```

The software should be evaluated in a disposable JatayuOS VM or a system with a verified backup before distributing it broadly.

## Important safety status

This is **not a stable/security-certified release**. Automated tests and package builds passed; however full end-to-end package upgrade tests, crash-safe transaction supervision, lock contention, offline handling and release provenance are still under investigation. The confirmation/preview fingerprint reduces accidental mismatches but is not a cryptographic authorization of an APT transaction and does not eliminate possible time-of-check/time-of-use races.

Track further work: https://github.com/jatayuos4u/jatayu-update-manager/issues/4

The package has not been approved for inclusion in the stable JatayuOS ISO.
