# ARMADA stability and performance review — 27 October 2026

Reviewed source: `6effd7f`, following the 0.99.117 release. This is an analysis, not an application change or release.

**Recommendation:** prioritize four changes: make startup independent of accumulated run history, check thread changes before rendering, decouple browser delivery from engine execution, and put real deadlines around native browser operations. These address demonstrated costs and failure modes without replacing ARMADA's architecture.

## Scope and evidence

Reviewed the desktop bootstrap and window lifecycle, HTTP serving, realm/history readers, thread synchronization and persistence, engine process supervision, scheduler dispatch, and provider status polling. This is a focused deep review of critical paths, not a claim that every feature or line was audited.

Experiments used temporary synthetic realms and the local Python 3.12 development environment. No production agent, scheduled job, connector request, notification, or owner realm was run or modified. Timings below are medians of three samples. OS caches were not flushed. They measure individual operations, **not installed-app cold-start time**. Profile timings have instrumentation overhead and are used to identify cost distribution, not as additional latency measurements.

Local reproduction material:

- *build/stability-audit.py* and `build/stability-audit-2026-10-27.json`: scaling, profile and fault-injection checks.
- *build/audit-blocked-observer.py* and `build/audit-blocked-observer-result.json`: blocked engine observer experiment.
- These are local ignored build artifacts; they are not part of a published release.

| Experiment | Result |
|---|---:|
| Read synthetic realm: 3 agents, no run records | 3.07 ms |
| Same realm: 1,000 run records per agent | 216.86 ms |
| Same realm: 10,000 run records per agent | 2,117.38 ms |
| Unchanged thread poll: 20 messages, no sibling threads | 15.32 ms |
| Unchanged thread poll: 1,000 messages, no siblings | 414.20 ms |
| Unchanged thread poll: 1,000 messages plus 20 siblings with 1,000 messages each | 732.81 ms |
| Browser bridge configured for a 20 ms timeout, with blocked `evaluate_js` | Still blocked after 150 ms |
| CLI configured for a 0.5 s timeout, with blocked event callback | Still running after callback blocked for 0.8 s; timed out after callback released |
| 32 idle loopback HTTP connections, without request headers | 32 additional handler threads |
| Malformed JSON in one synthetic agent's configuration | Whole `reader.read()` raised `JSONDecodeError` |

## 1. Remove full-history loading from startup and frequent requests

**Priority: high. Benefit: startup speed and responsiveness. Evidence: measured. Relative change size: small initial fix, medium for incremental summaries.**

`armada/serve.py` (line 902 in the reviewed revision) calls `reader.read(realm).name` before creating the HTTP server. Getting the realm's name therefore also reads every agent, job and historical run. `armada/reader.py` (line 170 in the reviewed revision) implements this aggregate read. It scans complete JSONL logs and calls `apply_annotation` for each record, including records outside the 30-day usage window.

`armada/job_history.py` (line 79 in the reviewed revision) probes an annotation file for every run. The 30,000-record profile made about 30,000 filesystem existence checks. Annotation handling accounted for roughly 85% of profiled reader time; filesystem checks dominated that work. On Windows this is expensive even when the annotation files do not exist.

The same aggregate reader is used by ordinary views and by `armada/routes/agents.py` (line 94 in the reviewed revision) to retrieve IDs for activity dots. `armada/webui/static/js/dotpoll.js` requests these every four seconds while visible. Historical data therefore slows both opening and continued use.

Implement in stages:

1. Read validated realm metadata only during startup registration. Keep schema validation and migration checks; remove historical aggregation from this prerequisite.
2. Separate agent roster/configuration reads from usage and job-history summaries. Activity polling and thread validation should not need usage totals.
3. Build an annotation lookup once per read instead of checking a path for every event. Preserve annotation semantics and handle updates during a scan coherently.
4. Maintain rebuildable incremental summaries for latest job outcome and rolling usage. JSONL remains the canonical audit record. Detect append, replacement, truncation, annotation changes and external edits; invalidate across the scheduler and desktop processes.

Do not simply skip old records: the latest known outcome of a rarely run job can be older than 30 days. Do not cache a mutable whole-realm object indefinitely.

Verification: compare summaries against a full scan after append, correction, truncation and restart; ensure startup metadata cost is independent of run count; measure installed-app launch with a populated realm.

## 2. Make an unchanged thread poll inexpensive

**Priority: high. Benefit: responsiveness, lower CPU and disk traffic, more headroom for stability. Evidence: measured. Relative change size: medium.**

`armada/thread_windows.py` (line 42 in the reviewed revision) renders the entire conversation, rewrites its HTML for the realm context, calculates metrics and hashes the result **before** comparing the client's revision. This avoids sending unchanged HTML, but does not avoid constructing it.

Thread selection also loads the whole realm. `_ordered_threads` (`armada/webui/threadsview.py` (line 142 in the reviewed revision)) loads sibling histories to identify job-only threads. Preview generation then reads sibling histories again. A single profiled unchanged request made 64 snapshots and approximately 64,000 JSON decodes in the largest synthetic case.

