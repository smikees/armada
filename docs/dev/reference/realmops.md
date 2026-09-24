# `armada/realmops.py`

Realm lifecycle — archive, export, delete.

A realm is potentially years of an agent team's memory, threads and artefacts, so these three
operations are deliberately very different in how much they destroy:

* **Archive** touches no files at all. It only drops the realm from ARMADA's list, so the folder
  stays exactly where it is and can be added back later. This is the one to reach for.
* **Export** writes a .zip of the whole folder next to it — the thing you want when moving to
  another machine. Read-only with respect to the realm.
* **Delete** removes the folder. On Windows it goes to the Recycle Bin rather than being shredded,
  because that's what "delete" means to someone using the app, and because a mistake here is
  otherwise unrecoverable. If the Recycle Bin isn't available we say so instead of quietly
  escalating to a permanent wipe.

Deletion also refuses to touch the realm ARMADA is currently serving: switch away first. That
avoids the app pulling the floor out from under itself mid-request.

### `_is_secret(name: str)`

—

### `_same(a, b)`

—

### `export(realm_root, dest_dir=None)`

Zip the realm folder. Returns {ok, path, files, bytes} plus {skipped, skipped_n} if any file could not be read — see below for why that is reported rather than swallowed.

### `_recycle(path: Path)`

Send a folder to the Recycle Bin via the Windows shell. Recoverable by design.

### `delete(realm_root, current_realm=None, permanent: bool=False)`

Delete a realm's folder. Recycle Bin by default; `permanent` only on explicit instruction.
