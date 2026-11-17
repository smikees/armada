# v0.99.159 — resizable Register and stable page loading

Published on 17 November 2026 from `c717ec50801d061da56577f1c6647425d4f694b9`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.159) and
[website](https://armada.stamih.com/) offer the matching installer.

Register columns have pointer and keyboard resize handles. Widths are local
presentation preferences keyed by the document's immutable realm identity, shared
with promoted Register sections. Arrow keys resize, Shift makes smaller changes,
and Home/double-click restores a column. Pointer cancellation restores the prior
width; rows retain their navigation behavior and the table scrolls horizontally.

The outgoing-page loading replacement is removed. Navigation marks its link
without changing the current title, agent frame, content, scroll or draft. Native
document navigation, authentication, cancellation and Back remain browser-owned.
The delayed-navigation test retains the eight-second cancel recovery.

Artefacts and Capabilities now serve lightweight destination frames first. Heading,
actions and tabs are identical before and after loading; only the inventory region
changes. Cold content uses an authenticated request and ordered first-party scripts.
Warm navigation includes the cached body directly, avoiding another loading phase.
The new Artefacts content endpoint is covered by the normal authentication and
realm-binding checks. The existing capabilities loader is replaced by a shared one.

The process-local cache lasts 30 seconds from rendering, has eight-entry and total
size bounds, and is keyed by canonical realm path plus page. App POSTs invalidate
it before and after dispatch, fencing in-flight renders; reload/Refresh bypasses
it. External edits can remain visible as the earlier snapshot for up to 30 seconds.
Nothing is persisted to a realm, and cached markup never authorizes a mutation.

Focused verification passed **427 tests**, including the reviewed golden pages
and generated references. Native page/loading checks cover populated content,
correct destination frames from a thread, unchanged heading/action/tab geometry,
warm revisits without inventory requests, refresh, failures/retry and Register
resizing/persistence in narrow enlarged-text dark mode. The bounded visual review
found a clipped-header issue and corrected it; the confirmation pass passed. The
design detector reported no findings in the changed targets. The existing Overview
subscription header can overlap at 900 px with enlarged text; it is outside this
change and no Overview header styling was changed.

The navigation probe's loaded-event injector raced rapid document replacement;
the test bridge is now embedded in its synthetic documents. Product startup code
is unchanged. The final native navigation journey passed seven checks with
2.5 ms link feedback while the destination response was held, without test-bridge
errors. Full release results follow below.

In the small synthetic route fixture, a warm Artefacts request took 17.16 ms
(previously 23.69 ms) and Capabilities 18.28 ms (previously 39.11 ms). These are
single server-side observations, not a user latency guarantee. The stronger
acceptance evidence is the native revisit check: no inventory request and no
loading placeholder on either warm page. Native click-to-content observations
were 101 ms and 225 ms respectively. Both destinations had zero measured heading,
action and tab geometry shift while their content arrived.

Provider metadata review confirmed the preferred defaults remain available.
The bundled runtime remains Python 3.14.10, verified against the official Python
release listing on 17 November 2026 during the preceding release; no runtime or
provider defaults changed. This continues the established unsigned maintenance
beta: Ed25519 update signing remains mandatory; Windows publisher signing and
clean Sandbox acceptance remain outside the verified boundary. The owner's
running app was not restarted to publish.

The full isolated local suite passed **4,839 tests with 6 skips** in
**925.49 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/44099976996) passed
both Python jobs and relay checks. The final-source stabilization gate passed
its fault matrix, 30-round concurrent soak, history performance budgets, three
native shared-thread runs, page-work and owner workflows. Its unique evidence
directory is `build/stabilization-20261117-150919-699812`.

Packaged launcher recovery, DLL isolation, session, tray, three restart cases and
presentation recovery passed. The staged runtime passed **124
owner-workflow checks**, **30 page/loading checks** and
**7 navigation checks**. The signed previous-release upgrade
rehearsal passed **72 checks**. Packaged main and
companion recovery screenshots were reviewed in light and dark modes.

Golden review covered every changed snapshot. The Artefacts inventory markup
and scripts moved verbatim to the new content snapshot. Capability controls
moved into the stable document header. Other changes are Register column markup,
identical agent-artefact padding, help text and the new release note.

Public verification checked the Ed25519 signature, exact source commit, all
**515 tracked package files**, installer hash and
website links. Installer: **23,519,101 bytes**, SHA-256
`080b9a097cde868cca5106d1806e0ca58672fc14fc9233ddfa645c9784e9ec61`.
Package SHA-256: `ded9083247bc09918738de1d046e0da24e4081fe6fb61e995e57d408dd9961d9`.

Evidence: `build/release-evidence-0.99.159.json`,
`build/public-verification-0.99.159.json`, `build/website-0.99.159-publication.json`,
`build/stabilization-0.99.159.json`, `build/owner-staged-0.99.159.json`,
`build/loading-staged-0.99.159.json`, `build/navigation-staged-0.99.159.json`,
`build/page-loading-159-final.json`, `build/navigation-159-final.json`,
`build/page-loading-159-before.json`, `build/page-loading-159-after.json`,
`build/golden-review-159.diff`, `build/design-159.json`,
`build/release-defaults-0.99.159.json` and `build/publish-0.99.159.log`.
