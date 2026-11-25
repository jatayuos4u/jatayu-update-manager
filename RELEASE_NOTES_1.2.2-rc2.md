# Jatayu Update Manager 1.2.2 RC2 — Security review build

**Status: PRE-RELEASE / TESTING. Not security-certified or cleared for public stable ISO inclusion.**

## Improvements
- Treat partially failed APT repository refreshes as failures (strict APT update error mode).
- Reject excessive simulation output before parsing, and limit displayed log history.
- Preserve the approved KDE Plasma 6 interface, expanded updates list, orange application icon, bilingual English/Hindi About and Help.
- Keep creator attribution: **Anup Kumar Yadav**, with the JatayuOS Team development credit.
- Add regression tests and a written final source-security audit.

## Installation (test systems only)

Download `jatayu-update-manager_1.2.2.rc2-1_all.deb` and `SHA256SUMS` from this GitHub release. Place both in the same directory, then run:

```bash
sha256sum -c SHA256SUMS
sudo apt install ./jatayu-update-manager_1.2.2.rc2-1_all.deb
```

The filename contains `.rc2` for GitHub compatibility; the **internal Debian version is `1.2.2~rc2-1`**.

## Remaining release blockers

**Do not promote to stable or include in the general JatayuOS ISO** until:
1. Privileged update operations survive GUI crashes/logout through an independently supervised transaction service, with recovery reporting and VM tests.
2. The upgrade transaction and its preview are coordinated robustly with concurrent APT/dpkg activity.
3. Failure-injection testing verifies offline repos, rejected authentication, locks, interrupted packages and signature failures.

See `SECURITY_AUDIT_2026-11-25.md` and https://github.com/jatayuos4u/jatayu-update-manager/issues/4.

## Verification
GitHub Actions builds and checks the Debian 13 package and generates a matching SHA-256 checksum. This is a **static audit plus automated tests**, not a complete penetration test.

Website: https://jatayuos.in
Source: https://github.com/jatayuos4u/jatayu-update-manager
License: MIT
