# v0.99.150 — reviewed job changes and durable interrupted work

Published on 14 November 2026 from `731eec8cb7c21d26a9154f17f5f7bf9fa27d919e`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.150) and
[website](https://armada.stamih.com/) both offer the matching installer.

This release adds reviewed changes to existing jobs, owner-controlled coordinator
proposal scope and proactive held-job notices. Multi-time cron schedules dispatch
per occurrence. Connector start checks accept recent healthy readings and avoid
routine wait notifications, with an on-demand check in the monitoring modal.
Interrupted chats retain requests, partial output, reset notices and run/file
evidence across history edits, with recovery context for subsequent turns.
[Root causes and regression coverage](AGENT_REPORTED_FAULTS_2.md).

The enforced publisher passed **4,680 tests with 6 skips** in
**902.45 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43629549094) passed
both required Python jobs and relay validation. No failed check was waived.

Clean committed-source stabilization passed in **364.72 seconds**:
fault recovery, concurrent soak and history performance, three native window
cycles, page work and owner workflows. Evidence is retained in
`build/stabilization-0.99.150.json` and `build/stabilization-20261114-195903-957140`.

The freshly staged runtime passed **98 owner-workflow checks**
and **19 editor/recovery-control checks**, including reviewed proposal replacement, unchanged live jobs while pending,
and on-demand connector readings. A separate native thread journey passed 163 checks. Mandatory native
launcher recovery, WebView2 session, tray/restart, presentation recovery and the
signed packaged upgrade rehearsal (72 checks) also passed. Light/dark recovery panels for both window types were visually reviewed. Staged drivers verified that the
application modules came from the installer staging directory.

Public verification checked the Ed25519 signature, release commit, package hash,
all **509 tracked packaged files**, installer hash and
website links. The **23,802,841-byte** installer has SHA-256
`fae4104a777f078bdbdfd3f4577b20f1900d9fd137f3ed20b1c832ae46d67564`. The package SHA-256 is
`f7c9355e8611de00708746d416dabeed37437889a770ddde841b40627ad2bce0`. The prior website page was backed up before replacement.
Evidence: `build/release-evidence-0.99.150.json`, `build/upgrade-0.99.150.json`,
`build/public-verification-0.99.150.json`, `build/website-0.99.150-publication.json`,
`build/owner-staged-0.99.150.json` and `build/readiness-staged-0.99.150.json`.

Provider defaults were checked against live Claude metadata, cached Codex metadata
and the connected Gemini catalogue. Existing explicit model choices and the
provider-default escape hatch are preserved. The bundled Python 3.14.10 remains
the latest 3.14 maintenance release checked at
[python.org](https://www.python.org/downloads/). Runtime compatibility is unchanged.

This continues the owner-authorized maintenance beta distribution: update assets
are Ed25519-signed, while Windows publisher signing and clean Sandbox acceptance
remain unverified. Prior release assets remain available; any faulty release must
be replaced through the signed update process. The user's app was not restarted.
