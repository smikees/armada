# Record health and repair

M5 separates presentation from execution admission. `records.presentation` returns
either validated configuration or a diagnostic; it never returns a permissive
configuration for a damaged record. Native realm readers retain an agent/job entry
with `record_error`. Healthy siblings remain available. Affected detail pages show
the explicit repair form instead of ordinary execution/configuration controls.

The shared JSON loader rejects duplicate keys, non-object roots, invalid encoding,
non-finite constants, unsupported write schemas and invalid consumed field types.
Agent IDs and job IDs, when supplied, must match their directory/filename. Optional
legacy fields retain their existing defaults; the free-text job budget remains a
label, not an enforced dollar ceiling. Existing access-policy validation remains
authoritative and runs even for unused policies.

All model turns retain strict coordinator admission before provider selection.
Command jobs and automatic job/inbox dispatch validate the agent independently.
Invalid records hold automatic work without claiming/consuming a pending inbox
message. Ordinary editors cannot silently replace structurally damaged input.
Execution failures already admitted into a turn still produce durable error reports;
no presentation fallback authorizes a run.

History views show validated rows and report incomplete totals. Malformed rows,
duplicate keys, invalid numeric fields and unreadable encoding hold that agent's
scheduled jobs: an unreadable record might describe a completed external action.
Other agents continue. The scheduler preserves existing claims and never treats
damaged history as proof that a job has not run. An explicit owner Run now remains
a manual action; repair never replays a run.

## Explicit owner repair

`POST /api/repair-record` uses the existing owner authentication, origin checks and
immutable realm binding. It accepts an agent ID and optional job ID, not an arbitrary
path. Safe-segment and component/reparse checks constrain the target. The owner must
review the complete replacement JSON and permissions and submit the current SHA-256.
The shared file lock is acquired without validating the damaged input; realm/schema,
target path, replacement structure, policy and original digest are validated inside
the operation. A newer-schema record cannot be downgraded through repair.

Before replacement, `.armada/record-repairs/<unique-id>/` contains the exact original
bytes (`original.bin`) and `repair.json`: owner actor, time, relative target, original
and replacement hashes. The replacement is flushed using the atomic writer and
renamed over the target on the same filesystem. Failure before rename leaves the
original intact. A crash can leave unused evidence; the receipt and current file hash
distinguish that from an applied repair. Backups are owner-managed control files.

There is no automatic reset, JSON salvage, permission reconstruction or history-row
deletion. Missing/inaccessible records require restoring a verified backup. History
repair likewise requires preserving evidence and restoring verified data; the JSON
configuration editor does not invent missing outcomes. Realm/theme corruption and
other managed state retain their existing refusal/recovery contracts; this milestone
does not claim a general arbitrary-file repair tool or an OS hostile-code sandbox.

Tests use synthetic realms, mocked provider boundaries and an authenticated local
HTTP server. They cover sibling pages, automatic holds, command/provider refusal,
invalid repairs, stale review, evidence bytes, replacement failure and access control.
