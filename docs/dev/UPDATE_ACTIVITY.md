# Update draining and visible work

13 November 2026 — implementation following the v0.99.146 update report.

The desktop rechecks update progress every second; the scheduler also checks while
draining. The banner was not a permanently cached blocker list. Two disagreements
made a valid wait look stale: system-job claimed attempts always displayed as held,
and the UI ignored running markers after 30 minutes while the updater used live PIDs.
A nested inbox ticket waiting for a subscription reset/reserve could also keep its
system dispatcher and RunSession alive indefinitely during update preparation.

Admission now refuses promotion while an update is pending. A queued ticket unwinds
through its existing cancellation/result path, including nested inbox waits; running
tickets continue. Nothing is silently replayed when an update is postponed. Scheduled
queued attempts retain their stopped outcome and can be retried explicitly.

RunSession activity holds a kernel ownership lock until cleanup. Job-series markers
refer to their existing invocation lock. Both presentation and update blockers use
this evidence, so old timestamps cannot hide work and abandoned new markers cannot
block an update merely because their process ID is still alive. Legacy marker PIDs
remain conservative until that process exits; no timeout guesses that work is dead.
System jobs similarly probe their execution lock: held without a live lock means
interrupted; a held lock means running. Queue tickets have a distinct queued state.

Chat clears text/attachments only after the successful admission response. Rejected
or unconfirmed requests keep the draft, without automatic replay. The canonical
thread snapshot reports update admission state to both main and detached views;
Send is disabled during a known pause and the composer explains how to postpone.

Activity shows separate working and queued avatar rows and live system work.
The calendar API includes live system definitions independently of dated events,
so even an empty user-job calendar shows frequent Inbox and Telegram processing.
Every month/week/day view puts this section first. Hourly/daily date projections
include known outcomes and do not invent successful skipped runs. System lists poll
every five seconds, calendar views every fifteen seconds and Activity every ten
seconds while visible, in addition to its completion signal/manual refresh.

Regression coverage: `test_update_activity.py`, the sender/observer Node harness,
the calendar Node harness, and `owner_workflow_probe.py --system-jobs-only` for
native light/dark/scaled geometry and every calendar view in both Jobs panes.
All fixtures are synthetic; no owner's realm or live job is modified.

Validation on source commit `8f2583805ed2241bf41bc48410e2c58fdff701ab`:

- Pinned isolated regression gate: **4,564 passed, 6 skipped**, 999.83 seconds;
  `build/update-activity-tests.log`.
- Clean-source stabilization gate: **passed**, 398.81 seconds;
  `build/stabilization-update-activity.json`, evidence directory
  `build/stabilization-20261113-185738-985701`.
- **98 native owner-workflow checks**, including all calendar views, and three
  successful native main/detached conversation lifecycle runs.
- **52 dedicated native calendar/layout checks**, including automatic live
  system-job transitions, narrow windows, both themes and 150% scaling;
  `build/update-calendar-native-final.json`.
- Golden diffs reviewed: shared server icon registration, the queued Activity row,
  system detail refresh targets, calendars for empty-job realms and updated help.

These changes are published in v0.99.147 on GitHub and the Armada website. The
owner's running installation was not restarted or modified during publication.
The final source passed 4,578 local tests, exact-source Windows CI, stabilization,
98 staged owner workflows and 72 signed-upgrade checks. See
[release validation](RELEASE_0_99_147.md) for final publication evidence.
