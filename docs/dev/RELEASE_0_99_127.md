# 0.99.127 — Isolate damaged records and preserve repair evidence

M5 candidate, locally verified on 5 November 2026. Publication and final-source
release gates are pending explicit approval. Maintainer acceptance remains separate.

Healthy agents and core realm pages remain usable when another agent/job contains
malformed JSON, duplicate keys, invalid encoding or invalid field types. Damaged
records show repair information and cannot authorize model/command execution.
Automatic inbox dispatch holds damaged recipients without consuming their messages.

The owner can review complete replacement configuration on the affected detail page.
Authenticated, realm-bound repair checks the original digest, validates the new
configuration and preserves exact original bytes plus an owner receipt before
atomic replacement. Ordinary editors cannot silently reset damaged input.

Malformed history rows are excluded from presentation with an incomplete-data
warning. That agent's scheduled jobs are held to avoid repeating uncertain work;
healthy agents remain eligible. History repair requires verified evidence, and no
repair replays work. See [the record-health contract](RECORD_HEALTH.md).

## Validation

- Pinned isolated gate for implementation commit `c2ffa92`: **4,087 passed, six skipped**.
- Final review reproduced an invalid retry-count detail-page failure. Four new
  regression cases failed first; routing these through shared retry validation fixed
  the repair view. **383 focused checks passed** on that follow-up change, including
  record health, retries, tool safety and generated references.
- Earlier final page/state/reference check: **401 passed**. Reviewed snapshots only
  add repair help text and the changelog. Repair-form JavaScript syntax checked.
- Synthetic checks cover all core sibling pages, provider admission, command refusal,
  scheduler/inbox isolation, evidence preservation, stale reviews, failed replacement,
  authenticated HTTP repair, origin refusal and immutable realm binding.
- Warm reader observation: 40 agents / 120 jobs, 12 interleaved iterations, median
  50.2 ms before / 68.3 ms after. This was under concurrent test load and is not an
  end-to-end navigation or acceptance benchmark; retained for M9.

Automatic approval review blocked the public push, distinguishing this new candidate
from the earlier explicit 0.99.123 approval. Nothing was pushed or published. Once
approved, the mandatory publisher must rerun the full gate on the final source,
require exact-source Windows CI and packaged native/upgrade checks, and verify public
artifacts and website. None of those pending release results is claimed here.

Ignored local evidence: `build/m5-pinned-gate.log`, `build/m5-final-focused.log`,
`build/m5-retry-red.log`, `build/m5-retry-final.log` and `build/m5-reader-timing.json`.

No live realm or provider is used for validation. The owner's app is not restarted.
The runtime/launcher remain compatible with 0.99.125 and newer. Older clients still
need the full installer once. This release retains the authorized unsigned Windows
maintenance distribution, separately signed update manifests, and the existing
unverified clean-machine WebView2/publisher-signing acceptance boundary.

Provider defaults are unchanged from the official metadata review recorded in
[0.99.126](RELEASE_0_99_126.md) earlier on 5 November 2026.
