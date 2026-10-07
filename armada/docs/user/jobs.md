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
