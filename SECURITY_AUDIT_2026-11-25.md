# Jatayu Update Manager: final security review (25 November 2026)

Scope: the `jatayu-update-manager` Python/PyQt6 source, APT helper, Polkit policy, Debian packaging, GitHub workflow definitions, and supplied GUI screenshots. Branch: `security/1.2.2-final-review`, based on main `34a4e790`.

## Summary

**Result: CONDITIONAL / NOT CLEARED FOR UNRESTRICTED STABLE RELEASE OR DEFAULT ISO INSTALLATION.**

The user's screenshots show working package discovery, preview, and the Polkit authentication prompt; the user reports a successful week of use. This is important functional test evidence, **not** independent fault-injection or crash recovery verification.

### Controls confirmed in source

- GUI is unprivileged; `pkexec` invokes a narrowly defined root helper.
- Helper only accepts `refresh` or `upgrade` with a 64-hex-character plan digest; no shell or user-supplied command line.
- `--no-remove` is passed; root helper independently re-simulates and blocks changes in the modeled Inst/Conf plan.
- Debian builds, selected Bandit checks and unit tests run on Debian 13 CI. Release artifacts include SHA-256 checksums.
- Polkit policy requires administrator authentication for active sessions.

### Findings

| ID | Priority | Observation | Status |
|---|---|---|---|
| SEC-01 | **High — release blocker** | GUI-owned `QProcess` can lose its privileged child when the GUI is killed, crashes or the user session terminates. Normal close protection does not address abrupt termination or durable status/recovery. | **Open**: independently supervised transaction service and VM fault-injection tests needed |
| SEC-02 | **High — release blocker** | APT simulation and upgrade are not atomic: external APT/dpkg changes could occur between the privileged re-check and actual APT execution. The digest is advisory, not a transaction authorization proof. | **Open**: robust transaction/locking design and end-to-end tests needed |
| SEC-03 | Medium | APT `update` may exit successfully despite some repository fetch failures using default behavior. | **Mitigated in RC2** with `APT::Update::Error-Mode=any`; requires runtime test |
| SEC-04 | Medium | Preview and GUI log memory were unbounded before parsing, allowing excessive output to consume memory. | **Mitigated in RC2** by a preview cap and display log block limit |
| SEC-05 | Medium | Published release workflows grant `contents: write`, are triggered by code updates, and use mutable `debian:trixie` instead of an image digest. Release provenance is not signed. | **Open**: protected manual release environments, digest-pinned images, attestations |
| SEC-06 | Medium | GitHub rulesets query returned no rulesets; classic branch protection was not verified from this connection. | **Open**: require PR review, build checks and protected tags |
| SEC-07 | Medium | Automated tests do not cover actual interrupted dpkg, lock contention, offline network, repository signatures, Polkit cancellation or GUI crash while upgrading. | **Open**: isolated JatayuOS VM integration suite needed |

### Release decision

RC2 may be published as a **testing pre-release**, but it must not be described as security-certified or stable. Do not include it by default in a public stable JatayuOS ISO until SEC-01/SEC-02 and the fault-injection checklist are resolved. Production signing and branch/tag rules should also be configured.

### Test procedure (disposable VM only)

1. Verify all `.deb` installed file owners, modes and polkit policy.
2. Verify no arbitrary helper arguments can invoke APT.
3. Check refresh with an offline/partially unavailable repository, and cancelled authentication.
4. Run an actual upgrade; compare apt history, package state and error codes.
5. Exercise APT lock contention, a failing package maintainer script, and a simulated repository signature error.
6. Force-kill the GUI during an upgrade and inspect whether package configuration is interrupted. **Do not do this on a real daily-use OS.**
7. Check translations, icon, version, uninstallation and clean reinstall.
8. Review the release's package SHA256, provenance, and GitHub protection settings.

This is a static/code-workflow audit, not a complete penetration test or certification.

## RC3 kernel-detection follow-up (27 November 2026)

The user identified that Discover offered a new `linux-image-6.12.118+deb13-amd64` dependency and the `linux-image-amd64` metapackage while RC2 reported no updates. RC3 changes discovery, preview, and privileged execution to the same `apt-get upgrade --with-new-pkgs --no-remove` policy. The proposed kernel upgrade was verified by a successful local simulation and subsequently a real installation, clean `dpkg --audit` and `apt-get check`, successful reboot into `6.12.118+deb13-amd64`, and an empty post-upgrade list. CI for the focused fix completed successfully: 27 tests passed, one skipped, Debian 13 package built.

**Security decision unchanged:** SEC-01, SEC-02 and SEC-07 remain open. The earlier RC2 audit is not a certification of RC3; this is a focused follow-up only. Do not describe RC3 as stable or include it by default in the public ISO until disposable-VM crash and transaction-interruption testing passes. Release provenance, signed checksums and branch protections remain unresolved independently of the successful kernel upgrade.
