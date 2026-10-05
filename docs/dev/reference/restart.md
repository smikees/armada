# `armada/restart.py`

Prepare a monitored desktop handover before the old process releases its server.

### `lease_blockers(root, permitted)`

Report kernel-held installation leases, excluding this app and its scheduler.

### `state()`

—

### `begin(root, realm, port, version, scheduler_required)`

Start a lease-free supervisor and wait for its acknowledgement before shutdown.
