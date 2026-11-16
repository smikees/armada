# v0.99.155 — thread drafts and matching list markers

Published on 16 November 2026 from `6e3219f9e63caf4e2e0078396d2344947e66df69`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.155) and
[website](https://armada.stamih.com/) offer the matching installer.

Drafts previously used the entire page URL as their identity. Visiting Memories
and returning to Threads omits the thread query, so a remembered conversation
looked under a different storage key. Drafts now follow the rendered realm,
agent and thread identity, preserving separate drafts in each view. Existing
URL-keyed drafts migrate when their page is visited, and native recovery accepts
the current page's previous keys. Empty drafts remain cleared.

The composer uses two original circular glyphs with equal outlines and matching
vertical centres. Main items are filled and sub-items hollow. The font maps only
the two markers, preserving the selected body font for text and indentation.
Its source builder is reproducible and adds no runtime build dependency. The
font uses the repository's PolyForm license and is identified in the notices.

The mandatory isolated local gate passed **4,750 tests with 6 skips**
in **901.95 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43868418747) passed
both required Python jobs and relay validation. Focused draft, thread, run-control
and font tests passed (108 checks); a separate corrected license/font/draft pass
passed 60 tests. All intended golden-page changes were reviewed, and the
generated module references remained unchanged.

Clean-source stabilization passed in **406.71 seconds**,
including fault recovery, concurrent storage, history performance, three native
multi-window repetitions, page workflows and owner workflows. An earlier attempt
hit a synthetic realm-switch reload failure; its unchanged diagnostic rerun
passed all 180 checks, and the final complete gate passed every stage without
relaxing assertions.

Freshly packaged code passed **124 owner-workflow checks** and
**7 navigation checks**. The native navigation probe uses
the actual Threads → Memories → Threads links and verifies a remembered sub-thread,
exact multiline text with nested bullets, thread separation and clearing. A
separate marker comparison passed 19 browser checks for geometry, fill, alignment,
scaling and unchanged prose/spacing across the seven body fonts. Mandatory native
launcher/session/tray/restart/presentation checks and the signed packaged upgrade
rehearsal passed.

Public verification checked the update signature, release commit, all
**511 tracked package files**, installer hash and
website links. Installer: **23,510,789 bytes**, SHA-256
`d15b7d25894dfcb669a287babe162674d93b47715cb9c3de23930f38c1b5ed79`. Package SHA-256:
`9152ce55bdb34aed294345312c4b9c2c2beccd180554773a1acdb851bb4f5ec0`.

Evidence: `build/release-evidence-0.99.155.json`,
`build/public-verification-0.99.155.json`, `build/website-0.99.155-publication.json`,
`build/stabilization-0.99.155.json`, `build/stabilization-20261116-133831-839345`,
`build/owner-staged-0.99.155.json`, `build/navigation-staged-0.99.155.json`,
`build/navigation-155.json` and `build/bullet-markers/checks.json`.

Provider catalogue metadata was reviewed on 16 November with no model runs; each
preferred default remains available. Python 3.14.10 remains the current patch
in the packaged 3.14 line ([official releases](https://www.python.org/downloads/)).
This continues the owner-authorized maintenance beta: update assets are
Ed25519-signed; Windows publisher signing and clean Sandbox acceptance remain
unverified. The owner's running app was not restarted to publish.
