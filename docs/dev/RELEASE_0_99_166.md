# v0.99.166 — independent engines and latest-message navigation

Published on 24 November 2026 from `5652f303b2ab33e3812f9a33cf835ac2a70d2999`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.166) and
[website](https://armada.stamih.com/) offer the matching installer.

Claude, OpenAI and Gemini now have independent account-wide execution pools.
The previous shared account and realm caps could queue an OpenAI conversation
behind Claude, particularly when a critical job reduced the realm to one ordinary
slot. Each engine retains two slots, with one reserved when that engine has an
approved critical job. Different models on the same engine share its pool.
Commands retain their separate pool of two and maintenance wrappers their one
separate slot. Conversation serialization, fair realm turns, bounded queues,
cross-process ownership, Stop and post-queue permission validation remain in place.

Opening a thread or minister keeps the latest message visible through late font,
image, formula and viewport layout. Turn-size observation covers visible windows;
the existing snapshot refresh also settles hidden WebView2 windows, where resize
callbacks are deferred. Manual scrolling or transcript interaction stops this
initial following, preserving reading position. Returning through browser history
opens at the latest message and re-enables normal reading controls.

New regressions fail against the preceding behavior: independent same-realm engine
capacity, engine-specific critical reservation, and late transcript growth in
JavaScript and real hidden WebView2 geometry. Native navigation checks cover
thread clicks, minister revisits, unsent drafts and manual scrolling.

The full local gate also exposed an intermittent Gemini setup parser failure:
three hyphens inside a connector value were treated as a frontmatter boundary.
Parsing now recognizes the complete delimiter line, with a deterministic regression
using synthetic connector values. The occupied-port native test verifies that its
fixture has a nearby free pair, instead of assuming Windows assigned one beside
an available range. The initial local failure is retained in the build logs.

Read-only provider metadata on 24 November confirmed that all first-choice model
defaults remain available. Defaults and the previously verified Python 3.14.10
bundled runtime are unchanged.

This release follows the standing maintenance beta procedure: Ed25519-signed
update assets and an unsigned Windows installer. Windows publisher signing and
clean Sandbox acceptance are not claimed. Publication does not restart the owner's app.

The full isolated local suite passed **4,944 tests with 6 skips** in
**939.84 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/45467933664) passed
both Python jobs and relay. Stabilization passed recovery, a 30-round concurrent
soak, history performance, three native cycles of 277 checks each, page-work and
owner workflows. Evidence is retained in `build/stabilization-20261124-201333-163891`.

Packaged launcher recovery, DLL isolation, authenticated sessions, tray lifecycle,
restart and presentation recovery passed. The signed update rehearsal from
0.99.165 passed **72 checks**. The final packaged
runtime passed **124 owner-workflow checks** and
**277 thread-window checks**.

Public verification checked the Ed25519 manifest signature, source commit, all
**519 tracked package files**, installer hash and
matching website release/download links. Installer: **23,544,615
bytes**, SHA-256 `8b99c0ca6f2a0b3219933ccdeb1c3fbb34c1a48ba520b2b0dac9475126d28978`.
Package SHA-256: `0859851baed073cc73bc36f1e722ead0260be84e65f2927ca7589e3cb1cc067c`.

The first packaged owner-workflow attempt encountered a lock on the real Windows
account ledger: changing HOME alone does not redirect account identity. The staged
harness explicitly isolated its execution ledger, then all packaged checks passed.
The same fixture correction is retained in the owner-workflow probe for future runs.
The runtime files and built artifacts were unchanged during this continuation.

The running application was not restarted. Native page-work checks also passed
against the staged runtime, including late layout and thread/minister navigation.

Evidence: `build/release-evidence-0.99.166.json`,
`build/prepared-publication-0.99.166.json`, `build/public-verification-0.99.166.json`,
`build/website-0.99.166-publication.json`, `build/stabilization-0.99.166.json`,
`build/owner-staged-0.99.166.json`, `build/thread-staged-0.99.166.json`,
`build/page-work-staged-0.99.166.json`, `build/resume-preparation-0.99.166.log`,
`build/owner-staged-0.99.166-isolation-failure.json`,
`build/release-defaults-0.99.166.json`, `build/golden-review-166.diff`,
`build/golden-review-166-parser.diff`, `build/prepare-publication-0.99.166-failed.log` and
`build/prepare-publication-0.99.166.log`.
