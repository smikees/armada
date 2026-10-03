# Armada architecture and code review — 2026-09-26

**Verdict:** retain the local modular architecture, but address the security, data integrity and
execution-lifecycle findings below before an invited beta. The present implementation does not yet
meet its own guarantees about exclusive writes, capability enforcement or completed runs.

Reviewed the **working tree**, including the uncommitted Codex integration, on `main` at base
commit `4e834fd` (package version `0.99.73`). These findings describe that source state, not a
separately verified installed release. No production code or live realm was changed for this review.

## Scope and evidence

Traced the HTTP → runner → engine → thread/report paths; scheduler ownership and system jobs;
memory protection; capability grants; realm switching; content origins; UI module boundaries;
schema migration; release verification and test infrastructure. Read the existing architecture,
engine-seam audit, threat model and launch plan to avoid relisting fixes already delivered.
This was a source review with targeted execution, not an exhaustive review of every line, a
penetration test, a dependency vulnerability scan or the outstanding clean-machine release test.

- Full Windows/Python 3.12 suite: **1,991 passed, 3 failed, 1 skipped**, in 94.29 seconds.
- Failures: `test_page_matches_golden[memory]`, `test_page_matches_golden[agent_threads]`,
  `test_one_broken_job_does_not_stop_the_others`. Details under R11.
- Temporary, isolated probes reproduced R1–R9 below. They used scratch realm files, controlled
  interleavings and fake engines/our own short Python child processes. No model calls, credentials,
  live agents, Telegram messages or remote services were needed for those probes.
- The scheduler probe synchronizes two contenders at the actual read-before-write seam and gives
  them distinct owner identities. It demonstrates the race deterministically; it is not a claim
  that two independent Windows scheduler processes were exercised end to end.
- HTTP probes exercised the real handler dispatch with captured responses. SVG script execution
  in a browser was not attempted; the confirmed facts are the executable MIME type, app origin,
  unmodified SVG body and absence of isolation headers/redirect.

To repeat the suite from the repository root:

```powershell
$env:PYTHONPYCACHEPREFIX='D:\Work\.cache\armada-pycache'
.venv-codex\Scripts\python.exe -m pytest -o addopts='' -q --basetemp=.test-tmp-architecture-review-next
```

Source locations below are repository-relative, with line numbers from the reviewed working tree.
**P1** means a security, data-loss or execution-integrity defect to fix before beta; **P2** means
a functional or engineering gap with the delivery gate stated explicitly. No P0 was established.

## Architecture assessment

The core choices fit the product: a local Python application, portable human-readable realms,
server-rendered HTML with small JavaScript modules, a scheduler independent of the window, and
CLI adapters that leave authentication with the providers. A distributed service architecture,
frontend framework replacement or wholesale database migration is not justified by this review.

| Boundary | Current shape | Assessment |
|---|---|---|
| Entry points | HTTP route mixins, CLI, Telegram and scheduler call domain/runner functions | Useful separation, but HTTP handlers still own process cancellation and mutable realm identity |
| Execution | `runner.py` assembles context, enforces grants, calls engines, persists turns, captures artifacts and notifies | Too many lifecycle responsibilities; paths differ in failure/cleanup behavior |
| Persistence | JSON/Markdown/JSONL, helper locks and atomic replacement | Portability is valuable; atomic replacement is being mistaken for transaction safety |
| Providers | `engine/base.py`, Claude/Codex/mock adapters and model selection | A real seam exists, but streaming/capabilities are not an explicit common contract |
| Presentation | `webui/` layers, separate static assets and golden pages | Keep the renderer; replace copied namespaces and private renderer calls incrementally |
| Trust | Local-host/origin guards, separate content server, sealed reviews and signed updates | Good foundations; R1/R2 leave gaps in the actual enforcement |

Several prior investments are substantive: `write_text_atomic` flushes and replaces files;
thread progress is checkpointed before SSE delivery; Codex drains stderr and uses a monotonic
deadline; untrusted section/attachment content has a separate origin; updates verify signed
manifests and archive hashes. These should be preserved. The problem is inconsistent guarantees
across callers and failure paths, not an absence of structure.

## Findings

### R1 · P1 · File serving can escape the static directory and bypass content isolation

