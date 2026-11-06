# Disposable history summaries — M9

Decision, 6 November 2026: keep JSON/Markdown authoritative and build bounded,
process-local presentation summaries. A persisted database would add migration,
repair and portable-realm obligations without helping the common warm reads.

`run_summary` keeps latest status per task, daily accounting, model/day usage,
legacy job-turn timestamps and byte offsets for date queries. It retains no run
output or conversation content. Overview, Usage and recent attention/week views
use these projections. Explicit full-history reads, scheduling, policy validation
and execution admission still read canonical records. No cache can grant work.

Each entry tracks file identity, size, nanosecond timestamps and annotation files.
Growth is incremental only when the old complete prefix hashes identically and
ends in a newline. It still reads that prefix to hash it; only the appended rows
are decoded and aggregated. Replacement, truncation, edit-plus-append and changed
annotations rebuild. A 30-second revalidation catches edits that preserve all
metadata. That is a presentation freshness bound, not an authorization guarantee.
Cold reads and periodic rebuilds still scan history and can cost more than the old
single full scan. First-window startup remains on metadata-only reads.

Writers and summary builders share the existing file lock. Date queries recheck
the generation under the lock and retry if it changed. Invalid rows preserve their
diagnostics and source bytes. A continuously changing/unreadable file can produce
an incomplete view; the detailed realm reader exposes its history diagnostics.
The display cache is neither a backup nor evidence that a record is valid to run.

Summary retention is limited to 64 files and a 32 MiB accounting budget, with LRU
eviction; the estimate is not a hard Python heap cap. Rebuild working memory and
the canonical file size are not capped by this presentation cache. Fixed lock
stripes coalesce rebuilds without accumulating one lock per requested key. View
caches retain their existing count/byte bounds and recheck after another window
finishes building. No index file is written into a realm.

Conversation invalidation depends on legacy job timestamps for that thread, not
the entire run log. An unrelated report therefore does not rebuild every preview.
Each poll visits thread summaries once for both ordering and previews. Rendered
turns, message count and context estimate share the reconciled transcript snapshot;
completion between snapshot and marker lookup still gets its second read.

## Evidence and performance

`tests/test_run_summary.py` checks canonical/full-scan equivalence for every usage
window and grouping, unknown accounting, append-only decoding, rewrites,
truncation, annotations, Unicode content, concurrent appends/readers, coalescing,
fresh admission and independent previews. The native shared-window probe checks
real synchronization and Stop against an isolated deterministic engine.

Reproduce with `python tools/history_benchmark.py build/history-benchmark.json`.
The fixture contains 30,000 reports over 1,500 days, three agents and 21 threads
with 1,000 messages each. Warm figures use 12 samples; four-window measurements
are whole batches, not per-window latency. They are local synthetic observations,
not end-to-end startup, navigation or provider-speed promises.

| Read | Before p50 / p95 ms | M9 p50 / p95 ms |
|---|---:|---:|
| Warm detailed realm | 282.0 / 299.1 | 3.6 / 4.1 |
| Warm Usage | 696.1 / 715.6 | 31.8 / 64.6 |
| Unchanged thread poll | 33.7 / 38.2 | 17.1 / 17.7 |
| Four simultaneous polls | 105.1 / 116.1 | 54.9 / 59.4 |
| Metadata and roster | 1.7 / 2.0 | 1.8 / 2.3 |

The single cold detailed-realm observation increased from 355.9 to 643.0 ms,
because it now builds reusable aggregates and offsets. Initial iterations also
regressed polling; removing repeated thread enumeration fixed that regression.
No production data or owner app restart was used to measure these results.

## Recovery and release limits

Caches disappear on process exit and can be evicted without loss. If a display
regression is reported, preserve the source records and reproduce synthetically;
do not repair a display by rewriting canonical history. A release with incorrect
accounting, stale authorization, or failed native shared-window checks must not
ship. Runtime/installer compatibility is unchanged by M9. See the release evidence
for the exact tested source, packaged checks and public verification.
