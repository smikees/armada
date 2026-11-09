# 0.99.138 — Steer an active conversation

Released from `7fa65a2876f7da081958ebc255e74572f5c2d697` on 9 November 2026.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.138) and
[website](https://armada.stamih.com/) published and verified.

Codex app-server conversations accept text steering while working, through the
same composer in the main and detached views. Steer appears alongside Stop only
when the current process has an active provider turn. Exact-run admission,
durable delivery receipts, explicit duplicate-safe Check, preserved later draft
edits and a full-width narrow input protect the owner workflow. Claude, Gemini,
Codex fallback and background jobs do not advertise unsupported steering.

The transport retains the turn's permissions and owns a bounded stdin writer so
stalled input cannot block timeout or Stop. Receipt mutations use the existing
history journal and keep one original user/assistant pair. Accepted instructions
survive subsequent context and compaction. Unknown delivery remains explicit.
See the [contract and limits](STEERING.md).

Focused steering, transport lifecycle, history recovery, rendering, realm-bound
HTTP, golden and logging checks: **203 passed**. The final native thread probe
passed **100 checks**, including steering from both views, typing focus,
single-turn persistence, narrow layout, synchronization and cancellation.
Light main and dark narrow companion captures were reviewed in two bounded
passes; the first pass exposed a cramped input, corrected before confirmation.
All fixtures were synthetic; no owner app restart, live realm or provider call.

The first candidate's local full suite passed **4,393 / six skipped**, but one
Windows CI job exposed an existing activity-marker read/delete race in dry-run
status. Windows returned PermissionError while cleanup removed the marker.
Publication stopped. The repair coordinates reads and removal with the shared
marker lock, skips marker reads for terminal/in-process runs, and rechecks the
authoritative result if completion lands during a status read. Deterministic
concurrent-reader and terminal-result regressions cover the repair. All release
gates were rerun on the repaired source; the failed CI was not waived.

The repaired candidate then passed **4,396 / six skipped** locally and the
packaged-Python CI job. The other CI job exposed a test synchronization defect:
the HTTP stress fixture has one control slot, but receiving a response body does
not imply its worker has released that slot. The next nominally sequential
control request could legitimately receive 503 during cleanup. The test now
waits for that explicit handoff before testing the next sequential request; a
new delayed-cleanup case verifies 503 during actual overlap and 200 afterwards.
Production HTTP limits and behavior are unchanged. This test-only correction
also received fresh final-source gates; no failure was waived.

The final publisher full suite passed **4,397 tests / six skipped** in 711.00s.
Both [exact-source Windows CI jobs](https://github.com/smikees/armada/actions/runs/42685701616)
passed **4,399 / four skipped** (822.96s and 692.60s). The marker repair's focused
regressions passed 156 tests; the final HTTP/dry-run/steering group passed 108.
The clean committed-source stabilization gate passed in 234.71s, retaining
`build/stabilization-20261109-204107-302037`: fault injection, three concurrent
realms, large-history budgets, three 100-check native-window cycles, page work
and owner workflows. This supplements the earlier focused and visual checks.

Packaged launcher recovery/DLL isolation, 16 session checks, 68 tray checks,
69 checks in each restart mode, 86 presentation checks and **72 signed-upgrade
checks** passed. Fresh main/companion light/dark recovery captures were reviewed.
Public update signatures, changed package/source bytes, installer hash and
matching website version/release/download links verified. Installer SHA-256:
`3047ade35d06b566cb129c1162f0ab4e67b7449b8c87075467e5247384adbda7`.
The owner's app and live realms/providers were untouched.

Protocol was checked against official app-server documentation and generated
schemas from the installed Codex CLI. Provider preferences were reviewed against
official sources on 9 November for 0.99.136 and are unchanged. Python 3.14.10 and
launcher protocol 2 remain unchanged. Distribution continues the existing
unsigned Windows beta maintenance path with Ed25519-signed update manifests.
Windows publisher signing, clean-machine WebView2 and maintainer product
acceptance remain open.
