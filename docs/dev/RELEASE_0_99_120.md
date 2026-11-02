# 0.99.120 — Explicit tools for proposed jobs

Agent proposals previously accepted an omitted tools choice, so tool-dependent work
could reach its due date without the tools needed to produce its output.

## Changes

- Agent proposals require an explicit JSON boolean `allow_tools`. Approval displays
  and edits the choice; text-only proposals with file, connector or messaging hints
  require a warning acknowledgment. Command proposals keep their existing behavior.
- Agent guidance includes the field and directs tool-dependent drafts to choose true.
  No missing field is converted to true by validation, approval, lint or execution.
- Enabled jobs in every registered active realm are audited at startup and daily.
  Jobs pages read the current findings locally. One durable review notification per
  job uses existing approval-needed channel settings; job files remain unchanged.
- Saved job choices override agent/caller tools flags. A required output or destination
  with tools off fails before engine selection or context/model work, records a startup
  configuration failure and uses the existing failure notification without retrying.
- Approval and notification history use shared locks and atomic writes.

The warning heuristic does not block legitimate text-only work. The hard guard is
limited to required result-contract outputs/destinations and invalid boolean values.
Daily scans are local file reads, with no provider polling or page-render network work.
Five-field cron expressions recur annually even if they name a month and day, so this
release does not label them as jobs that will never run again.

## Validation

Synthetic tests cover explicit booleans, editable approval and warning confirmation,
immutable legacy jobs, notification deduplication, all-realm daily checks and pre-run
failures across Claude, Codex and Gemini without an engine/model call. Publication
evidence is recorded below. Tests do not use
personal realm data or restart the owner's running application.

The clean baseline passed 3,817 tests (5 skipped). Existing permission, memory,
provider-translation and Gemini fixtures now explicitly enable tools for the tool
behavior they exercise; all four regression groups pass with their original denial
and isolation assertions intact. Approval, documentation and golden checks passed
316 tests. Synthetic browser checks covered missing choices, warning confirmation,
light/dark appearance and an empty error console. Golden changes are limited to the
Jobs help search text and changelog.

On November 2, read-only provider metadata confirmed the preferred Claude Opus,
Codex Sol and Gemini Flash entries. Defaults and provider authentication remain
unchanged. The publisher enforced the final pinned suite and exact-source CI before
packaging and publication.

Hosted Windows CI exposed short test-only deadlines in Node startup, concurrent
memory I/O and asynchronous voice replies. These synchronization waits now allow
60, 60 and 15 seconds respectively. Behavior, permission and transcript assertions
are unchanged; no application timeout or retry policy was relaxed.

## Publication evidence — November 2, 2026

Published [v0.99.120](https://github.com/smikees/armada/releases/tag/v0.99.120)
from source `7bd08bc05c59202619d488ffa93ae80ca8734403` through
`tools/publish_release.py --maintenance-unsigned`. The final isolated suite passed
**3,868 tests, with 5 skipped**. [Exact-source CI](https://github.com/smikees/armada/actions/runs/41510128748)
passed both Windows Python jobs and the relay job.

The source native startup probe passed 17 checks. Packaged checks passed recovery at
all five interruption points, 16 WebView2 session checks, 68 tray lifecycle/recovery
checks and 69 signed-update upgrade checks. Build evidence is retained in
`build/release-evidence-0.99.120.json`, `build/tray-lifecycle-staged.json` and
`build/upgrade-0.99.120.json` outside version control. All probes used isolated data;
the owner's running application was not restarted or upgraded.

Downloaded all four public assets and compared their bytes, sizes and SHA-256 hashes
with the build. Verified the Ed25519 manifest signature, its source commit and package
hash, and all 439 packaged files against the committed application source.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `armada-0.99.120.zip` | 7,096,184 | `70ce8f4042889c835242e0a4e18a99f6fd31026e2ccebe755d09ea2938f87d43` |
| `ARMADA-Setup-0.99.120.exe` | 22,008,767 | `1a5f9d3f6b02ff4c63f7d25f9dfecb9f41953a68c6267b23863731da712f7f44` |
| `armada-update.json` | 349 | `b3061bdc4d9c73cd2f4c68ac3dcc6b3871ce4d966c31ccaa525ce1e97c005564` |
| `armada-update.json.sig` | 89 | `3970258a07031bf9c04fb1d9757dca6f832666e63340af39205cbce9e3e8eee8` |

[armada.stamih.com](https://armada.stamih.com/) was published through the documented
FTPS procedure, with remote backups saved under the private deployment backup
`20261102T194357Z`. The public page shows 0.99.120 and its installer link returns the
matching release asset. Its HTML matches the repository after normalizing line
endings and removing only the hosting script already present before deployment.
The fetched public HTML SHA-256 was
`17082b88c0e52072680550411a3c4e992ff71b91924401d410284b46c8799386`.

The existing maintenance beta boundary remains: the installer lacks Windows
publisher signatures, and clean-Sandbox GUI acceptance is not certified. Update
manifests remain Ed25519-signed. The bundled Python 3.12.10 runtime is unchanged;
the [Python 3.12.16 source-only security release](https://www.python.org/downloads/release/python-31216/)
was reviewed. Refreshing the embedded runtime requires a separate installer and
runtime validation; this release does not claim that runtime is current.
