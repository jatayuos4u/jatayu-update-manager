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

## Stage A2 — supervised worker prototype

A root-only, opt-in `systemd-run --system` launcher and standalone worker are included **without GUI integration**. The worker invokes the existing validated helper, emits a minimal atomic transaction status file under `/var/lib/jatayu-update-manager/transactions/`, and runs under a transient systemd unit rather than the GUI. This prototype does **not** yet implement recovery reconciliation, proper cross-service single-flight, full journal authentication, reliable active-state reporting or crash tests. No stable use is approved. The worker is shipped solely to support controlled root-only backend testing; do not expose the launcher via a desktop entry.

## Stage A3 — worker serialization

The prototype now holds a private root-owned POSIX `flock` for the entire worker operation, including helper invocation and status completion; competing workers fail without launching APT. Tests exercise contention from independent processes and verify that the lock releases. Status records include boot identity and last-updated UTC. This worker-level lock **does not** prevent external package managers from running; APT's native locking still governs cross-application contention. It also cannot yet classify a worker killed while its status reads `running`: a recovery reconciler and GUI reconnect mechanism are outstanding.

## Stage A4 — read-only status verification and conservative recovery classification

A new `status_reader.py` provides bounded, read-only status-file parsing with file/directory permission checks and symlink rejection. A status left `running` on an older boot is classified `interrupted_unknown`; an apparently running record on the same boot is `running_unverified`, **not** proof that APT is still active. Completed/failed records require consistent exit codes. This is a data/recovery inspection foundation, not an authorized GUI control path. We deliberately leave GUI integration disabled: no arbitrary status file can be used as evidence of package integrity, and no completed outcome should be reported solely from a missing systemd unit. To enable the GUI later, first implement a reviewed Polkit-authorized, fixed-argument launcher and verify systemd unit identity; then use the returned transaction ID to reconnect to a validated status. Crash simulations and root-only integration tests are still pending.
