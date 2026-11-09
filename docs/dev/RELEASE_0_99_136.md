# 0.99.136 — Timed inbox tasks and ARMADA system memory

Released from `fcc1866e8f689dc8621b0260f32c2760f89539b6` on 9 November 2026.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.136) and
[website](https://armada.stamih.com/) published and verified.

Inbox processing windows are code-enforced, including after capacity waits.
An acknowledged owner Process now warning overrides a valid window once and
records that choice. App Settings manages shared instructions for every agent
and realm. [Behavior and boundaries](INBOX_TIMING.md).

Focused inbox, memory, Settings, documentation and golden checks: **522 passed**.
Provider/execution checks: **117 passed**. Final timestamp-range and documentation
regressions: **352 passed**. Extreme UTC-offset conversions now fail with a clear
validation error instead of an overflow. The final native UI probe passed ten
checks, including Settings Save/Restore and both warning outcomes. Light Settings
and dark 1024px timing-warning captures were reviewed, as were all three changed
golden pages (context size, Help index and Settings).

The publisher's final full suite passed **4,358 tests / six skipped** in 717.42s.
Both [exact-source Windows CI jobs](https://github.com/smikees/armada/actions/runs/42633170422)
passed **4,360 / four skipped**. The final clean-source stabilization gate passed
in 210.75s, including faults, concurrent stress, history budgets, three 79-check
native-window cycles, six page-work checks and 16 owner-workflow checks.
Evidence directory: `build/stabilization-20261109-151725-769789`.

Packaged launcher recovery/DLL isolation, 16 session checks, 68 tray checks,
69 checks in each restart mode, 86 presentation checks and **72 signed-upgrade
checks** passed. Fresh main/companion light/dark recovery captures were reviewed.
Public update signatures, package/source bytes, installer hash and matching
website version/release/download links verified. Installer SHA-256:
`2552c3cf21f9bddca1b3fe5b4b0edeb51ac3a82b3f77bcfe58ba1bc7091e3cf7`.
Synthetic fixtures only; no owner app restart or live realm/provider testing.

Provider preferences were reviewed on 9 November against official
[Claude models](https://platform.claude.com/docs/en/models/overview),
[OpenAI models](https://developers.openai.com/api/docs/models) and
[Gemini models](https://ai.google.dev/gemini-api/docs/latest-model).
No provider/model selection changes are included; authenticated catalogues still
control availability. Python 3.14.10 and launcher protocol 2 remain unchanged.
Publication uses the existing unsigned Windows beta maintenance distribution
with Ed25519-signed update manifests. Windows publisher signing, clean-machine
WebView2 acceptance and maintainer product acceptance remain open.
