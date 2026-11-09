# Timed inbox tasks and app system memory

9 November 2026, 0.99.136. Timing is an admission rule, not a prompt convention.

`inbox_timing.window` validates optional top-level `process_after` and
`process_before` strings plus standalone `process after ...` / `process before ...`
lines in `ask`. Accepted formats are MM/DD/YYYY HH:MM:SS and ISO timestamps with
seconds and optional offsets. Offset-free values use the realm's IANA timezone,
falling back to the machine timezone only when the realm uses local time. Invalid
zones, malformed dates, ambiguous/nonexistent DST wall times and conflicting
bounds fail closed. Both boundaries are exclusive; after must be before before.
Messages without timing preserve existing behavior.

`send` stores canonical UTC fields and display-only original inputs. The window
participates in deduplication. Direct agent-written inbox JSON is validated too.
Batch selection excludes deferred messages before applying its cap. Expired or
invalid tasks are filed without invoking an agent; their reason reaches the sender
and does not consume the delegated-run hourly allowance. Claim locks the pending
record, rereads its current contents and checks admission before the atomic move.
The turn coordinator checks timing before provider preparation, after capacity
admission, before compaction and immediately before model execution.

Owner **Process now** first returns a warning and a digest of the exact record.
The authenticated owner request must acknowledge that digest. Claim compares it
again under the file lock, so concurrent edits invalidate consent. A valid override
is carried as an explicit `TurnRequest` attribute, never inferred from fields in
agent-written JSON or a job. It bypasses timing only. Sender rules, capabilities,
capacity and other admission checks remain active. The outcome records the owner
override, timestamp and constraints; the prompt names the owner's one-run exception.
Requeue removes that consent. Invalid timing must be corrected, not overridden.

This is a start window, not cancellation of an already-running task or an exact-time
scheduler. Unrestricted native tools/shell are not a filesystem security sandbox:
this gate controls ARMADA's inbox dispatch, not arbitrary independent reads of raw
inbox files by an already-authorized process. The bundled instructions tell agents
not to execute deferred inbox items through another task.

Installation-wide owner text lives in `~/.armada/config.json` as `system_memory`.
Missing means bundled guidance; an explicitly saved empty string means no additional
text. Reads never seed/write files. Writes use the shared lock and atomic writer,
validate the 16,000-character limit, record a change timestamp and reject stale
editor revisions. Corrupt configuration stops context assembly rather than silently
dropping owner instructions. Settings shows the load error without replacing data.
The existing authenticated Settings API owns editing. The common memory assembly
adds the text to all provider turns and context accounting; Alexander also receives
it. Realm export does not move machine-level instructions or owner settings.

Synthetic tests cover boundaries, timezones/DST, malformed direct files, stale
claims/confirmations, expiry during capacity waits, one-time manual overrides,
all three provider contexts, stale editor saves and corrupt state preservation.
`tools/inbox_timing_probe.py` exercises native Settings Save/Restore and inbox
warning Cancel/Process now. It uses temporary homes and a fake recipient turn,
never the owner's app, real realms, providers or actual queued messages.
