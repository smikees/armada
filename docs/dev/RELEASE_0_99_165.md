# v0.99.165 — detached shadows and editable steering

Published on 24 November 2026 from `d13745e680667c50d2a7236a0a91440c055aa366`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.165) and
[website](https://armada.stamih.com/) offer the matching installer.

Detached-window shadows and antialiased edges now remain immediately above their
own window, below any foreground thread. Previously each refresh used
ShowWindow(SW_SHOWNOACTIVATE), which could raise a background decoration over a
front window. Both decorators now use a shared SetWindowPos operation that places
them beside their owner without activating or reordering that owner. This covers
delayed startup captures, movement, hiding and re-showing overlapping threads.
Normal Windows activation still brings the selected window and its decorations
forward together. The saved-size and restart cascade behavior is unchanged.

OpenAI's voice controls incorrectly disabled the composer for every active run,
overriding the steering state immediately after each thread poll. They now lock
input only for an active local or remote audio session or audio teardown. Ending
audio re-enables text drafting/steering even if the agent is still working. The
thread state updater respects the same audio ownership. Drafts and Stop retain
their existing behavior.

The HWND regression runs on a private Windows desktop and checks real native
stacking after refresh, hide/re-show and activation changes. Browser regressions
cover voice controls during ordinary work, active audio, audio ending and draft
preservation. The hidden WebView2 journey now switches to the OpenAI layout and
inserts text using native editing in both main and detached steering composers,
then verifies focus and editability survive polling and acknowledged delivery.
Repeated native validation also exposed late font loading during list measurement.
The composer recalculates hanging indents when lazy-loaded marker fonts finish;
the geometry test waits for fonts before comparing actual rendered glyph positions.

Python's [official release list](https://www.python.org/doc/versions/) was checked
on 24 November 2026: 3.14.10 remains the current patch in the supported 3.14 branch.
The bundled runtime is unchanged. Read-only provider metadata confirmed all
first-choice defaults remain available; existing defaults and model settings are unchanged.

This release follows the standing maintenance beta procedure: Ed25519-signed
update assets and an unsigned Windows installer. Windows publisher signing and
clean Sandbox acceptance are not claimed. Publication does not restart the owner's app.

The full isolated local suite passed **4,938 tests with 6 skips** in
**911.96 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/45430900519) passed
both Python jobs and relay. Stabilization passed recovery, a 30-round concurrent
soak, history performance, three native cycles of 277 checks each, page-work and
owner workflows. Evidence is retained in `build/stabilization-20261124-165430-710384`.

Packaged launcher recovery, DLL isolation, authenticated sessions, tray lifecycle,
restart and presentation recovery passed. The signed update rehearsal from
0.99.164 passed **72 checks**. The final packaged
runtime passed **124 owner-workflow checks** and
**277 thread-window checks**.

Public verification checked the Ed25519 manifest signature, source commit, all
**519 tracked package files**, installer hash and
matching website release/download links. Installer: **23,545,834
bytes**, SHA-256 `1560970394788edfd3ea35a9ffe93bacb9bb386ffb901154b7bb211d44b7a230`.
Package SHA-256: `0279eada5db8cf38ca4dd617f32f15ccb1629fde95b1c36a3a1adab304463e29`.

Automatic approval review initially stopped release creation. Local preparation
completed all enforced publication checks and paused at that final command. The
owner explicitly approved the exact GitHub payload and website update, after
which unchanged source, notes, artifact hashes and CI were rechecked and the
pending publication completed. The running application was not restarted.

Evidence: `build/release-evidence-0.99.165.json`,
`build/prepared-publication-0.99.165.json`, `build/public-verification-0.99.165.json`,
`build/website-0.99.165-publication.json`, `build/stabilization-0.99.165.json`,
`build/owner-staged-0.99.165.json`, `build/thread-staged-0.99.165.json`,
`build/release-defaults-0.99.165.json`, `build/golden-review-165.diff` and
`build/prepare-publication-0.99.165.log`.
