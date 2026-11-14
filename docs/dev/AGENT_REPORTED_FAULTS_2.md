# Job proposals, scheduled occurrences and interrupted conversations

Investigated on 14 November 2026 against 0.99.149; fixed in 0.99.150.
Regression fixtures use synthetic agents, jobs and connectors. Live realm files,
credentials and broker registrations were not changed.

## Existing-job proposals

`jobs.approve` explicitly rejected an existing ID. Editing the live JSON instead
invalidated the owner seal, with no proactive seal-change notification. A pending
proposal now resolves its target separately, renders every field difference and
binds approval to a digest of the proposal, current job, approved snapshot and
existing extra access. A stale card cannot overwrite a newer edit. Reject affects
only the pending file. Owner approval writes the replacement and renews the seals.

Own-job proposals remain available to agents. Cross-agent changes require a realm
owner setting and a coordinator identity captured when that setting is saved;
editing an agent's coordinator flag afterward does not grant this authority.
The owner can see retained extra access and completion checks before approving.
New approvals retain their complete snapshot; older approvals explicitly fall
back to comparing the saved file when no approved snapshot exists.

The scheduler checks seals before the job's due time and emits one review notice
per changed version. It does not silently approve, restore or rewrite job files.

## Multiple scheduled times

Both `_first_fire` history filtering and daily-only durable claim keys suppressed
later cron matches. Multi-time schedules now claim each local minute separately.
Single-time schedules keep their existing daily key. Repeated ticks, restarts,
midnight catch-up and the repeated DST hour cannot replay an occurrence. Catch-up
selects the latest eligible occurrence rather than replaying the entire backlog.
Existing daily claims remain authoritative on their original day during upgrade.
Uncertain claims continue to hold later same-day occurrences for review; live
overlaps retain the existing skip-and-notify path. Wait state is tied to the fire
time, so a completed morning wait does not suppress an afternoon occurrence.

## Connector checks

The first wait evaluation required a check timestamp at or after that evaluation,
discarding healthy pre-fire readings and immediately notifying on the resulting
wait. A healthy reading under five minutes old now counts. A confirmed unhealthy
reading notifies immediately; an absent/stale first reading waits quietly until
five minutes have passed. Starting after a silent check sends no recovery notice.
The owner can request a recorded check from the monitoring modal at any time.
Checks remain asynchronous, coalesced and free of model calls/provider slots.

## Interrupted chats

The reported failure has a terminal run record, but its owner/assistant messages
are absent. The history revision changed at 17:47:37, corresponding to the reported
resend. This supports a later history rewrite as the removal mechanism; the
available evidence cannot prove which UI action produced that rewrite.
The execution path already completed error turns, but Edit/Restart unconditionally
truncated them and no independent interruption receipt informed the next run.

Owner input is now persisted before engine preparation. Failed turns retain their
partial output, error/reset text, interruption time, run ID and observed file
changes. An independent receipt survives compaction, and Edit/Restart preserves
the interrupted exchange. Subsequent context identifies the prior run and advises
inspection before replaying side effects. Run history also stores the request and
receipt. Successful write-tool receipts, captured artifacts and job-file hash
changes contribute paths; arbitrary shell effects remain incompletely observable,
and job-file changes can include concurrent edits. No historical work was replayed
or retroactively labelled successful.

Edit/Restart now checks truncation responses before removing UI content or sending
a replacement. History editing is refused while that conversation has active work.

## Validation

Tests cover reviewed approval, stale review rejection, opt-in coordinator scope,
self-promotion denial, proactive held-job notices, every quarter-hour occurrence,
duplicate ticks, uncertain claims, fresh/silent/outage waits, and a simulated
mid-turn plan refusal whose file evidence survives Restart and reaches the next
engine prompt. The native owner journey verifies the real proposal card and
on-demand heartbeat; the native thread journey exercises both window types.
Release-specific full-suite, stabilization and public-download evidence is recorded
separately after publication.
