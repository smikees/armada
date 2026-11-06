# `armada/realm_export.py`

Verified portable realm copies. A live copy is never a point-in-time snapshot.

See docs/dev/REALM_EXPORTS.md for exclusions, resource limits and recovery semantics.
The manifest detects damage, not a malicious author who can replace it and its hashes.

### `is_secret(name)`

—

### `_parts(name)`

—

### `_linked(st)`

—

### `_plain_path(path)`

Reject linked ancestors as well as the final component, before resolving.

### `_signature(st)`

—

### `_inventory(src)`

—

### `_capture(src, rel, signature, spool)`

Read bounded chunks; source read failures alone are recoverable omissions.

### class `ExportWriteError`

Writing the backup failed; never downgrade to a partial success.


### `export(realm_root, dest_dir=None)`

—

### `_json(raw)`

—

### `_open_archive(path)`

Bound the central directory *before* ZipFile allocates its entry objects.

### `_verified(archive, extract_to=None)`

—

### `verify(archive_path)`

Check every byte against the manifest; this is integrity, not author authentication.

### `_hold_restored(root)`

Pause definitions without resetting any execution claims/history or access policy.

### `restore_copy(archive_path, destination, *, allow_incomplete=False)`

Windows recovery to a new directory; never register, launch, or merge a realm.
