# 0.99.128 — Verified exports and fresh, paused recovery

Candidate implementation; publication and maintainer acceptance are pending.

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

- Full pinned isolated gate: **4,139 passed, six skipped** in 660.73 seconds.
- Focused export fault/recovery suite: **44 passed**. Related lifecycle, record and
  threat-model checks also pass in the full gate. Both changed golden pages were
  reviewed; generated references and Python/JavaScript syntax checks are current.
- Failure evidence includes source read errors, output failures, forced process
  exit, same-time exports, changing files, Windows junctions, hostile ZIP members,
  metadata limits and recovery publication failures/races.
- Windows file identity checks use lstat rather than DirEntry.stat, whose file IDs
  are zero; comparisons use identity, size and mtime rather than inconsistent legacy
  ctime values across path/descriptor APIs.
- The publisher will repeat the final-source suite. Exact-source Windows CI,
  packaged native lifecycle, signed upgrade and public signature/download/website
  verification remain pending.
- Release model preferences are unchanged. Connected-provider/catalogue filtering
  and unknown-model provider-default fallback remain authoritative; no live model
  or connector run is used for these tests.

## Remaining boundaries

A verified ZIP is not an authenticated author or a transactionally consistent live
snapshot. Named exclusions do not find secrets in arbitrary content. Restore does
not repair missing/corrupt records or make uncertain past work safe to replay.
Permissions/timestamps/external dependencies are not restored. Automated atomic
recovery is Windows-only and has no GUI yet; legacy archives require separate review.

This is an app-only change: bundled Python 3.14.10, baseline installer 0.99.125,
launcher protocol 2 and the existing unsigned beta boundary are unchanged. The
publisher-signing and clean-machine WebView2 acceptance gaps remain open. No owner
app restart or live realm/provider testing is authorized by this release procedure.