**Remediation verified 2026-09-27 (source):** launch 2.11 now resolves static paths under the
asset root and rejects Windows/encoded escape forms. Every user-image route sends a script-free
sandbox CSP and `nosniff`. HTTP regressions pass; direct browser SVG documents stayed visible
and made zero test-endpoint calls (ordinary control page: one). Full suite: 2,022 passed,
2 skipped. Symlink creation is unavailable on this Windows test host. Original finding follows
for audit history; installed-release verification remains a separate gate.

**Locations:** `armada/serve.py:206–213,372–380`; `armada/routes/realm.py:81–89`;
`armada/routes/_shared.py:196–208`. **Launch ticket: 2.11.**

`_static` removes literal `..` but then joins an unchecked path to the asset directory. On Windows,
`/static/D:/.../file` produces a drive-qualified `Path` that replaces the intended base. A scratch
file outside `webui/static` was returned with HTTP 200 through `do_GET`, including with
`Sec-Fetch-Site: cross-site` because `/static/` is exempt from that guard. This exposes files the
server account can read through an endpoint intended only for bundled assets. Same-origin policy
still restricts an unrelated page reading arbitrary response bodies; this is not evidence of
automatic remote exfiltration. Serving an external HTML/SVG/JS file as an app-origin asset also
undermines the separate-content-origin design.

Independently, uploaded/adopted realm SVG icons are returned directly from `/realm-icon` as
`image/svg+xml`. `_untrusted` does not classify that route, so there is no content redirect or
sandbox CSP. SVG in an `<img>` does not execute scripts, but opening it as a document changes that
boundary. The image-upload helper accepts raw SVG without sanitizing it. A probe confirmed a
script-bearing fixture was returned unchanged on the app origin without isolation.

**Required:** a canonical, resolved containment check for bundled assets; reject absolute,
drive-relative, UNC and escaping paths; apply the active-content policy to every user-controlled
image/document route. Use raster conversion, robust SVG sanitization or the existing isolated
origin. Add response-level tests for both ordinary assets and adversarial Windows paths, plus a
browser test that an SVG document cannot reach a harmless test-only app endpoint.

### R2 · P1 · Capability lookup errors relax the agent's permissions

**Remediation 2026-09-27 (source):** launch 2.12 removes the permissive fallback, strictly
validates realm/agent permission data before execution and refreshes grants at launch. Both
adapters reject invalid provider inventories and deny ungranted configured MCP servers.
Failures are recorded in chat/job/inbox threads and run reports. The installed Claude CLI
honored empty-grant server settings (three configured, zero remaining), without a model turn.
Original finding follows for audit history; see the launch table for final suite verification.

**Locations:** `armada/runner.py:282–305`; `armada/capabilities.py:119–129,253–270`;
`armada/engine/claude.py:377–380`. **Launch ticket: 2.12.**

`_disallowed_tools` catches a grant-resolution error and falls back to denying only capabilities
disabled for the whole realm. An enabled capability that this agent was never granted is then
omitted from the denial list. Claude tool turns load the regular harness with permissions skipped,
so this failure path broadens access. A real malformed grant entry (`connectors: [7]`) with an
enabled realm connector reproduced an empty denial list; no injected lookup exception was needed.

Codex's additional allowed-server inventory provides a stronger separate check; do not generalize
this finding to claim both adapters bypass that check identically. The common contract must still
be fail-closed: invalid/unreadable policy means no tool run, with a clear configuration error.
Also validate effective provider inventories so servers absent from the realm catalogue are not
implicitly allowed by a catalogue-only deny list. Contract tests must cover missing, malformed,
revoked and newly discovered capabilities for both providers.

### R3 · P1 · The shared file lock stops excluding writers after its timeout

**Location:** `armada/util.py:155–186`. **Launch ticket: 2.13.**

On lock timeout or an OS error, `file_lock` still yields into the critical section. Atomic
replacement prevents a half-written JSON file, but cannot prevent one valid update replacing
another. Two callers incrementing a scratch counter under this helper both entered the protected
section; the result was **1 instead of 2**. The probe shortened the configurable timeout; the
same branch is reached after the default five seconds. An orphaned lock has no owner metadata
and causes later callers to repeat this wait-then-proceed behavior.

