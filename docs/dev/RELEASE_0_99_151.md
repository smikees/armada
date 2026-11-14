# v0.99.151 — scheduler survives held job outcomes

Published on 14 November 2026 from `af03cb050535bddd78f5cb775f9b9ac4c72c7450`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.151) and
[website](https://armada.stamih.com/) offer the matching installer.

The daemon no longer exits while displaying a job held for changed approval,
unreadable records or another early admission failure. Job outcome metadata is
consistent, and reporting tolerates missing fields. Approval holds remain enforced;
no live job settings or past attempts were changed.
[Root cause and regression coverage](SCHEDULER_HELD_OUTCOME.md).

The mandatory local gate passed **4,700 tests with 6 skips** in
**829.88 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43641671843) passed both
required Python versions and relay validation. Focused scheduler tests passed
107 cases; page/reference and regression tests passed 386 cases.

Clean-source stabilization passed in **350.77 seconds**, including
fault recovery, concurrent activity, history performance, three native window
cycles, page work and owner workflows. Fresh installer staging passed
**98 owner-workflow checks** and **19 job-editor checks**.
Mandatory launcher recovery, session, tray/restart and presentation checks passed,
as did the signed packaged upgrade rehearsal (**72 checks**).
Light and dark recovery screens for both window types were visually reviewed.

Public verification checked the update signature, release commit, all
**509 tracked package files**, installer hash and website links.
Installer: **23,806,116 bytes**, SHA-256 `cc0e89e61c7f63cce500184b0df15cdab09ad55f41ad47cab8df14828601256b`.
Package SHA-256: `d9277fbe7b80f7f6c5e1c5ea31a195dddde391a8b5c53890fa1e22a1790fbd13`.
Evidence is retained in `build/release-evidence-0.99.151.json`,
`build/public-verification-0.99.151.json`, `build/website-0.99.151-publication.json`,
`build/stabilization-0.99.151.json`, `build/stabilization-20261114-221335-643472`,
`build/owner-staged-0.99.151.json` and `build/readiness-staged-0.99.151.json`.

Runtime dependencies and provider defaults are unchanged from v0.99.150,
reviewed earlier on the same day. Existing explicit provider/model choices remain
unchanged. This continues the owner-authorized maintenance beta: update assets
are Ed25519-signed; Windows publisher signing and clean Sandbox acceptance remain
unverified. The owner's running app was not restarted to publish this release.
