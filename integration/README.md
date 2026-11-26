# Alpha 16: disposable-VM-only systemd smoke test

This test starts a harmless Python task under a real transient systemd service in a **disposable Debian 13 VM**, kills the controller process, and verifies the service independently finishes. It does not use APT/dpkg, the real update worker, or Polkit.

It refuses to run outside a VM, requires root, and defaults to a dry run. In the disposable Debian 13 VM, with the source checkout available:

```
python3 integration/vm_systemd_smoke.py
sudo env JATAYU_VM_SMOKE_ACK=YES python3 integration/vm_systemd_smoke.py --execute
```

Successful output includes `"worker": "completed"` and `"apt_touched": false`. CI tests only the script's safety gates; CI does not execute its systemd test. This proves neither live package-upgrade survival nor Polkit authentication. Both remain release blockers.
