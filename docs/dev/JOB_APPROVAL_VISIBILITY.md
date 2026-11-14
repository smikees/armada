# Saved-job approval visibility and calendar cleanup

Implemented in v0.99.152, 15 November 2026.

The runner checked owner approval, but Jobs rows only used history and projected
cadence. A changed saved job therefore looked scheduled even though admission
would hold it. Both realm and agent Jobs views now use a read-only approval check,
including stale extra-access grants. A badge, reason, review action and status
filter expose the hold; Run now is disabled and the next-run cell says Needs
approval. Future calendar entries carry the same state. Broken records and tool
configuration warnings also appear in the review filter. Historical outcomes stay
unchanged. Opening a page never re-seals or migrates an approval.

The separate live System jobs panel was duplicated above all calendar views.
It has been removed. Minute-frequency jobs previously relied on that panel and
were excluded from the date grid; their recorded runs, current activity and next
due occurrence now appear as individual server-icon entries without projecting
hundreds of future minute slots. Hourly/daily projection and refresh remain.

Regression tests cover changed prompt, schedule, critical flag, timeout and API
policy, stale or malformed extra-access grants, missing approval, unreadable
approval state, legacy compatibility without writes, broken records, future holds
and frequent system entries. The JavaScript harness exercises both calendar scopes
in month/week/day views, status updates, escaping and refresh failures. Native
owner workflows verify visible approval controls and filtering at three widths,
plus calendar entries and the absence of the duplicate section. Existing System
job geometry checks still cover filters, scaling, dark mode and horizontal scroll.

No live job approvals or settings were changed. Review and save remains an owner
action. Provider defaults and runtime are unchanged; their release review is
recorded with publication evidence.
