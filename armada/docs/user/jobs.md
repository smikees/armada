# Jobs

Everything that runs on a schedule, in one list. **User** is your team's jobs; **System** is the
upkeep ARMADA does for itself (refreshing the model list, checking capabilities for updates,
pruning old history).

## Reading the list

Each row: the job and what it does, its kind (**agent** runs a prompt, **command** runs a command
on your computer), its owner, its cadence, its **cost** (*free* for a command, *uses quota* or a
typical token count for an agent job), its next run, the seven-day **week strip**, and an on/off
switch.

The week strip is the last three days, today and the next three: **Success**, **Running**,
**Scheduled**, **Warning**, **Failed**, **Missed** (✕ — due and didn't run), **Not scheduled**.

## Things you'll do

- **Filter** by owner, status or cadence, or search by name.
- **Switch the calendar on:** the calendar icon beside the list icon.
- **Stop a job without deleting it:** the switch on its row.
- **Run it now, edit it, see its history:** open the job.
- **Approve what an agent proposed:** proposals appear at the top of the list (and under
  Approvals). Approve and it's scheduled; dismiss and it isn't.

## Paused jobs

If the realm's scheduled jobs are paused, a banner at the top of the Jobs page says why.

- **A realm added from an existing folder** starts paused. The banner lists every command it would
  run on your computer, word for word, and how many agent jobs it has. Read them; if you're happy,
  **Review done — let them run**. Nothing runs until you do.
- **Something the realm needs is missing** — the workspace folder doesn't exist on this computer,
  or Claude isn't signed in. Fix it (usually Settings → Realm) and the jobs resume on their own.

## When a job didn't run

1. Is it switched on?
2. Is the realm paused? (the banner above)
3. Is the **scheduler** running? Jobs run from a separate background process, not the window.
   Opening ARMADA starts it; if it isn't running, a yellow bar under the menu says so and offers
   **Start it**.
4. Open the job: its last run says what happened, including the error.

More in [When something goes wrong](troubleshooting.md).
