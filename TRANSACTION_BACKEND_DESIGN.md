# Transaction backend design — development, not production ready

The shipped 1.2.2 RC2 starts `pkexec privileged-helper` as a GUI-owned Qt process. A GUI crash can terminate its output connection and may leave the privileged child in an unknown state. A record lock preflight prevents a **known active frontend lock** at the time of each check, but is not atomic with APT's own later lock acquisition.

## Stage A — implemented in 1.2.3 alpha1 branch

- Reject privileged refresh and upgrade if an existing dpkg frontend advisory lock cannot be acquired nonblockingly.
- Recheck the frontend before starting `apt-get upgrade` after a successful plan digest comparison.
- Use `fcntl.lockf` on the existing lock file; never delete, truncate or forcibly unlock another process's lock.
- Verify lock contention with a real **second process** in unit tests.
- Keep existing RC2 releases unaffected; this branch is not yet a stable release.

## Stage B — still required before stable release

1. Use a root-managed, independently supervised transaction service (systemd), not a GUI-owned `pkexec` process for the full operation. Authentication remains a separate Polkit authorization step.
2. Service owns one transaction at a time with a fixed allowlist of actions and rejects concurrent requests. It must survive GUI termination.
3. Persist a root-owned, bounded status journal with unique transaction ID, requested action, start, final return code, and boot ID. Use atomic replace and fsync where needed. Never trust user-writable status.
4. GUI reconnects via an unprivileged status API or a narrowly permissioned D-Bus service and shows actual running/completed/failed state.
5. Carefully coordinate plan preview and execution. Never claim an external APT simulation digest is a cryptographic authorization proof or that a preflight lock is atomic.
6. Test `dpkg` interruption, GUI SIGKILL, system restart, separate APT process lock contention, package maintainer script failure, mirror failure, signature failure and canceled authentication on disposable snapshot VMs.
7. Audit systemd unit sandboxing, Polkit identity checks, per-user authorization, status/log file permissions, resource limits, provenance and branch/tag protection.

**Release gate:** Alpha1 improves busy-lock rejection only. **It does not solve GUI crash survival or the preview/execute race.** Do not ship as stable or enable it by default in the public JatayuOS ISO.
