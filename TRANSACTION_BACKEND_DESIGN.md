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

## Stage A5 — fixed-argument Polkit launcher (GUI still disabled)

The package now includes a dedicated `supervised-launcher` bound by a separate Polkit policy to `pkexec`. It accepts only `refresh` or `upgrade` plus a lowercase 64-character hexadecimal fingerprint, requires effective root, and emits a generated transaction locator only after `systemd-run` succeeds. Its `systemd-run` environment is sanitized, and it never passes user-controlled systemd options. The packaged executable is not connected to GUI controls. Tests reject malformed requests, simulate authorization failure and launch failure, and verify the policy binding. **This is not an end-to-end authorization audit or transaction-survival test.** Before enabling it, evaluate Polkit session policy, user identity, service isolation, status reconnect, progress display and fail-safe interruption handling. Never infer successful APT completion from a successful launcher exit.

## Stage A6 — GUI read-only status diagnostics

The application menu now offers **Transaction status (experimental)** in English and Hindi. This only reads a validated record **when an explicit supervised transaction ID is already in the user's local QSettings**; otherwise it says none is tracked. The existing GUI does not launch or adopt experimental transactions. A completed record is labeled as a worker report, not as verified package integrity. Stale records remain unknown. This is a diagnostic surface, not a reliable end-to-end reconnect mechanism: it has no automatically persisted launcher-issued ID, no systemd-unit liveness verification, and no production launch UX. Privileged APT operations and normal update buttons remain unchanged.

## Stage A7 — developer-opt-in GUI launch and read-only session persistence

An experimental **refresh-only** launcher is visible solely with environment variable `JATAYU_UPDATE_MANAGER_EXPERIMENTAL=1`. It is deliberately separate from the normal Check/Install buttons, requires a second explicit warning and Polkit authentication, bounds/parses the exact `TRANSACTION_ID=<32 lowercase hex>` launcher response, persists the locator in user QSettings and polls validated read-only status after relaunch. Successful systemd launch is never interpreted as successful APT update. The GUI never kills the worker. There is no production-grade progress stream, service liveness attestation, guaranteed startup handoff (e.g. GUI SIGKILL before saving ID), or automatic resolution of an interrupted transaction. Do not enable the opt-in feature on main hardware or ship in a public ISO; isolated end-to-end tests are required.

## Stage A8 — liveness reconciliation

For an existing validated transaction record, a separate bounded `systemctl --system show` query now checks the transaction's systemd unit state and confirms that its configured ExecStart points at the packaged root worker and includes the matching transaction ID. Active units can be displayed as `running_confirmed`, but **this only confirms systemd service state, not that APT is installing packages**. If a record remains running but its unit has disappeared, report `interrupted_unknown`, never success. If the systemd query fails, report `running_unverified`, not interruption. This read-only check makes no service changes. Final status records are still based on worker reports, and actual crash survival and package-repair testing remain pending.

## Stage A9 — isolated controller-crash fault injection

New automated tests start a worker with a **temporary fake helper**, detach it from a controller process, kill the controller, and verify that the worker can still complete and persist its status. They also check that an inactive worker with a running record remains an unknown outcome. This test invokes **no real APT, dpkg, Polkit, or systemd** and does not prove that the packaged transient systemd unit will survive a real GUI crash. A real systemd/Polkit end-to-end test and crash-before-ID-handoff recovery design are still necessary before switching normal update buttons or approving a stable release.

## Stage A10 — per-user crash-before-ID handoff

The authorized launcher now obtains the caller identity from `PKEXEC_UID` and asks the root supervisor to atomically store a per-UID transaction locator before invoking `systemd-run`. The record is updated to `submitted` after a successful launch or `launch_unknown` if launching fails or times out. In experimental mode only, the GUI can recover that locator if its QSettings did not capture the launcher response. Root-owned records are bounded, checked for symlinks/permissions, and validated against the requesting UID. A locator is never proof that the service started or that APT finished. **Known gaps:** this supports the most recently submitted per-UID operation only; there is no robust transaction backlog, caller authentication for unprivileged status listing, and no real systemd/Polkit crash-timing validation. Do not enable normal updates on this backend.

## Stage A11 — unresolved handoff serialization

Two overlapping Polkit-authorized launchers for the same UID can no longer replace the recovery pointer while the prior submission is unresolved. A separate nonblocking advisory lock serializes the entire check + initial handoff + systemd-run attempt. The launcher rejects a pre-existing pending handoff, a running record, or unreadable/malformed status, retaining the previous locator for manual recovery. A terminal worker status allows a later submission, but **terminal status alone does not assert package integrity**. This per-UID guard is not a global service lock across different users; the worker's single-flight mechanism provides that secondary guard. A real systemd/Polkit integration audit is still required.

## Stage A12 — final status and service-state coherence

The next per-UID launch is denied unless the previously handed-off transaction has a validated **terminal record** and its associated systemd service is confirmed **inactive**. Unknown service liveness fails closed, rather than allowing the saved recovery ID to be overwritten. Status writes now reject inconsistent state/exit-code pairs and convert signal-terminated subprocess results such as `-9` into reportable failure codes such as `137`. Unit tests cover abnormal exit, terminal-record validation, active unit and unqueryable systemd. The actual transient service and post-upgrade package integrity still require disposable-VM end-to-end tests; none are implied by CI.

## Stage A13 — recovery handoff confidentiality and explicit limitation

Audit identified that the root-created per-UID recovery handoff was world-readable (`0644`) and could be read by another local user who knew or guessed the UID. Handoff files are now `0600` and the root-owned transaction directory is non-listable to ordinary users (searchable for known, random transaction IDs). The handoff reader itself refuses non-root execution. **Consequently automatic GUI recovery of a lost transaction ID is deliberately disabled** until a reviewed per-caller authenticated read-only IPC mechanism exists. If the GUI saved the ID from the launcher before a crash, its read-only status checks continue to work; if the GUI crashes before that handoff, manual privileged inspection is required. This prioritizes user privacy over an incomplete recovery feature. Disposable VM systemd/Polkit, interruption, and package-integrity tests still block stable release.
