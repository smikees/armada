# 0.99.137 — Compact thread activity

Released from `f07186ce8d5db1811689fb7f8006e31ae0526d09` on 9 November 2026.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.137) and
[website](https://armada.stamih.com/) published and verified.

Working replies show their latest activity in one collapsed row between the
written update and current working indicator. Expansion materializes ten rows
at a time, newest first; More reveals the next page. Individual commands,
inputs, results and thinking summaries remain available. Expansion, loaded
pages, open details and keyboard focus survive progress updates independently
in each view. The existing 80-entry progress buffer and execution are unchanged.

Final focused thread, persistence, token, escaping, documentation, release and
golden checks: **418 passed**. The synthetic native thread
probe passed **89 checks**, including pagination, new streamed events, detail
and focus preservation, narrow layout, shared-window synchronization and Stop.
Light main-window and dark compact-window captures were reviewed. The initial
sandbox run could not reach localhost fixture servers; rerunning outside that
network restriction passed. No live realms/providers or owner app restart.

The publisher's final full suite passed **4,363 tests / six skipped** in 696.90s.
Both [exact-source Windows CI jobs](https://github.com/smikees/armada/actions/runs/42649222257)
passed **4,365 / four skipped**. The first CI attempt timed out starting the
unchanged PowerShell installer preflight on one runner. The other matrix job
passed; three local repetitions passed in 1.64s, 1.63s and 2.48s. Retrying the
failed CI job on the unchanged source passed in 760.59s. The publisher's full
local suite was also repeated. No test timeout or release requirement was waived.

The final committed-source native thread probe passed all 89 checks again.
Packaged launcher recovery/DLL isolation, 16 session checks, 68 tray checks,
69 checks in each restart mode, 86 presentation checks and **72 signed-upgrade
checks** passed. Fresh main/companion light/dark recovery captures were reviewed.
Public update signatures, package/source bytes, installer hash and matching
website version/release/download links verified. Installer SHA-256:
`4d98fcb6aaf75edb15d9bac1157d78e4aed27cf104d30d7131181b8a1c33b314`.

Provider preferences were reviewed against official documentation on 9 November
for 0.99.136; no model/provider/runtime changes are included here. Python 3.14.10
and launcher protocol 2 remain unchanged. Distribution continues the existing
unsigned Windows beta maintenance path with Ed25519-signed update manifests.
Windows publisher signing, clean-machine WebView2 acceptance and maintainer
product acceptance remain open.
