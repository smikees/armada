# 0.99.130 — Fair, bounded execution across realms

M8 release candidate. Not yet published; maintainer acceptance remains pending.

The daemon discovers scheduled work separately from execution. Account-wide kernel-owned
tickets share capacity across the desktop, scheduler and command line: four executions,
two per provider, two per realm and one per conversation. Eligible realms take turns;
the queue is bounded. Maintenance wrappers have one separate slot and their model children
use normal capacity. Policy is revalidated after waiting. Stop reaches the owning process.

Queued chat messages and attachments are saved before waiting. Later queued input cannot
leak into the active turn's context. Job invocation locks are taken after capacity so a
manual request cannot block the scheduled job it is queued behind. Large shared run-report
appends hold an OS lock through flush. Voice backlog is bounded and its cleanup no longer
suppresses exceptions. See [the admission contract](EXECUTION_ADMISSION.md).

## Candidate validation

- Initial final-source pinned gate: **4,197 passed, six skipped in 672.95s** on Python
  3.14.10. Exit status zero. The later Windows snapshot correction below requires a new gate.

- Initial concurrency gate: 58 passed. Expanded regression: 186 passed.
- Dispatcher gate: nine passed, including 64 tasks across eight synthetic realms, with
  no dropped/duplicate callback or total/provider/realm capacity violation.
- Real process tests cover shared ownership, capacity recovery after process death and
  remote cancellation. Durable uncertain attempts are held rather than replayed.
- A broad run was stopped to fix a separately reproduced manual/scheduled lock conflict.
  The next completed gate had 4,155 passes, six skips and 37 failures in 672.68s. All failures
  traced to early adapter creation or redundant preparation; the corrected 220-test batch
  passed in 30.55s. The final complete gate above includes these corrections.
- Hidden native shared-window probe: 79 passed, repeated after durable queue changes.
  Final native confirmation after the admission-order correction also passed all 79.
- A further diagnostic gate passed the earlier failures, then was stopped around 78%
  to fix a restored-retry cancellation edge case. Cancelling queued work now withdraws
  its backoff; a stopped claim cannot restore that backoff even if the journal write
  fails. The 101-test retry/ownership batch passed in 18.11s, including tomorrow's job
  remaining eligible after a normal cancellation. The final complete gate above passed.
- References regenerated. Changed goldens are limited to release notes and queueing help.
- Candidate `3171fa4` was pushed with the owner's explicit 0.99.130 release approval.
  Its mandatory publisher repeat stopped with 4,196 passes, six skips and one failure
  in 673.89s: the cross-realm test double counted repeated Stop requests as separate
  cancellations. The production cancellation handle is idempotent. The test now uses
  that handle and deliberately repeats Stop while cleanup is paused, preserving all
  realm-isolation assertions. The 94-test cancellation/contract batch passed in 20.79s.
  Application source is unchanged; the corrected test and evidence require a new exact-source
  CI/publisher run. No artifact was published by the failed run.
- At `f2e43ba`, the publisher passed **4,197 tests / six skips in 670.42s** and the pinned
  Windows CI job passed **4,199 / four skips**. The second Windows job found a real race:
  a watcher opening the ledger during replacement received a transient access error and
  cancelled healthy work. Snapshot reads now share the writer's kernel lock. The forced
  overlap regression fails with the old reader and passes with the fix; the related
  **106-test batch passed in 29.16s**. Persistent invalid/unreadable state still fails closed.
  A superseded CI run also exposed a four-second test-only drain deadline on a slow disk;
  the deadline is now 15 seconds, with progress/capacity/uniqueness assertions unchanged.
  Publication stopped at CI without creating assets. Native shared-window confirmation after
  this fix passed all **79 checks**. Full exact-source gates restart after this fix.

Release-owned defaults were reviewed against official [Claude model documentation](https://platform.claude.com/docs/en/models/overview),
[OpenAI model documentation](https://developers.openai.com/codex/models), and
[Antigravity model documentation](https://antigravity.google/docs/models/) on 6 November 2026.
The existing preferences remain runtime-catalogue gated, with provider-default fallback;
no account's availability is inferred from the UI seed catalogue or these public pages.

## Remaining release gates and limits

Exact-source Windows CI, mandatory publisher repeat, packaged native checks, signed
.129→.130 upgrade and public/website verification remain pending.
No owner app restart or live realm/provider testing was performed.

This is cooperative application admission, not a security boundary against other programs
running as the owner. Existing binaries do not implement the limits. Job retry backoff retains
its slot, checks Stop between bounded waits, and is at most 120 seconds per wait. Maintenance
I/O without a process cancellation handle relies on its own timeout during shutdown.
Crashes can leave external effects uncertain; capacity recovery never authorizes replay.

Python 3.14.10, launcher protocol 2 and the existing Windows distribution remain unchanged.
Publisher signing and clean-machine WebView2 acceptance limitations remain open. Update
assets still require Ed25519 signing and all required release gates. The owner explicitly
approved gated 0.99.130 publication using the existing unsigned beta distribution; publication
remains pending.
