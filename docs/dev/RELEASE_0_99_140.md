# 0.99.140 — A simpler Windows title bar

Released from `60c34b7499a39585fdb4575adbd04cb7ddfe75c5` on 10 November 2026.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.140)
and [website](https://armada.stamih.com/) both offer v0.99.140.

The main title bar hides the caption and icon while keeping native window
controls and dragging. On Windows 11 its background follows the current app
palette. Windows 10 uses its system caption color. The divider below the title
bar spans the window, and the divider under the main menu is inset to the page
margins. The offscreen WebView2 check verified light and dark previews, caption
dragging, and the divider geometry at wide and narrow sizes.

The publisher passed **4,402 tests with six skips**. Both Windows CI jobs
passed **4,404 tests with four skips**. The clean release commit passed the
stability gate in 226.35 seconds, with three 100-check native window cycles.
The standalone startup and tray probe passed 68 checks. Evidence is retained
in `build/stabilization-20261110-192545-831682` and `build/startup-0.99.140.json`.
[Windows CI](https://github.com/smikees/armada/actions/runs/42874997312).

The staged installer passed launcher recovery, WebView2 session, tray, restart,
and presentation checks. Light and dark recovery captures were reviewed in the
main and companion windows. The packaged upgrade from v0.99.139 passed **72
checks**. The installer follows the unsigned beta path and app updates use
Ed25519 signatures. Windows publisher signing and clean-machine Sandbox
acceptance are still open for the beta.

The live website displays the matching release and installer links. The signed
update and public package hash verified, and all seven changed package files
matched the release checkout. The downloaded installer matched the release build.
Installer SHA-256 is `a22be97532e817abe20b824b7cdc4c86903c31237d5e7cfc41fca18dc113cc0e`.
