# Shared state and recovery

Launch ticket 2.13 replaces the former wait-then-write lock with a bounded OS lock.
Use `util.mutate_json(path, mutate, default=..., validate=...)` for a JSON read/modify/write.
It holds one exclusive lock across the strict read, validation, mutation and atomic replacement.
Only a missing file may use the explicit default factory. Duplicate keys, invalid JSON,
unexpected shapes and unsupported schema versions are errors; a tolerant UI reader must never
be used as mutation input.

`write_json_atomic` by itself prevents torn files. It does not serialize a read/modify/write;
callers must use `mutate_json` or hold `file_lock` across the complete operation. The common
realm, agent, thread-index and system-job files have additional overwrite protection in the
atomic writer. Those checks do not make an earlier unlocked read safe.

## Lock ownership

Each target has a persistent hidden sibling, `.<filename>.lock`. Windows uses a kernel byte-range
lock; POSIX uses `flock`. The file descriptor is not inherited by child processes. Different
threads and different processes contend on the same file. The timeout uses a monotonic clock;
timeout, access denial and other I/O failures never enter the caller's critical section.

Closing the descriptor, including process termination, releases ownership. The lock file stays
in place: unlinking it would allow two processes to lock different files with the same name.
There is no PID-based stale-owner takeover. Creating the small format marker is also protected;
an interrupted initialization is refused unless another live initializer completes it within
the bounded wait.
While the marker is empty, waiters observe its size without repeatedly taking the OS lock,
leaving the initializer able to publish it. Once published, its contents are validated under
the exclusive lock. This avoids starvation between simultaneous short-timeout startup checks;
it does not permit stealing an interrupted or legacy lock.

Upgrade the UI and scheduler together, with their existing runs stopped. Old versions used
unmarked `<filename>.lock` files and do not participate in this protocol. Their lock files are
refused. After all writers have stopped, an operator may remove an abandoned legacy lock or an
empty/incomplete new lock file, then restart the updated processes. Do not delete a valid new
lock file to resolve contention; wait for or stop its owner instead. Normal process crashes
require no lock-file cleanup.

## State versions and recovery

The supported realm format comes from `realmformat.CURRENT`. Unstamped legacy data and the
documented `"0.1"` stamp remain supported. Invalid version stamps are preserved and reported.
Migration reads strictly and does not replace corrupt configuration with an empty realm.

A realm with a newer schema can be inspected where the existing readers understand its layout.
Mutating HTTP requests return a readable 409 response, scheduler passes are held, and agent
execution is refused before provider selection. Export, preflight and app update/restart remain
available. Shared file writers also check the realm version. A failed capability admission can
still record an error transcript when the realm policy is malformed or unreadable; this never
repairs or overwrites that policy. A known newer realm schema remains read-only.

For damaged JSON, preserve a copy and restore a known-valid backup using a compatible app version
while writers are stopped. Armada does not guess missing fields and save those guesses over the
damaged source. HTTP lock contention returns 423; state/format failures return 409. Some legacy
route methods return the same explanation in their existing `ok: false` response envelope.

## Audited writers

- Realm settings, capability catalogue edits, section edits and workspace changes already hold
  the realm-file lock; they now get exclusive ownership and strict overwrite checks.
- Agent settings and capability grants use the same agent-file lock and strict reads.
  Retirement/reinstatement stamps merge under that lock; directory moves use a rename rather
  than a copy/delete fallback. This does not cancel or redirect an existing agent run.
- Thread metadata actions read strictly under their lock. View/unread updates use `mutate_json`;
  an optional display-state write failure is logged without preventing read-only inspection.
- System-job switches and completion records merge under the same lock. Completion re-reads
  current state, preserving switches and other job results changed during the job's execution.
- Job create, edit, enable and delete routes serialize on the job file; format migrations use
  the same lock when rewriting command jobs.

Launch 2.15 removes memory rollback entirely; [Memory boundaries](MEMORY_BOUNDARIES.md) describes
the provider restrictions and non-destructive audit. Launch 2.16 adds the recoverable thread
transaction below; atomic replacement of one file alone cannot keep a summary and log coherent.

## Thread history and compaction (2.16)

`thread_store.HistoryStore` serializes all thread appends, truncation, compaction commits and
coherent reads using the existing `messages.jsonl` lock. `Thread.snapshot()` returns one
summary/log generation; model context and transcript rendering use it. Read-only inspection of
a newer realm remains available if no pending transaction needs recovery.

Compaction takes a snapshot under the lock, releases it for the model call, then validates the
unchanged summary, opaque revision and complete original log prefix under the lock. Append-only
growth is retained verbatim as text after the compacted snapshot. Any rewrite, truncation or
competing compaction raises `CompactionConflict` with an explicit retry message; no stale result
is applied. Truncation advances the revision even if another writer later recreates identical
messages, preventing an ABA race. It keeps the previous summary, matching the existing restart
behavior. A no-op truncation does not change the revision.

Only a completed conversational prefix is eligible. Explicit turn IDs pair overlapping requests;
legacy exchanges pair adjacent user/assistant records. The cutoff moves back to retain both
halves of any exchange it would split. An unmatched record prevents compaction from crossing it.
Events, pending turns and their progress files stay live, including a pending question followed
by completed background work. Existing summary text is folded into the model's replacement
summary once, rather than prepended again afterwards.

Compaction and truncation use a small write-ahead transaction:

1. Under the messages lock, atomically write and flush `.history-transaction.json` (schema 1).
   It contains complete before/after log, summary and revision text, the operation and a checksum.
   This prepared journal is the commit decision; the original raw records remain recoverable.
