# 0.99.128 — Verified exports and fresh, paused recovery

Published on GitHub and armada.stamih.com on 6 November 2026 from
`7d06e68cc4053012ea6d3bfe1a11b2ab0e111b0f`, after explicit owner approval.
M6 is implemented, verified and released. Maintainer acceptance remains pending.

M6 adds collision-resistant ZIP names, same-volume staging and atomic no-replace
publication after complete manifest/hash verification. Settings reports incomplete
copies and observed changes. Exports exclude observed links/reparse paths and must
be saved outside the realm. Durable scheduler claims, history and skill pins stay
in the archive; credential/cache/runtime omissions are recorded.

Owner CLI verification/recovery validates paths, member sets, hashes and resource
limits. Recovery creates a new paused Windows folder, never merges or registers a
realm, and retains access policy and past execution evidence. Incomplete copies
require explicit acknowledgement. See [the full contract](REALM_EXPORTS.md).

## Validation

- Mandatory publisher final-source gate: **4,139 passed, six skipped** in 653.56s.
  The earlier pre-publication local gate also passed 4,139 tests (six skipped).
- Focused export fault/recovery suite: **44 passed**. Related lifecycle, record and
  threat-model checks also pass in the full gate. Both changed golden pages were
  reviewed; generated references and Python/JavaScript syntax checks are current.
- Failure evidence includes source read errors, output failures, forced process
  exit, same-time exports, changing files, Windows junctions, hostile ZIP members,
  metadata limits and recovery publication failures/races.
- Windows file identity checks use lstat rather than DirEntry.stat, whose file IDs
  are zero; comparisons use identity, size and mtime rather than inconsistent legacy
  ctime values across path/descriptor APIs.
- Exact-source Windows CI: **4,141 passed, four skipped** on each Python job
  (3.14.10: 675.45s; 3.14: 811.24s). PHP relay passed.
  [CI run 42223624322](https://github.com/smikees/armada/actions/runs/42223624322).
  Both retain the existing Python warning in `voice_turns.py` at line 122, tracked for M8.
- Packaged launcher: all five recovery interruption points and DLL isolation with
  clean/legacy parents passed. WebView2 sessions: **16** checks; tray: **68**;
  visible/tray/busy restart: **69 each**.
- Signed compatible-runtime upgrade from **0.99.127 to 0.99.128: 72 checks passed**.
- Public HTTPS verification passed: manifest signature, exact release commit,
  package size/hash and changed source bytes, installer hash, and matching website
  version/release/installer links. GitHub has all four assets as a normal release.
- Website deployment backed up replaced files, verified uploads and published
  index.html last. Backup set: `20261106T133054Z`.
- Owner app was not restarted; no live realm or provider was used for tests.
- Release model preferences are unchanged. Connected-provider/catalogue filtering
  and unknown-model provider-default fallback remain authoritative; no live model
  or connector run is used for these tests.

Installer SHA-256:
`b2815fa748a4fbc6f5c43f289590b8c018ae3bbd8d3d6e604a7b154b9851303a` (23,254,561 bytes).

Package SHA-256:
`f9438f45dca321d244ed92f7f9595dd9268e0e631e29c02fc1defd5bdd3ccf07`.

## Remaining boundaries

A verified ZIP is not an authenticated author or a transactionally consistent live
snapshot. Named exclusions do not find secrets in arbitrary content. Restore does
not repair missing/corrupt records or make uncertain past work safe to replay.
Permissions/timestamps/external dependencies are not restored. Automated atomic
recovery is Windows-only and has no GUI yet; legacy archives require separate review.

This is an app-only change: bundled Python 3.14.10, baseline installer 0.99.125,
launcher protocol 2 and the existing unsigned beta boundary are unchanged. The
publisher-signing and clean-machine WebView2 acceptance gaps remain open. Windows
Sandbox was not rerun for this app-only change; this release makes no clean-machine
GUI acceptance claim. The owner-authorized unsigned maintenance path retains all
application/CI/native/upgrade gates and Ed25519 update signing.