`thread_sync.js` already prevents overlapping requests within one view and schedules the next poll after completion, with 750 ms active / 1,500 ms idle delays. The issue is expensive work per request, multiplied by main and detached views, not a missing guard in that controller.

Recommended design:

- Compute a cheap, coherent change token before rendering. Include transcript, summary, progress, title/archive metadata, active-run/cancellation state and voice state.
- Cache rendered output, metrics and previews by their actual dependencies. Separate sibling preview revisions from the selected conversation revision.
- Reuse one coherent history snapshot within a request.
- Consider one lightweight change feed for a view, with targeted fetches when something changes. Retain a cheap reconciliation fallback for lost events and external file changes.

Important implementation detail: `HistoryStore.append` does not update the transaction revision file. Using that revision alone would miss appended messages. Introduce a reliable generation mechanism or validated file fingerprints; do not trade speed for stale conversations.

Preserve synchronization while windows are occluded. Stopping all background polling would reintroduce the user's detached-window consistency problem.

Verification: no full transcript rendering on an unchanged poll; both views converge after append, edit, stop, voice transcript replacement and compaction; changed sibling previews update independently; test multiple windows with long histories.

## 3. Decouple engine execution from browser stream writes

**Priority: high. Benefit: reliable cancellation, deadlines and completion persistence. Evidence: call-chain inspection plus reproduced blocked-callback behavior. Relative change size: medium.**

`armada/routes/agents.py` (line 242 in the reviewed revision) passes an event callback to `chat_stream` that writes and flushes directly to the HTTP socket. `armada/execution.py` (line 266 in the reviewed revision) invokes that observer synchronously, within the live-text event ordering lock. `armada/engine/process.py` calls provider output handlers in the same loop that checks cancellation and deadlines.

An ordinary disconnect raises an exception, which is caught. A slow client that stops consuming data can instead block a socket write. Exception handling does not bound that wait. This can delay the next cancellation/deadline check and terminal persistence.

The controlled experiment used a local Python child and a deliberately blocked observer. Its 0.5-second timeout was not handled during a 0.8-second callback blockage; it was handled once the observer returned. This proves the supervisor's dependence on prompt callbacks. It does not claim an actual user's socket was blocked during the reported incident.

Recommended fix:

- Execution owns durable state and completion independently of the browser connection.
- Publish UI events into a bounded observer queue. Coalesce replaceable progress/render events under pressure; do not drop durable transcript or terminal state.
- Have a separate delivery worker with bounded socket writes. A failed or slow observer detaches; it does not stop an otherwise valid run.
- Reconnected views recover from the authoritative thread state. Keep process-tree ownership and cancellation semantics unchanged.

Verification: client disconnect, connected-but-not-reading client, blocked renderer and full observer queue; cancellation/deadline handling and final persistence must still complete within a defined bound. Avoid replacing synchronous blockage with an unbounded event queue.

## 4. Bound the native bridge and recover the renderer

**Priority: high. Benefit: fewer stuck startup/window operations and clearer recovery. Evidence: reproduced timeout gap; recovery gap found by inspection. Relative change size: medium to large.**

`armada/app.py` (line 75 in the reviewed revision) starts its timeout wait only after `window.evaluate_js(...)` returns. If the bridge call itself hangs, the declared timeout is ineffective. Other startup evaluations around `app.py` (line 686 in the reviewed revision) also call the bridge directly. The existing overall startup deadline is useful, but it does not make each native operation bounded or guarantee recovery if the native UI is unresponsive.

The injected bridge test demonstrated the gap: a 20 ms deadline did not return after 150 ms because evaluation had not returned.

Use an asynchronous native-operation adapter with a deadline measured from entry, a finite number of outstanding operations, and generation checks that discard late completions. A new daemon thread for every timed-out operation would merely turn a hang into accumulating leaked workers.

Add explicit handling for WebView2 process failure/unresponsiveness and a visible recovery state. Reload or recreate the presentation while retaining the existing server/coordinator and drafts. Never automatically replay agent requests, scheduled jobs or external side effects during renderer recovery.

Keep the ordered native visibility operations introduced in 0.99.117. Expand their real-desktop tests to repeated hide/show, close during initialization, renderer failure and recovery. Startup already verifies authenticated server identity and shared controller readiness; preserve those checks.

The persistent white rectangle previously observed without an owning ARMADA process is **not explained conclusively by this audit**. These code defects are actionable independently. Do not label them the proven cause of that incident or change graphics drivers based on this evidence.

## 5. Isolate malformed records instead of failing unrelated views

**Priority: medium-high. Benefit: resilience to partial/corrupt state. Evidence: reproduced. Relative change size: medium.**

One malformed `agent.json` caused the aggregate reader to fail. Individual job JSON has the same unguarded parsing pattern. This can break unrelated pages or thread requests; the activity endpoint catches the exception and returns an empty map, which conceals the distinction between no activity and unavailable state.

Read and validate records individually. Show a specific unavailable-agent/job diagnostic and preserve the original file for repair. Keep valid agents and the app's recovery/settings views accessible. Distinguish missing, unsupported and corrupt state.

