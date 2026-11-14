# v0.99.149 — reliable schedules and run outcomes

Published on 14 November 2026 from `e8449ad22a311fcb145957a23c74f73a1979d133`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.149) and
[website](https://armada.stamih.com/) both offer the matching installer.

This release fixes untouched schedules becoming manual, late Claude events
invalidating terminal results, false missing connector aliases and optional
connector failures contaminating unrelated job audits. API fallback preserves
refusal evidence and explains critical-only eligibility. Replay, connector loss,
approval and provider-budget safeguards remain enforced.
[Root causes and regression coverage](AGENT_REPORTED_FAULTS.md).

The enforced publisher passed **4,663 tests with 6 skips** in
**880.31 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43613851093) passed
both required Python jobs (4,665 passed, 4 skipped each) and relay validation.
No failed check was waived.

Clean committed-source stabilization passed in **354.0 seconds**:
fault recovery, concurrent soak and history performance, three native window
cycles, page work and owner workflows. Evidence is retained in
`build/stabilization-0.99.149.json` and `build/stabilization-20261114-170733-925458`.

The freshly staged runtime passed **98 owner-workflow checks**
and **14 editor/recovery-control checks**, including Critical-only
schedule preservation and explicit cadence-change disclosure. Mandatory native
launcher recovery, WebView2 session, tray/restart, presentation recovery and the
signed packaged upgrade rehearsal (72 checks) also passed. Light/dark recovery
panels for the main and compact windows were visually reviewed. Staged drivers verified that the
application modules came from the installer staging directory.

Public verification checked the Ed25519 signature, release commit, package hash,
all **509 tracked packaged files**, installer hash and
website links. The **23,791,570-byte** installer has SHA-256
`e74e505b80ec0687c90135ec9b998b04b5309b61bf86d8939764b451da6bb931`. The package SHA-256 is
`2558fd75256023bf49f9c6433fc2068d085841c6ba99983e9a29886ffa3789ce`. The prior website page was backed up before replacement.
Evidence: `build/release-evidence-0.99.149.json`, `build/upgrade-0.99.149.json`,
`build/public-verification-0.99.149.json`, `build/website-0.99.149-publication.json`,
`build/owner-staged-0.99.149.json` and `build/readiness-staged-0.99.149.json`.

Provider defaults were checked against live Claude metadata, cached Codex metadata
and the connected Gemini catalogue. Existing explicit model choices and the
provider-default escape hatch are preserved. The bundled Python 3.14.10 remains
the latest 3.14 maintenance release checked at
[python.org](https://www.python.org/downloads/). Runtime compatibility is unchanged.

This continues the owner-authorized maintenance beta distribution: update assets
are Ed25519-signed, while Windows publisher signing and clean Sandbox acceptance
remain unverified. Prior release assets remain available; any faulty release must
be replaced through the signed update process. The user's app was not restarted.