2. Atomically replace `summary.md`, `messages.jsonl` and `.history-revision`, flushing each file.
3. Remove the journal only after every replacement succeeds. Old raw records summarized out of
   the live log are no longer retained once the transaction completes.

Every participating read or mutation first rolls a prepared transaction forward under the same
lock. Each current file must match either its journaled before or after value; all three are
validated before any replacement. An interrupted recovery is safe to repeat. Read operations
wait for a writer rather than returning a new summary with the old log. Recovery uses no model
call and works in a new process. Existing thread folders need no migration; the revision and
journal are created on the first rewrite. Text comparisons normalize line endings consistently
across Windows and other hosts.

If journal preparation fails, no history file changes. If replacement or cleanup fails after
preparation, the call reports the failure and the journal remains for the next access to finish.
Malformed/unsupported journals, checksum errors and unexpected external edits block recovery
and preserve all files. Keep the entire thread directory, including hidden control files, and
repair access or restore a known-consistent backup with all writers stopped. Do not delete a
pending journal as if it were a stale lock: it may be the only copy of the original raw prefix
while the commit is incomplete.
Malformed log entries remain visible where readable but block mutation; compaction never
silently drops an invalid line.

Upgrade the UI and scheduler together; older writers do not participate in this transaction
protocol. The guarantee covers process interruption on filesystems supporting atomic replacement
and flush, not arbitrary storage loss, external writers that ignore the lock, or a live export
copied across different generations. Stop writers before taking a consistent folder backup.

## Scheduler ownership and attempts (2.14)

`scheduler_state.acquire` holds the OS lock on `.scheduler.lock.json.lock` for the entire
daemon lifetime or standalone pass. `scheduler.lock.json` is diagnostic metadata with a unique
owner token, PID and start time. Only the handle that owns the token can remove its metadata,
while still holding the OS lock. The stable hidden lock file is never removed. A daemon passes
its lease into each tick; a non-reentrant gate also excludes overlapping calls using that lease.
PID liveness cannot override the modern OS lock, and stale metadata with a reused PID cannot
block recovery. A known-live legacy PID-only scheduler is refused; stop old writers on upgrade.
Owner-write failure holds all dispatch and releases the kernel lock.

Agent/command jobs keep one durable automatic admission per `(agent, job, realm-local scheduled day)` in
`.scheduler/attempts/YYYY-MM-DD.json`, preserving the existing once-per-day behavior, including
cron schedules with multiple matching minutes. The day is taken from the matched fire time,
including grace-period catch-up after midnight. The scheduler still honors earlier run reports
at or after that day's first fire time; a previous night's catch-up cannot suppress tonight's run.
Each admission has an attempt ID, owner token and `claimed` state written and flushed before the
runner is called. A terminal result changes it to `finished` with the result status. Failure
also consumes that day's automatic attempt. No age-based cleanup deletes this evidence.

If the process dies after admission, the next owner gets the kernel lock but does not replay
the uncertain claim. This includes a crash just before dispatch: the job may have done nothing,
or may have finished its external work. A completion-write failure also leaves the claim held.
The scheduler and dry-run results explain the hold and normal later-day schedules remain eligible.

System jobs use `.scheduler/system/` execution locks, shared by the scheduler, app-startup
nudges and manual requests. `system_jobs.json` stores their attempt IDs and states. Enabled,
due and admission checks happen under the state lock; execution happens outside that state lock;
completion merges under it, preserving concurrent switch edits. Scheduled calls recheck cadence
after obtaining the execution lock. An unfinished attempt holds automatic retries indefinitely;
the System jobs list shows the explanation. Completed errors retry on the normal interval.

For an interrupted job, inspect its run report, provider process and external destination before
using **Run now**. Agent/command Run now is an explicitly requested additional run; it does not
erase the daily claim and is outside automatic scheduling admission. System-job Run now cannot
overlap a current execution; after a crash it creates a new attempt, retains the interrupted
record in bounded history and records `retry_of`. Disabling/re-enabling a job does not erase claims.
Provider children can outlive a killed parent; process-tree supervision is tracked in 2.18.

These are exclusive admission and conservative replay semantics, **not exactly-once external
effects**. The claim and a remote write cannot be one atomic transaction. A provider may retry
internally, and an operator retry or restoration of stale state can duplicate effects. Jobs with
such effects should use destination-side idempotency keys or reconciliation. Preserve attempts
with realm backups; do not delete them as caches. On malformed or unsupported attempt state,
dispatch is held and the original bytes are preserved for recovery with all writers stopped.

## Verification

`tests/test_exclusive_state.py` starts four independent processes behind a barrier and verifies
all 120 increments. It also covers contention without unlocked entry, a killed lock owner,
thread contention, access errors, legacy/interrupted lock files, invalid/future state preservation,
system-job switch changes during execution and HTTP read-only behavior for a newer realm.

`tests/test_scheduler_claims.py` synchronizes two independent scheduler processes and two system
job processes, kills an owner before/after a simulated external effect, and checks same-process
overlap, stale ownership, state/write failures, cadence and explicit retry behavior. Provider work
is stubbed; no model quota or live realm is used.

`tests/test_thread_compaction.py` exercises an independent writer during the model call, two
synchronized competing compactors, a reader during partial commit, and real child-process exits
after preparation, each replacement and cleanup. It also covers interleaved/pending turns,
events, truncation including ABA, malformed history/journals, write failures, external edits,
recovery before reads/writes and the truncation route. All providers are replaced with local
summary stubs; the tests spend no model quota.