**Required:** bounded acquisition with an explicit busy/error result, never unlocked execution;
an ownership-safe crash recovery strategy; and one repository mutation helper that performs
read/validate/change/atomic-write inside the acquired lock. Audit all writers to each shared file,
not just `realm.json`. For example, `sysjobs.set_enabled` and `run_one` both rewrite
`system_jobs.json` through an unlocked read/modify/save sequence (`sysjobs.py:360–370,492–506`).
Acceptance must exercise independent processes, contention, owner death and access errors.

**R3 remediation 2026-09-27 (source):** `file_lock` now uses bounded OS ownership and refuses
unlocked execution. `mutate_json` provides strict read/validate/mutate/atomic-write; shared writer
paths and schema guards are repaired. Independent-process increments, contention, killed-owner
recovery, invalid state and future-schema HTTP behavior are covered. See
[`PERSISTENCE.md`](PERSISTENCE.md) for protocol upgrades, recovery and the boundary with R4–R6;
the launch table records final suite verification.

### R4 · P1 · Scheduler ownership is a non-atomic check followed by a write

**Location:** `armada/scheduler.py:166–194`. **Launch ticket: 2.14.**

`_lock_acquire` reads the current owner, then atomically replaces the owner file. Two starters can
both observe no owner and both return `True`; an atomic *write* is not an atomic *claim*. The
controlled two-contender probe returned **`[True, True]`**. Same-process reacquisition also permits
two concurrent callers unless another mechanism serializes them. Write errors explicitly return
success. The existing tests mostly assert sequential states, so they do not cover this window.

Two schedulers can consequently begin a due job before either records completion, duplicating
quota use and the job's external side effects. **Required:** an exclusive per-realm lease/OS lock
with a unique ownership token, conservative stale-owner handling, and durable job-attempt claims.
Define retry semantics after a crash; a completion ledger cannot promise exactly-once external
effects. Verify simultaneous startup and crash/recovery with independent processes.

**Remediation verified 2026-09-27 (2.14):** `scheduler_state` now holds the kernel lease for a
daemon/pass, with unique owner tokens and a non-reentrant per-lease pass gate. PID metadata is
diagnostic; stale cleanup cannot remove the stable OS lock or release a newer incarnation.
Daily agent/command attempts are persisted before runner dispatch. System-job execution locks
and claims also cover startup nudges and manual calls, with cadence rechecked after acquisition.
Independent synchronized processes produced one owner and one dispatch; killing an owner before
or after a simulated effect released ownership without replaying its uncertain claim. Owner,
claim and completion-write failures, corrupt state and same-process contention are covered.
Full suite: **2,204 passed, 2 skipped**, with 26 new regression cases. See
[`PERSISTENCE.md`](PERSISTENCE.md) for explicit retry behavior, upgrade requirements and the
external-side-effect boundary. Verified in source; the live processes have not been restarted.

### R5 · P1 · Memory protection can destroy another writer's legitimate changes

**Location:** `armada/runner.py:48–108`; used at `1250–1254,1397–1403,1513–1517`.
**Launch ticket: 2.15.**

At the start of a tool turn, `_guard_snapshot` copies realm memory and every other agent's memory.
At the end, `_guard_restore` restores changed bytes and deletes new files without knowing who
wrote them. While agent A is running, an owner edit, system-memory refresh or agent B's own work
is indistinguishable from an unauthorized write by A. The probe changed B's existing memory and
created a new B memory after A's snapshot: completion **reverted the edit and deleted the new file**.
Locking only the restore cannot fix attribution. The restore also writes bytes non-atomically.

**Required:** remove indiscriminate rollback. Prefer execution-time write restrictions or a staged
write/proposal boundary with explicit ownership. Where an adapter cannot enforce that restriction,
report the limitation and detected change honestly without erasing unrelated work. Preserve the
existing trusted-agent threat model; do not describe prompt instructions as a sandbox. Test A and
B concurrently, owner edits during a turn, failures and cancellation.

**Remediation verified 2026-09-27 (2.15):** the destructive helpers are removed. The runner
requests absolute Claude file-tool denials for protected roots and finalizes a non-destructive
audit in `finally` on all four execution paths. Unknown-writer changes and provider-reported
write attempts remain separate; current memory bytes are never restored or deleted by completion.
Evidence persists in an audit file and an expandable thread card even after engine errors.
Concurrent A/B, owner and system-upkeep tests preserve exact bytes and deliberate deletions
after success, failure, stop, exception and cancellation for both providers. Full suite:
**2,262 passed, 2 skipped**, followed by **177 focused checks** including the final Windows path-case
correction. Codex's current adapter has no per-memory write isolation; shell/MCP
and scan-coverage limitations are explicit in [Memory boundaries](MEMORY_BOUNDARIES.md).
Verified in source; the live processes have not been restarted.

