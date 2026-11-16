# v0.99.157 — shared code and obsolete-path removal

Published on 16 November 2026 from `e4d41db4d3f8d0441ef2bd0deade152474d61b8f`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.157) and
[website](https://armada.stamih.com/) offer the matching installer.
See the [ordered plan](SIMPLIFICATION_2026_11.md).

Removed nine unused UI helpers, their private model seed list, the unused
fail-fast connector checker and unreachable duplicate queued-turn creation.
The active connector withholding and post-wait authorization paths remain.
Memory and realm readers now share their existing flat metadata parser;
custom sections share a document wrapper; Claude JSON and streaming execution
share tool-mode selection with unchanged precedence and arguments.
Page dependencies are explicit, with package compatibility exports retained.
Add-on documentation now describes the active dashboard and Alexander consumers.

The one intended behavior correction is the static cockpit provider label:
it follows the realm default model and identifies itself as the realm default.
No saved configuration, agent model or job model is migrated.

Before the version bump, all 21 desktop golden pages passed unchanged.
A before/after comparison of 26 custom-section renders was byte-identical,
covering light/dark mode, local files, live URLs, snapshots, app assets,
overlapping precedence, widgets and missing sections. Focused
checks passed 406 tests with 5 intentional skips. Generated reference checks
passed 371 tests; regolding intentionally wrote/skipped 21 snapshots. Review
found only the new Settings changelog entry, with no removed or changed HTML.
The enforced isolated release suite passed **4,797 tests with 6 skips**
in **885.80 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43938637812)
passed both required Python jobs and relay validation.

Live Claude/Gemini metadata and the local Codex catalogue confirm each provider's
preferred default is available. Gemini's secondary seed was not present in the
connected account's returned list; connected-provider filtering and the provider
default escape hatch remain unchanged. No model work was launched for this review.

This continues the established owner-authorized maintenance beta procedure:
Ed25519 update signing is required; Windows publisher signing and clean Sandbox
acceptance remain outside the validated boundary. The owner's running app was
not restarted to publish.

The clean-source stabilization gate passed in 384.57 seconds:
282 fault-handling tests, a 30-round concurrency soak, history performance
budgets, three native thread-window passes (180 checks each), six page-work checks
and 124 owner-workflow checks. Its retained directory is
`build/stabilization-20261116-202229-781189`.

Mandatory packaged launcher recovery, session, tray, restart and presentation
recovery checks passed. Main and companion recovery-panel captures were reviewed
in light and dark themes; text and controls fit without clipping.
The freshly staged runtime passed **124 owner-workflow checks**. The signed upgrade from the previous published release
passed **72 checks**.

The first staged owner pass logged one transient calendar admission-lock timeout
while still passing all 124 checks. Calendar/system-job/admission code and the
file-lock implementation match the pre-refactor source. A complete packaged
repeat passed all 124 checks with an empty error log. Both results are retained
in `build/owner-staged-first-0.99.157.json`, `build/owner-staged-0.99.157.json`
and `build/owner-staged-repeat-0.99.157.log`. This does not establish that
transient contention is impossible; no source change was made to suppress it.

Public verification checked the Ed25519 update signature, exact release commit,
all **511 tracked package files**, installer hash and
matching website links. Installer: **23,505,733 bytes**, SHA-256
`4e47567bb10c2278f33ab024e5a90ebf0027c72ed238c3cc1066883444af5989`. Package SHA-256:
`f852db3f2935569585129b636e36229f64aba14efbcceb4607353a2cfaf67c1c`.

Evidence: `build/release-evidence-0.99.157.json`,
`build/public-verification-0.99.157.json`, `build/website-0.99.157-publication.json`,
`build/stabilization-0.99.157.json`, `build/owner-staged-0.99.157.json`,
`build/release-defaults-0.99.157.json` and `build/publish-0.99.157.log`.
The packaged runtime remains Python 3.14.10, reviewed against the
[official Python release listing](https://www.python.org/doc/versions/).
