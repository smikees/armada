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


## Publication evidence

Published as normal/latest [v0.99.118](https://github.com/smikees/armada/releases/tag/v0.99.118) from source `78da85953175b0ddc91e3a561cc24c35ae39136b` through
`tools/publish_release.py --maintenance-unsigned`.

- Final pinned local gate: **3781 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40579720147) passed before packaging.
- Final source native probes passed: 76 detached-thread checks and 9 startup/recovery checks.
- Packaged launcher recovery and WebView2 multi-window checks passed; the packaged tray/startup gate passed 60 checks.
- Signed compatible upgrade from 0.99.117 passed 69 checks.
- An additional synthetic CLI with a non-reading local socket honored a 0.5-second timeout in 0.547 seconds through the real stream observer.
- All four public downloads match local sizes and SHA-256 values. The signed update verifies and its 437 application files match the source checkout byte for byte.
- [armada.stamih.com](https://armada.stamih.com/) was deployed with certificate-verified FTPS, a backup and a verified temporary upload/rename. The public HTTPS page and installer download match this release. Website SHA-256: `a76ed2c931a39b653da57e107a4cd6d7f4617613efbeea92f861de4ed1a96298`.
- The existing unsigned beta installer and signed update were published under the maintainer's authorization. The owner's running application was not restarted.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.118.zip` | `16989281c3a6053691e856aa4fd053663b99b4b2d5b3f6cbb3d4f7613eaf5f52` |
| `ARMADA-Setup-0.99.118.exe` | `3eda2a069e045e8823c765d96a9cd65c74084852fa983a977509a6b5aab87f1a` |
| `armada-update.json` | `3da66699ad151f871fe26a98dc301866dd5fd9b136bc4565eb8f2c08ca04f0b0` |
| `armada-update.json.sig` | `c4ba1c3cbaff1e826048403aef964d86597e72eb261327627eaedb0dccce2205` |
