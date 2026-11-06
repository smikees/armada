# Bounded execution and scheduler dispatch (M8)

Status: implemented and locally validated in candidate 0.99.130; release gates and
maintainer acceptance pending.

## Decision and limits

The scheduler daemon discovers due work without executing it on its discovery thread.
It reserves a bounded ticket, persists the existing daily attempt claim, then queues a
callback. Only tickets granted capacity receive a worker. `schedule --once` retains its
synchronous result contract. Automatic attempts with uncertain outcomes are never replayed.

Desktop, scheduler and CLI execution share account-wide admission, independent of the
selected realm and install path. The initial conservative limits are four executions,
two per provider (Claude, Codex and Gemini equally), two per realm, and one per
conversation. Commands use a separate resource name with the same limit of two.
There are at most 128 tickets and 32 per realm, including running work. These are
application constants, not editable permissive policy. Queue saturation is explicit.

Eligible realms take turns; within a conversation requests retain FIFO order. A saturated
provider or busy conversation does not prevent a different eligible resource from starting.
Capacity is non-preemptive: a slow run retains its slot until it stops. Maintenance wrappers
have one separate slot because they can synchronously await a model child; holding all
model capacity in wrappers would deadlock. Their model children use normal limits.

## Ownership and failure

A bounded atomic account ledger records immutable destinations, resource, cancellation,
queue order and an incarnation token. Each live ticket holds a kernel lock on one of 128
stable slot files. A PID is diagnostic only. A crash releases its kernel ownership and a
later bounded sweep frees capacity. The separate scheduler/system-job attempt ledger
retains the uncertain result. No timeout steals a live ticket, and no queue record is an
instruction to replay work on startup. Corrupt or future-version admission state holds work.

Permissions and provider selection are checked again after queueing. Tickets grant capacity,
not access. A queued provider change is refused rather than charging the wrong resource.
Nested work in the same conversation shares its slot; maintenance children get their own.
Remote Stop records a cancellation request for the immutable realm/thread or run. The owning
process monitors it and invokes its existing process-tree cancellation handle. A queued
scheduled cancellation finishes its daily attempt as stopped without invoking the engine.
Stopping a restored backoff also cancels its retry journal. A stopped daily claim cannot
restore a backoff even if withdrawing that journal failed; repair is then explicit.

Queued chat input and attachments are persisted before waiting, with visible progress.
Pending queued requests are excluded from another turn's model context and never replayed
automatically. Conversation capacity is acquired before a job invocation lock, preventing
a manual request from blocking the admitted scheduler worker it is waiting behind.

Update checks include tickets. Scheduler shutdown cancels queued work and requests running
cancellation before draining workers and releasing realm leases. Archive/removal reconciliation
withdraws queued work and retains a realm lease until its running worker records its result.
Job retry backoff retains its invocation slot (at most 120 seconds per wait) and checks Stop
between bounded wait slices. This avoids unbounded parked retry workers; releasing/reacquiring
capacity for backoff would need a separate continuation design. Voice backlog is bounded
(32 messages across at most four conversation workers), and its
cleanup no longer returns from a `finally` block.

## Alternatives and tradeoffs

- A thread per realm would leave execution unbounded and would not share desktop limits.
- A normal thread-pool queue would be unbounded unless separately guarded, and blocked
  provider admission could occupy every worker. Ticket promotion precedes worker creation.
- PID files or expiring leases would allow PID reuse or a paused process to overlap another
  owner. Kernel ownership is released only on close or process death.
- A database/service broker would provide more scheduling facilities but add another
  component to install and recover. The bounded ledger fits the existing atomic-file model.

This is cooperative application admission, not an OS security sandbox against another
program running as the owner. Killing a process cannot undo external side effects. A
maintenance callback without a model cancellation handle still relies on its own bounded
I/O timeout while shutdown drains. Work from older builds must be stopped during upgrade;
older binaries do not implement these shared limits.

## Validation

Initial concurrency gate: **58 tests passed**, including real-process ownership recovery
and cancellation, provider saturation, conversation FIFO, policy revalidation after waiting,
queued stop without launch/replay, uncertain outcome preservation and voice exception cleanup.
Expanded regression gate: **186 tests passed**, including durable queued chat and the
reproduced manual/scheduled invocation-lock race. A separate nine-test dispatcher gate
includes update-pause draining and a **64-task/eight-realm** stress run with no capacity
violations or dropped/duplicate callbacks. A **220-test** corrective batch covers policy
guards before adapter construction, one adapter setup for immediate work, revalidation
after waiting, and locked large-report appends.
A **101-test** retry/ownership batch additionally verifies that cancelling a restored retry
cannot resurrect its old backoff, including a journal-write failure, while a normally cancelled
retry leaves tomorrow's independent job eligible.

The final pinned full suite passed **4,197 tests**, with six skips, in 672.95s. Native
shared-window confirmation passed **79 checks**. Exact-source Windows CI and required
publisher/package/upgrade gates remain pending. Generated references and both changed
goldens (release notes and queueing help only) have been reviewed.