### R6 · P1 · Compaction rewrites a stale conversation snapshot

**Location:** `armada/threads.py:179–206`. **Launch ticket: 2.16.**

`compact_if_needed` reads messages, performs an arbitrarily long model call, then takes a write
lock and replaces the log with the previously calculated retained messages. A turn appended while
the summary is being generated disappears. A fake summary engine appended a complete concurrent
turn during `run`; after compaction **neither half survived**. This occurs even with a perfect
file lock. Summary and message files are also rewritten in place as separate operations, leaving
a crash window between their updates.

**Required:** compact an identified prefix with version/hash validation and preserve the current
tail under lock; retry/abort if the prefix changed. Commit the summary/prefix boundary recoverably,
using an append-only checkpoint or a small transaction journal. Avoid holding a filesystem lock
across a model call. Include pending turns, events, concurrent append/truncate and crash recovery
in the acceptance tests. Keep raw history recoverable until the checkpoint commits.

**Remediation verified 2026-09-27 (2.16):** `thread_store.HistoryStore` now owns coherent
summary/log reads, appends and journaled rewrites. Compaction summarizes outside the lock, then
validates the original prefix, summary and revision before retaining all later appends. Explicit
and legacy exchanges stay paired; pending turns and events are preserved. Truncation and competing
compaction invalidate stale summaries with a retry conflict. A prepared before/after journal
recovers interrupted summary, log and revision replacements on the next read or write; unknown
external changes are never overwritten. Independent-process writers, competing compactors and
crash-boundary tests pass. Full suite: **2,298 passed, 2 skipped**; **152 final focused checks**
include the final Unicode JSONL correction. See [Shared state and recovery](PERSISTENCE.md) for
recovery and upgrade requirements. Verified in source; live processes have not been restarted.

### R7 · P1 · A realm switch changes the identity of an in-flight request

**Locations:** `armada/serve.py:28–33`; `armada/routes/realm.py:42–49`;
`armada/routes/agents.py:246–272`. **Launch ticket: 2.17.**

`Handler.realm` is a mutable class attribute. `/switch` changes it for every handler; the chat
route reads it again after the runner returns. A turn begun in A and completed after switching to
B marks B's thread unread and asks the title helper to operate on B. The controlled handler probe
confirmed that split. The answer itself remains bound to the realm captured by `runner.chat_stream`;
this finding does **not** claim the probe wrote the assistant answer into B. A stale page submitting
a subsequent mutation also has no explicit realm identity to distinguish its A data from B.

**Required:** immutable request/run context containing realm identity, agent, thread and run ID;
explicit realm identity on mutations/content URLs; reject stale mismatches. Capture context before
starting asynchronous work and pass it into title/notification helpers. Key cancellation and
activity by run identity, not the global current realm. Verify two realms with identical agent and
thread IDs, a mid-turn switch and a stale-page save.

**Remediation, 2026-09-27:** request admission now freezes the realm root and validates page
identity. Explicit run context carries agent/thread/run identity through completion and title
helpers; unread state and normal telemetry retain that destination. Cancellation is scoped by
realm/run, with independent activity markers and atomic release when a run ID is reused. Content
and notification links retain their source realm, including mini-site relative assets. Real HTTP
switches with overlapping identical IDs, stale writes/polls, handler reuse and browser request
binding are covered by `test_realm_context.py` and its Node harness. See
[Request and run identity](REQUEST_CONTEXT.md). Final full suite: **2,309 passed, 2 skipped**.
Source changes do not restart live processes. Process supervision and terminal-event guarantees
are addressed separately below, in R8 / ticket 2.18.

### R8 · P1 · Claude streaming can hang past its deadline or report a failed run as successful

**Location:** `armada/engine/claude.py:387–469`. **Launch ticket: 2.18.**

The deadline check occurs inside `for line in proc.stdout`. A silent child blocks that read,
preventing the check. stderr is not drained concurrently, so a full stderr pipe can also stall
the child. A local Python child that slept 0.35 seconds exceeded a 0.02-second timeout and returned
after approximately 0.41 seconds with `ok=True` and no result. A second child emitted an assistant
text event and exited with code 3: the adapter returned **`ok=True`, output `partial`, no error**,
because nonzero exit is treated as failure only when no output was collected. The runner can then
persist partial output as successful completion.