Authorization must fail closed for the affected record. Do not recover by silently substituting an empty configuration, retaining stale permissions or running a partially validated job. Preserve atomic writes and transaction recovery.

Verification: malformed agent, job, realm and theme records; one broken agent must not prevent a different valid agent's page from loading; the affected job cannot run with guessed defaults.

## 6. Bound HTTP resources and coalesce status probes

**Priority: medium. Benefit: predictable resource use under slow clients or several windows. Evidence: measured for HTTP threads; inspection for probe duplication. Relative change size: small to medium.**

`armada/serve.py` (line 766 in the reviewed revision) uses a thread-per-connection server without an explicit admission bound or first-header timeout. In the isolated test, 32 idle local connections retained 32 handler threads. The service is loopback-bound and authenticated; this is a resource-management finding, not evidence of a remote compromise.

Add bounded admission and request/header deadlines, with separate treatment for long-lived streams. Reserve capacity for health, stop and recovery actions. A single small worker pool shared indiscriminately with SSE would starve normal requests.

`armada/providers.py` (line 52 in the reviewed revision) performs status probes, including Codex/Gemini version subprocesses, and `statuses()` creates a pool per request. Some inner authentication checks already cache results, and page rendering reads prior observations; the missing optimization is coalescing the complete status operation across callers.

Reuse the background refresh pattern already present in `provider_limits.py`: last-known result with age, one in-flight refresh per provider, explicit invalidation after login/install, bounded retries. Avoid rewriting unchanged provider configuration on every observation.

Verification: several windows trigger only one refresh per provider; pending login still updates promptly; idle sockets expire; streams cannot consume all stop/recovery capacity.

## 7. Separate scheduling decisions from job execution

**Priority: medium. Benefit: schedule reliability as job count grows. Evidence: code inspection, not a production lateness measurement. Relative change size: large.**

`armada/scheduler.py` (line 480 in the reviewed revision) runs each job synchronously inside `tick`. The daemon calls each realm's tick sequentially at line 666. A long-running job therefore delays later due-job evaluation, including other realms in that daemon. This is current serial behavior, not a newly demonstrated regression.

Introduce a dispatcher that evaluates due work independently of execution, with a small bounded worker budget and explicit per-agent/provider concurrency policies. Preserve durable claims, dependencies, retry rules, uncertain-outcome handling and shutdown/update admission. Do not blindly parallelize `tick`: avoiding duplicate publication is more important than throughput.

Verification: a long job cannot delay evaluation of an unrelated due job; crash/restart, lease loss and update shutdown never cause duplicate side effects. Ship this separately from the lower-risk reader optimizations.

## Startup measurement and secondary opportunities

Fresh-process import medians were about 113 ms for `armada.cli`, 204 ms for `armada.app`, 321 ms for `armada.serve`, and 1,003 ms for pywebview's Edge backend. These are separate overlapping import experiments, not additive startup phases. They suggest native initialization deserves measurement after removing avoidable history work; they do not justify replacing Python or the desktop stack.

Add structured local timing milestones: launcher entry, instance check, native import, server bind, document navigation, first painted content, authenticated controller ready, scheduler ready and update health acknowledgement. Record durations and outcome, without prompt contents or credentials. Report warm/cold and populated/empty realm results separately.

Useful follow-on work:

- `HistoryStore.append` validates the full existing log on every append (`armada/thread_store.py` (line 126 in the reviewed revision)). Maintain a validated generation/index to avoid repeated parsing as transcripts grow, while retaining corruption detection and `fsync` durability. Benchmark append latency before choosing a design.
- Profile frontend rendering, font initialization and optional assets on the installed build. No browser trace was collected here, so frontend changes are not assigned promised savings.
- Add a long-running desktop soak scenario: main plus detached views, bounded synthetic streams, repeated hide/show, render failure, reconnect and shutdown. Track CPU, memory, thread/handle counts and responsiveness over time.

## Recommended delivery order

1. **First stability/performance release:** lightweight startup/roster reads, batched annotation lookup, observer isolation, effective bridge deadlines, and timing instrumentation. Gate on data correctness and native lifecycle tests.
2. **Next performance release:** early thread revision checks, coherent snapshot/render/preview caches, bounded HTTP resources, provider refresh coalescing and malformed-record isolation.
3. **Separate scheduler improvement:** bounded concurrent dispatch with crash/restart and duplicate-delivery tests. Follow with renderer recovery and a sustained desktop soak gate if these need more native integration work than the first release can safely accommodate.

Suggested performance targets to validate on the same machine: warm unchanged thread-state responses below 50 ms at the tested scale, no history-dependent startup registration work, and no observer-induced violation of cancellation/deadline handling. These are proposed acceptance targets, not achieved results. End-to-end launch targets should be set after measuring the signed-update/installed-app path.

Keep the existing strengths: canonical thread state across views, journaled history updates, process-tree cleanup, durable scheduler claims, local HTTP authentication, isolated content serving, signed updates, rollback/quarantine and native release checks. The most valuable work is removing expensive work from frequent paths and making blocking dependencies bounded—not a wholesale rewrite.
