# v0.99.152 — visible job approvals and simpler calendars

Published on 15 November 2026 from `7151dca9149e0efa9f2bda69b4232d5235996ffa`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.152) and
[website](https://armada.stamih.com/) offer the matching installer.

Saved jobs now show approval holds and their reasons in Jobs lists and future
calendar entries, with a review filter and owner action. Page rendering is read-only.
System work remains visible as individual calendar entries without the duplicate
section above the grid. No live job settings or approvals were changed.
[Root cause and regression coverage](JOB_APPROVAL_VISIBILITY.md).

The mandatory local gate passed **4,717 tests with 6 skips** in
**853.98 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43652713436) passed both
required Python versions and relay validation. Focused page/reference and regression tests passed 483 cases with 21 skips;
the JavaScript calendar harness and 52 native layout checks passed. The final
fixture and review-status checks passed 35 tests.

Clean-source stabilization passed in **347.12 seconds**, including
fault recovery, concurrent activity, history performance, three native window
cycles, page work and owner workflows. Fresh installer staging passed
**98 owner-workflow checks** and **19 job-editor checks**.
Mandatory launcher recovery, session, tray/restart and presentation checks passed,
as did the signed packaged upgrade rehearsal (**72 checks**).
Light and dark recovery screens for both window types were visually reviewed.

Public verification checked the update signature, release commit, all
**509 tracked package files**, installer hash and website links.
Installer: **23,806,468 bytes**, SHA-256 `e81c207b8cdef9588338dfb5f1680cf9fea481c8358c8ca5b9ddcdd174d3298e`.
Package SHA-256: `13cfdbda1ce924c05c68df7f1af16457187106e429dc4c4dfe8644700fd80ab8`.
Evidence is retained in `build/release-evidence-0.99.152.json`,
`build/public-verification-0.99.152.json`, `build/website-0.99.152-publication.json`,
`build/stabilization-0.99.152.json`, `build/stabilization-20261115-002018-373954`,
`build/owner-staged-0.99.152.json` and `build/readiness-staged-0.99.152.json`.

Runtime dependencies and provider defaults were reviewed on 15 November.
The connected catalogues still include the preferred Claude, Codex and Gemini
models (metadata only, no agent runs). Python 3.14.10 remains the current patch
in the packaged 3.14 line: [official release](https://www.python.org/downloads/release/python-31410/).
Model review is retained in `build/release-defaults-0.99.152.json`. Existing explicit provider/model choices remain
unchanged. This continues the owner-authorized maintenance beta: update assets
are Ed25519-signed; Windows publisher signing and clean Sandbox acceptance remain
unverified. The owner's running app was not restarted to publish this release.
