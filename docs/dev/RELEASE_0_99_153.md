# v0.99.153 — calendar, jobs, settings and budget visibility

Published on 15 November 2026 from `7ab5667810b5e15211c28bc93f86b30da62161c9`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.153) and
[website](https://armada.stamih.com/) offer the matching installer.

Calendars remember All/User/System filters and use the monochrome Armada symbol.
Jobs have expandable Markdown descriptions and appear in Activity monitor while
running. Nested bullets use hollow markers and deeper indentation in both thread
views. Realm run limits are under Advanced and use the overall Save; unsaved
settings pulse with a reduced-motion alternative. Agent-level permissions control
cross-agent job-change proposals, defaulting on for owner-appointed coordinators
and off for regular agents while preserving explicit choices.

Overview displays an explicitly labelled estimated Claude budget, entered in the
fallback modal minus Armada-reported monthly costs. Unknown completed-run costs
suppress the estimate. Console remains the spending authority. Custom sections
now show immediate loading feedback on navigation. No live job approvals, provider
limits or owner credentials were changed. [Implementation and coverage](UI_POLISH_153.md).

The mandatory local gate passed **4,740 tests with 6 skips** in
**858.34 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43723625860) passed both
required Python versions and relay validation. Focused regression tests passed;
397 golden/reference/policy checks passed, along with shared JavaScript harnesses.
Native main/detached thread checks passed. The delayed custom-section navigation
probe confirmed feedback before its held response. All 57 native System layout
checks passed, including filter persistence, expansion, narrow and scaled views.

Clean-source stabilization passed in **377.39 seconds**, including
fault recovery, concurrency, history performance, native windows and owner workflows.
Fresh installer staging passed **109 owner-workflow checks** and
**19 job-editor checks**. Mandatory launcher/session/tray/restart
and presentation checks passed, as did the signed packaged upgrade rehearsal
(**72 checks**). Light and dark recovery screens for
both window types were visually reviewed.

Public verification checked the update signature, release commit, all
**510 tracked package files**, installer hash and website links.
Installer: **23,814,613 bytes**, SHA-256 `e17d964c120de0a3b98d7b7f07e04c98a7f7d77e1bb6144c32e27ece8981b7d1`.
Package SHA-256: `6d4caf12db4f0003a74b0f3c96de287a18c52a5f2a5a84de071119322d1ce3a3`.
Evidence: `build/release-evidence-0.99.153.json`, `build/public-verification-0.99.153.json`,
`build/website-0.99.153-publication.json`, `build/stabilization-0.99.153.json`,
`build/stabilization-20261115-151842-501236`, `build/owner-staged-0.99.153.json`,
`build/readiness-staged-0.99.153.json`, `build/navigation-153.json` and
`build/thread-window-153.json`.

Provider catalogue metadata was reviewed on 15 November with no model runs;
configured preferences remain available. Python 3.14.10 remains the current patch
in the packaged 3.14 line: [official release](https://www.python.org/downloads/release/python-31410/).
This continues the owner-authorized maintenance beta: update assets are
Ed25519-signed; Windows publisher signing and clean Sandbox acceptance remain
unverified. The owner's running app was not restarted to publish.