**Required:** share a tested subprocess supervisor: concurrent bounded stream draining, monotonic
deadline independent of output, explicit cancellation, process-tree cleanup and resource closure
in `finally`. Provider parsers should require a valid terminal success event and successful exit;
preserve partial text with an error/stopped status. Codex already implements several of these
mechanisms; retain them and test both adapters through the same conformance suite. Test silent
children, stderr flooding, malformed/missing terminal events, nonzero exit after text, cancellation
and callback failure. These lifecycle defects should be fixed before a broad runner decomposition.

**Remediation, 2026-09-27:** both adapters now share a bounded subprocess supervisor. A monotonic
deadline is checked independently of stdout; stdin/stdout/stderr have separate workers. Windows
turns use suspended launch plus Job Object ownership; POSIX turns use process groups. Cancellation,
parent exit and errors clean up ordinary descendants, pipes and process handles with bounded waits.
Both parsers require valid terminal success and zero exit, preserve partial text on errors, and
reject malformed JSON/UTF-8 and invalid terminal shapes. Plain chat, streaming chat and agent jobs
persist partial output with explicit error/stopped statuses. Activity-marker deletion failure has
a terminal-state fallback. The shared conformance suite includes 70 real-child and persistence
regressions; behavior and limits are in [CLI turn lifecycle](PROCESS_LIFECYCLE.md). No live process
was restarted or paid model turn invoked for this implementation. Final Windows/Python 3.12 full
suite: **2,381 passed, 2 skipped** (158.29s), including all 20 page snapshots.

### R9 · P2 · Codex agent inbox work still depends on Claude being signed in

**Location:** `armada/sysjobs.py:93–116,475–484`. **Launch ticket: 2.19; required for mixed-provider beta.**

Every `QUOTA` system job checks `auth.status()` for Claude before running. `inbox-dispatch` routes
to provider-aware agent execution, but is skipped when Claude is signed out even if the receiving
agent uses an authenticated Codex model. A fake inbox-dispatch function was never called under
that condition. The same precheck affects the Telegram fallback system job; the independent
Telegram listener is a different path and is not proven blocked by this probe.

**Required:** each task declares its provider requirements. Dispatch should check the selected
recipient's provider; Claude-specific keepalive may remain explicitly Claude-specific. Return a
consistent result (`id`, status, reason, skipped/error distinction) on every branch, including
disabled and signed-out cases. Verify Codex-only, Claude-only, both connected, and neither connected.

**Remediation, 2026-09-27:** quota cost no longer implies Claude authentication. Inbox tasks and
both Telegram paths check their selected recipient provider through a shared admission helper;
Claude keepalive declares its fixed provider explicitly. Signed-out inbox recipients retain mail
and cadence, while other recipients continue. Telegram replies with sign-in/retry guidance without
charging its run allowance. Malformed or failed auth probes fail closed. System-job results now
carry identity, status, reason, detail and distinct skip/error flags on all return paths; recorded
skips preserve that status and do not trigger failure notifications or paint a successful run.
The four connection combinations are exercised separately for inbox dispatch, Telegram fallback,
the independent listener and keepalive. The final Windows/Python 3.12 suite passed **2,425 tests
with 2 skipped** (161.60s), including all 20 page snapshots and 41 provider-upkeep regressions.
Verification also repaired a starvation race during empty-lock initialization, with a regression;
process-cleanup tests now publish descendant PIDs atomically and check the original parent handle.
No paid provider calls, live Telegram sends or app restarts were performed.
See [provider upkeep](PROVIDER_UPKEEP.md).

### R10 · P2 · Module splits have not yet produced explicit service contracts

**Remediation verified 2026-09-27 (2.20):** shared typed requests/events/results and declared
provider capabilities now drive one agent-turn coordinator across HTTP, plain chat, jobs, inbox
and Telegram. Unsupported budgets/fallback/tool policies fail explicitly; per-turn adapter copies
isolate grants. Backend thread metadata owns unread mutations. Unknown accounting stays null and
incomplete chart totals are labelled. The 68-case execution contract suite covers both providers;
full suite: **2,494 passed, 2 skipped**, including all 20 unchanged page snapshots. See
[execution contracts](EXECUTION_CONTRACTS.md) for ownership and compatibility boundaries.
Full UI namespace cleanup remains D.8. Original finding follows for audit history.

