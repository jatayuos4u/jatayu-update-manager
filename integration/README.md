# Alpha 16: disposable-VM-only systemd smoke test

This test starts a harmless Python task under a real transient systemd service in a **disposable Debian 13 VM**, kills the controller process, and verifies the service independently finishes. It does not use APT/dpkg, the real update worker, or Polkit.

It refuses to run outside a VM, requires root, and defaults to a dry run. In the disposable Debian 13 VM, with the source checkout available:

```
python3 integration/vm_systemd_smoke.py
sudo env JATAYU_VM_SMOKE_ACK=YES python3 integration/vm_systemd_smoke.py --execute
```

Successful output includes `"worker": "completed"` and `"apt_touched": false`. CI tests only the script's safety gates; CI does not execute its systemd test. This proves neither live package-upgrade survival nor Polkit authentication. Both remain release blockers.

## Alpha 17: actual transaction-worker with a mock helper

A second disposable-VM-only harness now runs the **actual** `supervisor.run_worker` code under a transient systemd unit using `integration/vm_mock_transaction_worker.py`. The adapter changes the helper path only inside the isolated test service process; it never calls APT or the production helper. It exercises genuine worker locking, journal writes, and both a successful mock operation and a nonzero exit, killing the launching controller after observing the running record. The VM must be Debian 13, root, disposable and explicitly acknowledged.

In the disposable Debian 13 VM only:

```sh
python3 integration/vm_real_worker_smoke.py
sudo env JATAYU_VM_WORKER_ACK=YES python3 integration/vm_real_worker_smoke.py --execute
```

Successful output reports both `mock-success` and `mock-failure` passing, with `apt_touched: false`. **No actual VM run has been performed by CI.** Polkit interactive authentication, live package upgrade interruption and reboot recovery are still untested and remain release blockers.

## Alpha 18 test-harness security review

The disposable-VM adapter rejects symlinked helper or directory paths, unsafe ownership, and group/world-accessible mock resources before it calls the actual transaction worker. These safeguards ensure the test cannot be silently redirected to a different helper through a simple symlink. CI checks this logic with isolated temporary directories; systemd itself is not invoked by CI.
