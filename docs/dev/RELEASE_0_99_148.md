# v0.99.148 — connector outage recovery and guarded job starts

Published on 14 November 2026 from `a2a9765d6239798e44eec6d94a1d4e7add7ad1d1`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.148)
and [website](https://armada.stamih.com/) both offer this version.

This release adds the [outage-recovery controls](BROKER_RELIABILITY.md): connector
health monitoring without model calls, durable prerequisite waits, dependent
start windows, custom retry delays, approved fallback jobs, guarded coordinator
starts and command secrets. Approval seals cover the new choices. The owner
accepted the same-user Windows credential boundary and deferred live IBKR sign-in.
Existing broker registrations, live job settings and the temporary Windows test
account were not changed. Broker OAuth refresh and gateway work remain deferred.

The enforced local publisher passed **4,628 tests with 6 skips** in
**880.19 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43592737012) passed both
required Python jobs and the relay: **4,630 tests with 4 skips** each, in 902.40
seconds for the pinned job and 792.76 seconds for the current-3.14 job. Both
resolved Python 3.14.10. No failed check was waived.

Clean committed-source stabilization passed in **373.34 seconds**,
including 280 fault tests, concurrent soak/history checks, three 163-check native
window cycles, six page-work checks and 98 owner workflows. Evidence:
`build/stabilization-0.99.148.json` and `stabilization-20261114-130127-296614`.

The freshly staged Python 3.14.10 runtime passed **98 owner-workflow
checks** and **11 outage-control browser checks**. These loaded
Armada from the installer staging folder, including saving/reloading job conditions,
approval seals, watch/credential modals, credential storage and panel geometry.
Evidence: `build/owner-staged-0.99.148.json` and
`build/readiness-staged-0.99.148.json`. The captured forms and system-job layouts
were reviewed. Mandatory installer recovery, WebView2 session, tray/restart,
presentation recovery and the signed packaged-upgrade gate passed.
One background calendar poll logged a 50 ms admission-lock timeout during the
staged owner journey; it returned a controlled error, and the journey recovered
and passed all calendar/status checks. No failed assertion was ignored.

Public verification checked the Ed25519 manifest signature, release commit,
package hash, every tracked packaged Armada file, installer hash and website links.
The **23,777,969-byte** installer has SHA-256
`e19422e3008e2d3a63e4237d49669d3a8a60e455abbebd680338ef411d40b794`; the update package has SHA-256
`0e654f6ecf9066bc6eeca4e11839d912bad77da20dded170b4cc41af66275548`. Evidence: `build/release-evidence-0.99.148.json`,
`build/upgrade-0.99.148.json`, `build/public-verification-0.99.148.json` and
`build/website-0.99.148-publication.json`. The replaced website page was backed up.

Provider defaults were checked against live Claude metadata, cached Codex metadata
and the connected Gemini catalogue. Connected-provider filtering and the
provider-default fallback remain intact. Runtime compatibility is unchanged;
Python 3.14.10 matches the latest 3.14 maintenance release checked at
[python.org](https://www.python.org/downloads/release/python-31410/).

This continues the owner-authorized maintenance beta distribution. Update assets
are Ed25519-signed; trusted Windows publisher signing and clean Sandbox acceptance
remain unverified. A faulty release must be replaced through the signed update
process; previous artifacts remain available. The owner's app was not restarted.
