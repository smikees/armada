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

## Dry runs

Expand a job and choose **Dry run**, or open **Dry runs** on its **Edit job** page.
Choose an available **Test model**, then **Start dry run**. This choice applies only
to the test: the saved production model, schedule, enabled switch and production
outputs stay unchanged. A switched-off job can still be tested. Unsaved editor
changes are not included: save first to test a changed prompt.

The separate **Dry-run history** shows the selected model, outcome, final answer
and draft files. **Stop** stops the current dry run. Closing the page does not stop
it; reopen the job to review its result. Dry runs use quota and their token usage
is recorded, but they do not enter production job history or the calendar, consume
scheduled slots, retry automatically, or send ARMADA job notifications.

Model tests use **saved file inputs** from the realm, its workspace, and the job's
owner-approved input folders. Enable production tool capture below to make exact
connector responses available as inputs for model comparisons. Dry runs cannot
refresh live connectors, publish, send messages, or use unrestricted shell tools.
The agent uses ARMADA tools to read inputs and write temporary drafts; missing
inputs and skipped steps must remain visible. This tests draft quality rather than
end-to-end publication or the production tool chain.

Each test has a unique folder inside the realm:
`.armada/dry-runs/<agent>/<job>/<run-id>/`. Draft artifacts and `final-answer.md`
live in its `output/` folder; `run.json`, `job.json` and `transcript.json` preserve
the test identity, configuration and result. Tool capture, when configured, also
stays in this temporary tree. `{dry_run_dir}` in the job prompt expands to the
absolute draft folder. Scripts receive `ARMADA_DRY_RUN=1`, `ARMADA_DRY_RUN_DIR`
and `ARMADA_RUN_ID`.

Housekeeping removes the **whole completed test folder after seven days** by
default. Set **Edit job → Dry-run settings → Keep dry runs for days** (1–365) to
change retention for new runs; each existing test keeps its original retention.
Active tests are never pruned. Copy a useful draft elsewhere before it expires.
Interrupted tests are identified from their owned activity marker. Up to two dry
runs can be active in a realm at once.

**Command jobs** require a user-saved **Draft-only command** under Dry-run settings.
The production command is never substituted automatically. The test command must
already avoid sending, publishing and production writes, and write outputs into
`ARMADA_DRY_RUN_DIR`. It starts in that folder; use an absolute script path or
`{workspace}` to find inputs. Command arguments also support `{dry_run_dir}` and
`{run}`. ARMADA does not sandbox arbitrary scripts: the user is authorizing that
specific command's draft-only contract. Changing the command, its environment or
its production definition requires saving it again. Command tests have no model
selector because scripts do not use the job's model.

## Inspector agents

In **Agent → Configure → Advanced**, enable **Is inspector**, then **Save**.
This authorizes the inspector on this machine. Moving/importing a realm does not
carry this permission: save the setting on the new machine to authorize it there.
An agent cannot authorize itself by editing `agent.json`.

Inspector turns use scoped ARMADA tools to list any job in their realm, choose any
available model, start a dry run, and review its output. They can read all agents'
**recorded output artifacts**, including captured tool results, but cannot edit
other agents' files, change production models or jobs, or trigger production runs.
They write their own review artifacts in `agents/<inspector>/artifacts/`.
Shell, live connectors and publishing tools are unavailable in inspector turns.
Disabling the setting revokes their review tools immediately. Ordinary agents do
not receive inspector tools.

For example: “Compare the latest digest artifacts with a dry run using an available
lower-cost model. Record any missing inputs and recommend whether I should change
the production model.” An inspector may start at most four tests per conversation
turn; it can poll an asynchronous test and return in a later turn to review it.
Changing the production model remains a user action.

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
the final outcome notification after recovery or exhaustion. The calendar shows one entry
for a proven retry series, with its final outcome and attempt count. Open it to inspect each
attempt without treating retries as separate scheduled jobs.

Provider startup failures are shown as **Not started — provider environment unavailable**
and do not consume business-job retries. On Windows, Codex first executes a harmless sandbox
readiness command and checks the selected model. If the desktop runtime fails, ARMADA can use
an independently installed standalone Codex CLI after it passes those checks. The report
records this fallback. Your login, model choice, grants and sandbox policy are preserved;
ARMADA does not install CLIs or silently change a model. Repair/update Codex or choose an
available model when the report requests it. Claude connector health discovery has a bounded
90-second budget because it checks the configured connector inventory before the turn.

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
does not establish a clear audit or clear an unresolved risk gate.
A delivery failure is separate from the execution that produced the report. Runtime errors,
timeouts and stops are shown under Armada errors, separate from the agent's original answer.

Output evidence, missing inputs, findings and delivery receipts are attached to the individual
run. Delivery is verified only by a receipt for that run and destination. An earlier receipt
does not prove a later delivery. Historical corrections appear as annotations, preserving the
original status, error and final answer without repeating the job or its deliveries.

Older `ARMADA_JOB_RESULT: SUCCESS/FAILED` results are marked **less detailed**. Their explicit
result and explanation remain available; SUCCESS does not establish a clear audit.

Research jobs can record ordinary facts in `observations` and optional future announcements
in `expected_unknowns`. These are distinct from audit/rule breaches (`findings`) and unavailable
required evidence (`missing_inputs`). Actual contradictions or unresolved risk gates still
produce warnings; older reports are preserved with their original evidence.
