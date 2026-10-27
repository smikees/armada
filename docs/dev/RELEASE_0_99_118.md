# 0.99.118 — Startup and conversation performance

This implements the first delivery from the [stability/performance review](STABILITY_PERFORMANCE_REVIEW_2026_10_27.md).

## Changes

- Native realm metadata and lightweight roster reads keep history, jobs and skills out of startup registration, activity-dot polling and thread target validation. Detached-window headers use the same metadata path. Full overview/accounting reads retain their existing semantics.
- History scans list annotations once per agent rather than probing a missing annotation file for every historical run. Corrections added between scans are observed on the next scan; the original audit log stays immutable.
- Bounded presentation caches reuse transcript HTML/metrics and sidebar preview/classification results. Fingerprints include append/replacement metadata, summaries, transaction revisions, progress files and legacy job logs. Render keys also include live marker/PID state, voice state, portraits, names and model context limits. A pending history transaction bypasses caching. Changes during rendering are not cached; entries also expire after 30 seconds as a reconciliation fallback. These caches are never used for authorization or model input.
- Browser stream delivery runs independently of engine callbacks, with a 128-event/1 MiB queue, two-second socket write deadline and at most 16 delivery workers. Overload disconnects the observer; canonical transcript persistence and execution continue. A closing stream has a bounded drain, and both views can reconcile from thread state.
- Browser evaluation has a deadline covering entry, native evaluation and asynchronous completion, with at most four outstanding worker calls. Synchronous JavaScript values are explicitly wrapped in a Promise to respect pywebview's callback contract. Startup uses this path for paint confirmation, document readiness, identity proof and draft restoration.
- Startup logs record phase durations without prompt content or credentials.

## Measurements

Same synthetic three-agent fixtures and local Python 3.12 environment as the review; medians of three samples. These are operation timings, not installed-app cold-start claims.

| Operation | Before | After |
| --- | ---: | ---: |
| Read realm with 1,000 runs per agent | 216.86 ms | 12.54 ms |
| Read realm with 10,000 runs per agent | 2,117.38 ms | 102.15 ms |
| Unchanged thread, 1,000 messages | 414.20 ms | 5.88 ms |
| Unchanged thread, 1,000 messages plus 20 populated sibling threads | 732.81 ms | 35.97 ms |

The injected 20 ms browser deadline now returns despite a blocked native evaluation. A deliberately stalled stream writer does not block event production, and queued data remains bounded.

## Verification and scope

Focused regressions cover metadata-only reads, annotation scanning, cache bounds, unchanged polling, sibling updates, external replacements, progress, truncation, pending transactions, stalled browser calls and stalled stream delivery. Existing voice, history correction, realm binding and process-lifecycle tests pass. Native startup/recovery and detached-window synchronization/Stop probes pass with synthetic data.

Provider metadata confirms the preferred Claude and Codex models and Gemini 3.8 Flash. Defaults and existing model choices are unchanged. Gemini's unavailable older fallback remains filtered by the existing availability logic.

The broader review also recommends incremental usage indexes, malformed-record isolation, HTTP admission bounds, provider probe coalescing, scheduler dispatch changes and automatic renderer recovery. Those are separate follow-ups, not claims made by this release. The previously observed unowned white desktop rectangle still has no proven root cause.

Publication must pass the enforced full suite, exact-source Windows CI, packaged native lifecycle gates, signed upgrade rehearsal and public GitHub/website verification. The owner's running app is not restarted by publication.
