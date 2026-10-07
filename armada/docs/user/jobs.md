# Jobs

Everything that runs on a schedule, in one list. **User** is your team's jobs; **System** is the
upkeep ARMADA does for itself (refreshing the model list, checking capabilities for updates,
pruning old history).

## Reading the list

Each row: the job and what it does, its kind (**agent** runs a prompt, **command** runs a command
on your computer), its owner, its **model and effort**, its cadence, its **cost** (*free* for a command, *uses quota* or a
typical token count for an agent job), its next run, the seven-day **week strip**, and an on/off
switch.

The week strip is the last three days, today and the next three: **Success**, **Running**,
**Scheduled**, **Warning**, **Failed**, **Missed** (✕ — due and didn't run), **Not scheduled**.
Today's larger square shows the latest scheduled run's status, or the current run while it is
working. Before today's first scheduled time it shows **Scheduled**; an overnight catch-up of
yesterday's job does not count as today's later run. Catch-up attempts stay tied to the scheduled
day so crossing midnight cannot automatically repeat yesterday's work or consume today's slot.

Expand a job, then open **Prompt**, **Output** or **Run history**. Each section uses the full
width and can be collapsed independently. The output uses the same
formatted responses and activity details as Threads, and refreshes while a job runs. Choose an
earlier run in the output dropdown or click its timestamp in the run history. Job output stays
in Jobs instead of appearing in conversations.

On **Edit job**, model, effort and output verbosity each inherit from the agent by default.
Choose an override to use a different combination for this job; choose **Inherit agent** to
follow the agent's settings again. Command jobs run scripts and don't use these model settings.

## Capture tool results to files

In **Jobs → Edit job → Capture tool results**, enter one full tool-name glob per line.
Capture is off when this list is empty. For example:

```json
{
  "capture_tools": ["mcp__*Interactive_Brokers*__get_*"],
  "capture_dir": "Finance\\data\\raw\\{date}\\{job}\\",
  "require_capture": true,
  "capture_keep_days": 30
}
```

Patterns are case-sensitive and match the whole tool name (`*`, `?` and `[abc]` work).
Only matching calls are saved. Capture does not grant tools or authorize trades.
It writes locally and does not send a copy to another service.

The folder is relative to **Settings → Realm → Workspace**, which must exist.
The default is `Finance\data\raw\{date}\{job}\`. Folder placeholders are `{job}` (job ID),
`{date}` (local date at run start) and `{run}` (unique run ID). Use `raw\{job}\{run}`
for a separate folder per run. Shared folders use increasing sequence numbers;
retries and simultaneous jobs cannot overwrite earlier captures. Absolute paths,
traversal, Windows device names, symlinks and junctions are refused at save time
and checked again during writes.

Put **`{raw_dir}`** in the prompt to expose the absolute folder. Scripts launched
by the agent inherit **`ARMADA_RAW_DIR`** from the engine process:

```python
import hashlib
import json
import os
from pathlib import Path

raw_dir = Path(os.environ["ARMADA_RAW_DIR"])
rows = [json.loads(line) for line in
        (raw_dir / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
# In a shared folder, filter rows by the current run_id first.
for row in rows:
    received = (raw_dir / row["file"]).read_bytes()
    assert hashlib.sha256(received).hexdigest() == row["sha256"]
```

Each matching call writes `<seq>-<tool>.json` and adds a line to `manifest.jsonl`
as its result reaches ARMADA. Both use temporary files and atomic rename; the
manifest only advertises completed payload writes. Entries record `seq`, `tool`,
`arguments`, `started`, `finished`, `run_id`, `job_id`, `agent_id`, `is_error`,
`byte_size`, `sha256`, `file` and `encoding`. Times are ISO 8601 with offsets;
`started` is null if the CLI exposes only the completion. Sequence numbers are
scoped to the folder and can have gaps after interrupted writes.

The saved boundary is **what the CLI exposed to ARMADA**, before the short UI
preview. JSON objects and arrays retain numeric spelling, whitespace and key
order. Text is decoded once and written as UTF-8 without trimming or newline
conversion. Every payload uses the `.json` extension; `encoding: "text"` may be
arbitrary text rather than a JSON document. `is_error` describes the tool result,
not capture failure. CLI-side transformations or truncation cannot be recovered.

Claude captures the sibling `tool_use_result` for a single result when available,
otherwise the result block's `content`. Codex captures the completed MCP item's
`result` (or `error`). Gemini through Antigravity captures `tool_info.output` (or
`error`), mapping its server/tool names to `mcp__server__tool`. All three current
engines expose results. An engine without this ability, including a command job,
reports capture as unsupported. Gemini's existing shell restrictions still apply.

A later script or file tool in the same run can read completed files. The CLI and
ARMADA consume the stream concurrently: briefly retry the manifest read if the
immediately preceding result has not arrived yet. Do not retype missing raw data.

**Run history** shows the count and manifest link. The run transcript separately
retains complete matching payloads and hashes. A write error, missing result or
unsupported engine produces **Capture incomplete** with the reason in the audit.
Capture errors never interrupt execution. **Fail the run if capture is incomplete**
(`require_capture: true`) marks the final result **Failed**; otherwise it is a warning.

The existing **Prune old history** system job removes expired registered capture
files and their manifest entries after `capture_keep_days` (default 30, minimum 1).
It preserves other runs, unregistered files, modified files and active captures.
Run transcripts follow normal run-history storage; capture-file retention does
not delete them. If the workspace moves, old files remain untouched and retention
reports that it could not validate their location.

## Things you'll do

- **Filter** by owner, status or cadence, or search by name.
- **Switch the calendar on:** the calendar icon beside the list icon.
- **Stop a job without deleting it:** the switch on its row.
- **Run it now, edit it, see its history:** open the job.
- **Approve what an agent proposed:** proposals appear at the top of the list (and under
  Approvals). Approve and it's scheduled; dismiss and it isn't.

## Paused jobs

If a scheduler or app process stops during a job, Armada keeps its attempt record and avoids
automatically repeating uncertain work. Check the run report and any external changes before
using **Run now** to retry. A retry may repeat changes that already succeeded. System jobs show
an explanation when an attempt is in progress or interrupted; switching a job off and on does
not clear that record. User jobs remain eligible on their next scheduled day.

If the realm's scheduled jobs are paused, a banner at the top of the Jobs page says why.

- **A realm added from an existing folder** starts paused. The banner lists every command it would
  run on your computer, word for word, and how many agent jobs it has. Read them; if you're happy,
  **Review done — let them run**. Nothing runs until you do.
- **Something the realm needs is missing** — the workspace folder doesn't exist on this computer,
  or Claude isn't signed in. Fix it (usually Settings → Realm) and the jobs resume on their own.

## When a job didn't run

**On failure** in Edit Job offers **No retries**, **1 retry**, **2 retries** or **3 retries**.
These are additional attempts after the first run, with waits of 30 seconds, 1 minute and
2 minutes. Each attempt has its own run ID, output and result in Run history. Armada sends
the final outcome notification after recovery or exhaustion.

Completed reports with findings or missing evidence are not rerun. Stopped runs, admission
errors, malformed results and confirmed or uncertain delivery require inspection instead
of blind replay. A safely recorded retry wait can resume after an app restart; an interrupted
attempt with an unknown outcome remains held. Disabling the job or archiving its realm cancels
a queued retry. Legacy “Retry ×3, then alert me” choices are interpreted as three retries.

1. Is it switched on?
2. Is the realm paused? (the banner above)
3. Is ARMADA open or in the tray? Scheduled jobs stop after a full quit. Opening ARMADA starts
   its scheduler automatically, including after an update. A background supervisor recovers
   unexpected scheduler exits while the app is open or in the tray. Startup and recovery do not
   show a warning. If three recovery attempts fail, a yellow bar shows the recorded reason and
   offers **Retry**. Automatic startup being deliberately disabled is also shown explicitly.
4. Open the job: its last run says what happened, including the error.

More in [When something goes wrong](troubleshooting.md).

## Understanding results

Open a run to see **Execution**, **Audit** and **Delivery** independently. A completed
report may contain findings or an incomplete audit. Such runs retain a warning: completion
does not mean the portfolio passed its checks or that an unresolved risk gate is cleared.
A delivery failure is separate from the execution that produced the report. Runtime errors,
timeouts and stops are shown under Armada errors, separate from the agent's original answer.

Output evidence, missing inputs, findings and delivery receipts are attached to the individual
run. Delivery is verified only by a receipt for that run and destination. An earlier receipt
does not prove a later delivery. Historical corrections appear as annotations, preserving the
original status, error and final answer without repeating the job or its deliveries.

Older `ARMADA_JOB_RESULT: SUCCESS/FAILED` results are marked **less detailed**. Their explicit
result and explanation remain available; SUCCESS does not establish a clear audit.
