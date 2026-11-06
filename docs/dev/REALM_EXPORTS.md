# Realm exports and recovery

M6, November 2026. `realm_export` owns the copy/manifest/recovery contract;
`realmops.export` remains the caller facade. Settings uses the same implementation.

## Publication and consistency

Exports use a second-resolution timestamp plus a random ID. They stage on the
destination volume under `.armada-export-*.partial`, close and fsync the ZIP,
verify every archived file, then publish with a no-replace atomic operation.
An existing ZIP is never replaced, including after a filename collision. Handled
failures clean up staging; a killed process can leave a recognizable `.partial`
file, never a successful-looking ZIP. No automatic cleanup races active exports.
Atomic publication does not promise durability across every filesystem/power failure.

The destination must be outside the source realm. This intentionally replaces the
old behavior that permitted archives inside the tree and could copy earlier
backups recursively. The normal Settings destination remains beside the realm.

This is a **live copy, not a point-in-time snapshot**. Individual files are spooled
in bounded chunks and checked for stable file identity, size and modification time
before and after reading. A second inventory detects additions, removals and changes.
Neither check is a transaction across the realm; a concurrent writer can change and
restore a file between observations. Finish work and close other writers before
making a recovery copy when consistency matters. Export does not pause or restart
the owner's app. It does not defend against a hostile process running as the same
OS account and racing path checks; it rejects observed symlinks, junctions, reparse
points and special files, including linked source/destination ancestors.

Source read failures, unsafe/linked paths and observed changes make the copy
**incomplete**, visibly in Settings and in its manifest. Failure to write the
archive or its spool, verify it or publish it fails the operation. No partially
read file becomes a member. `ok` means a verified archive was saved; callers must
also check `complete`. Completeness is relative to the documented exclusions.

## Contents and limits

The version-1 manifest lives at `<realm>/.armada-export.json`, contains relative
file paths, sizes and SHA-256 hashes, empty directories, full omission reasons,
observed changes, timestamps, export ID and application version. The source cannot
already contain that reserved filename. Result/UI path samples are bounded; the
manifest retains the full list. Metadata alone does not authenticate the archive's
author: someone who can rewrite files and hashes can create a different valid ZIP.

Excluded, and recorded:

- Named credential files: `.mcp.json`, `.env`, `.env.*`, `credentials.json`,
  `.credentials.json`, `secrets.json`, `telegram.json`, and `.env`, `.pem`, `.key`,
  `.pfx`, `.p12` suffixes. This is filename-based exclusion, **not secret scanning**.
  Conversations, output and arbitrarily named files may still contain private data.
- Cache directories: `__pycache__`, `.git`, `.venv`, `node_modules`.
- Runtime markers: `.running` directories, `.tmp-*` files, hidden `.*.lock` files
  and root `scheduler.lock.json`. Durable `.scheduler/attempts` claims, history,
  `system_jobs.json` and skill `manifest.lock` files are preserved.

Limits: 20,000 source entries, 4 GiB per file, 20 GiB total payload, 8 MiB manifest,
16 MiB central directory. The central directory is bounded before ZIP metadata is
allocated. Single-volume ZIP and ZIP64 are supported; unsafe layouts, encryption,
duplicate/case-alias paths, traversal, Windows devices/ADS/trailing-dot aliases,
links, file/directory conflicts and unlisted members fail verification. Content
verification/extraction streams in 1 MiB chunks. Limit failures produce a clear
error or a documented file omission, never an unchecked archive. Copy/verification
uses extra disk and I/O; free space must cover the ZIP plus the largest file spool.

## Recovery

Owner commands (in a checkout or bundled Python environment with ARMADA on its path):

```powershell
python -m armada backup verify "D:\Backups\SyntheticRealm-export.zip"
python -m armada backup restore "D:\Backups\SyntheticRealm-export.zip" "D:\Realms\Recovered"
```

Verification is read-only. Legacy ZIPs have no manifest and cannot pass this check;
retain them, inspect their contents manually and recover into a separate folder.
They are not silently labelled verified. A complete manifest checks bytes, not
whether every application record is valid or every job can safely run.

Automated recovery currently supports **Windows** (atomic no-replace directory
rename); other platforms fail without mutation. The destination's parent must
exist and its final folder must not exist, even if empty. Recovery validates paths
and all hashes before staging, rechecks hashes while extracting, pauses the copy,
then publishes it. It never merges, overwrites or registers a realm, starts an app,
calls a provider, or executes restored content. Failed staging is removed; a hard
process exit can leave `.armada-restore-*` beside the intended destination. Do not
add that staging folder to ARMADA.

The recovered `realm.json` is archived and all native/legacy job switches and
known/existing system jobs are disabled. Access policy and durable claims/history
are retained; malformed settings that cannot safely be paused refuse recovery.
The original ZIP remains the evidence for the original bytes. The generated
manifest is not copied into the recovered realm, so that realm can be exported
again. Permissions, file timestamps and external dependencies are not restored.

Incomplete recovery requires an explicit `--allow-incomplete` after reviewing the
manifest. It cannot reconstruct missing files. Review the new folder, repair any
damaged records, reconnect credentials, review workspace paths and uncertain past
work, then use **New realm** to add it. Adding releases the archive hold but leaves
job switches off. Enable reviewed jobs deliberately. Recovery does not erase
claims to make jobs runnable, and does not promise that incomplete live state can
be resumed safely. A graphical restore flow is not part of M6.

Tests use synthetic realms only: concurrent exports, no-clobber publication,
output/read failures, forced process exit, observed changes, junction escape,
malformed/hostile ZIPs, ZIP64, limits and fresh paused recovery/failure paths.
