# v0.99.154 — clearer settings, dark themes and companion windows

Published on 15 November 2026 from `e350d99f4729fa721bd376885d114d5d37296bb9`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.154) and
[website](https://armada.stamih.com/) offer the matching installer.

Overview now reads Remaining API, retains the explicit estimate label, and opens
Claude's fallback modal directly from the amount with its budget field focused.
Headline figures are two typographic points smaller. Bullets are larger without
changing ordinary chat text or nested indentation. Unsaved Save buttons have a
stronger pulse and halo with a reduced-motion alternative; isolated execution
controls have spacing below the folder field.

All six themes have readable light/dark previews. Four alternate themes retain
their own accent colours in dark mode. Alexander shares the detached-thread
antialiased perimeter, native shadow and header scale. No provider credentials,
Console settings, running jobs or live realm approvals were changed.
[Implementation and coverage](UI_POLISH_154.md).

The mandatory local gate passed **4,746 tests with 6 skips** in
**869.19 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43734030141) passed both
required Python versions and relay validation. Focused regression tests passed;
410 golden/reference/settings checks passed, with separate focused native lifecycle
and API regressions. The companion probe passed 180 checks including Alexander's
shared geometry, resizing, shadow, perimeter and close disposal. All twelve
selected/unselected theme and mode combinations passed contrast checks in WebView2;
the final appearance pass explicitly asserted each selected theme and colour mode.
Light/dark previews and companion composites were visually reviewed.

Clean-source stabilization passed in **390.24 seconds**, including
fault recovery, concurrency, history performance, native windows and owner workflows.
Fresh installer staging passed **124 owner-workflow checks** and
**19 job-editor checks**. Mandatory launcher/session/tray/restart
and presentation checks passed, as did the signed packaged upgrade rehearsal
(**72 checks**).

Public verification checked the update signature, release commit, all
**510 tracked package files**, installer hash and website links.
Installer: **23,826,542 bytes**, SHA-256 `5bd909eb50538922733ea43d63b3e975939f1f7e9809dc4a30b7247315c30ae1`.
Package SHA-256: `c3cabcf9855fdb97c75b481a75f52543af16380d87b7a3d9ef7763432266f52a`.
Evidence: `build/release-evidence-0.99.154.json`, `build/public-verification-0.99.154.json`,
`build/website-0.99.154-publication.json`, `build/stabilization-0.99.154.json`,
`build/stabilization-20261115-171124-241480`, `build/owner-staged-0.99.154.json`,
`build/readiness-staged-0.99.154.json`, `build/ui154-confirm-appearance/result.json` and
`build/ui154-final-thread/result.json`.

Provider catalogue metadata was reviewed on 15 November with no model runs;
the preferred default for each provider remains available. Python 3.14.10 remains the current patch
in the packaged 3.14 line: [official release](https://www.python.org/downloads/release/python-31410/).
This continues the owner-authorized maintenance beta: update assets are
Ed25519-signed; Windows publisher signing and clean Sandbox acceptance remain
unverified. The owner's running app was not restarted to publish.