**Locations:** `armada/engine/base.py:43–65`; `armada/runner.py:151–165,1243–1248,1385–1395`;
`armada/webui/__init__.py:13–24`; `armada/webui/pages.py:16–18`.
**Launch ticket: 2.20; broader UI cleanup: D.8.**

This is structural debt, not a separate reproduced crash. `EngineAdapter` declares `run` but not
streaming, cancellation, provider capabilities or event shapes. Callers use `hasattr(run_stream)`
and mutate Codex-specific adapter attributes. The base contract even permits ignoring a hard
budget; the Codex implementation correctly rejects it. Unsupported fallback and unknown pricing
also have different semantics (Codex cost currently serializes as zero).

The UI copies entire module namespaces using `globals().update`; patching a package export does
not update the original function's bindings. Tests already document having to patch several copies
of a helper. Route code also calls private renderer functions to mutate unread state. These make
dependencies implicit and slow reliable changes.

**Required before beta:** an explicit execution request/result/event contract, declared provider
capabilities, consistent unsupported-setting validation, and one owner for turn state transitions.
Build this incrementally while fixing R2/R7/R8/R9. Keep the filesystem format and compatibility
facades. Move persistence mutations out of render helpers. A wholesale UI rewrite is unnecessary;
replacing every namespace mirror can follow beta under D.8, with import boundaries enforced as
modules are touched. Represent unknown accounting as unknown, not a factual zero.

### R11 · P2 · The test suite is not yet a reproducible release gate

**Locations:** `tests/golden_support.py:26–88,119–150`; `tests/test_golden_pages.py:24–29`;
`tests/test_sysjobs.py:99–112`; `tests/test_scheduler_lock.py:1–9`.
**Launch ticket: 2.21; required before beta.**

The current suite has three failures, so there is no clean gate for subsequent refactoring:

| Failure | Evidence / needed correction |
|---|---|
| `memory` golden | System memory is stamped with the current date (25 → 26 Sep in the diff); fixture generation occurs before the render harness freezes time |
| `agent_threads` golden | Context/token-size output drifts with generated environment context; pin those inputs before fixture construction rather than refreshing a machine-specific golden |
| System-job isolation test | An early skipped result has no `id`, but the consumer expects one; fix the result contract and isolate auth in the test |

No tracked `.github` workflow was present. Existing race tests mainly check sequential states;
some enforce use of a lock without demonstrating mutual exclusion. A large passing count does
not establish crash safety or concurrency correctness. This does not establish that no external
CI exists; none is declared in this checkout.

**Required:** a declared Windows/Python 3.12 CI gate, pinned development test dependencies,
fixture clock/home/environment/provider state established before data generation, and no live
network/provider dependence in the default suite. Add deterministic interleaving/process tests
from R1–R9. Require a clean complete run; do not adopt a permanent accepted-failure baseline or
regold nondeterministic output. Keep installer/clean-machine smoke testing as the separate 5.10 gate.

## Refactoring sequence and limits

1. **Close trust-boundary gaps:** 2.11–2.12. These are focused correctness changes.
2. **Make persistence trustworthy:** 2.13, then 2.14–2.16. A small file-repository/transaction API
   is sufficient initially; choose SQLite only if measured needs justify changing the format.
3. **Give runs stable ownership:** 2.17–2.20. Introduce an immutable run context and a coordinator
   shared by chat, scheduled jobs, inbox delivery and Telegram. Keep provider decoding in adapters.
4. **Establish the release gate:** 2.21 begins immediately and accumulates each regression above.
   Keep full UI namespace cleanup in D.8 instead of delaying concrete safety fixes behind it.

The threat model and engine-seam document need current provider-specific guarantees, especially
around memory writes, unsupported controls and authentication. Preserve explicit decisions such
as trusted local agents and accepted beta-local authentication limitations; do not silently turn
this review into a new product security model. Future-schema realms and interrupted multi-file
migrations merit a read-only/recovery policy in this persistence work; no migration-loss incident
was reproduced here. The signed updater's positive checks do not substitute for a clean-machine
install/update/rollback rehearsal.

All work is entered as open launch-plan tickets. Review completion does not mark implementation
or Mihai's launch sign-off complete.
