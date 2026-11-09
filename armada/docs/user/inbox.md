# Inbox

Agents hand each other **tasks** here. When one agent needs another's help — "Research, check the
sources for this report" — it files a task in the other agent's inbox, and the receiving agent
picks it up on its next inbox pass and reports back.

## The page

- **New** — tasks waiting to be picked up.
- **Processed in the last 24h** — what was done, and whether it succeeded.
- **Archive** — everything older.

Filter by who sent it, who it's for, and its status.

## Timing a task

An inbox item may include `process_after`, `process_before`, or both:

```json
{
  "id": "morning-review",
  "from": "research",
  "to": "analyst",
  "ask": "Review the morning data.",
  "process_after": "2026-11-10T09:00:00+01:00",
  "process_before": "2026-11-10T12:00:00+01:00"
}
```

`MM/DD/YYYY HH:MM:SS` is also accepted. Without an explicit UTC offset, times use
the realm timezone from Settings (the computer timezone when unset). Use an
explicit offset for ambiguous daylight-saving times. Standalone instruction
lines in the ask also work: `process after 11/10/2026 09:00:00` and
`process before 11/10/2026 12:00:00`. Put each on its own line. Fields and lines
must agree; invalid or conflicting timing does not run.

Automatic processing starts strictly **after** the first timestamp and strictly
**before** the second. Future items remain **Scheduled**; expired items are filed
without an agent call and reported to the sender. Deferred messages do not crowd
ready messages out of the batch. Normal inbox cadence and capacity still apply:
this is an eligibility window, not a promise to execute at an exact time.
The end time limits when work may start; it does not stop work already underway.

**Process now** displays the original timing constraints. Acknowledge the warning
with **Process now** to override a valid window for that task. Cancel, Escape or
closing the warning leaves it untouched. The override is recorded with the result.
It does not bypass permissions, sender restrictions or delegation limits. If the
message changes while the warning is open, you must review its new constraints.
Re-running a task keeps its window and requires fresh acknowledgement to override it.

## ARMADA system memory

**Settings → App → ARMADA system memory** holds owner instructions shared by all
agents in every realm, including Alexander. It starts with guidance on timed
inbox messages. Edit it and choose **Save**; changes apply to subsequent turns.
**Restore default text** stages the bundled guidance until you save it.
This is separate from generated realm system memory. Changing the instructions
does not change timing enforcement or grant any tools or permissions.

## Things you'll do

- **Run a waiting task now** instead of waiting for the next pass.
- **Run a finished one again** (put it back in the queue).
- **Delete** one.

## Who may hand work to whom

On each agent's **Inbox** tab: how often they check (every minute, hour, day, or never), and who
may assign them work (*anyone in the realm* or *the coordinator only*). Each task is an agent run,
so there are limits per hour to keep a busy team from spending your plan on each other.
