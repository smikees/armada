# v0.99.160 — prompt inventory navigation and loading spinners

Published on 17 November 2026 from `c40c4eacd6abe9f4c0bb60c8f965eee52d7f8a4e`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.160) and
[website](https://armada.stamih.com/) offer the matching installer.

The previous inventory cache did not remove the work performed by the shared
navigation. Its waiting-work badge called `inbox.all_messages`, which read every
completed message before discarding the archive. A synthetic realm with 3,000
completed messages reproduced a 2,517.54 ms document render with cached inventory;
2,499 ms was spent in that full inbox scan. The new `count_waiting` reads only
pending and running messages, preserving the existing treatment of malformed and
empty records. The same profile measured 25.57 ms for the document after the fix.
Counts stay live; no new cache or data migration is introduced.

The navigation controller now applies the destination's complete active state,
clearing the old selection in the same menu. Cancellation restores the previous
selection. A compact status at the lower left includes a shared spinner, avoiding
the sign-in notice on the right. Native document navigation, authentication,
history, fields, scroll and draft persistence remain browser-owned. Artefacts,
Capabilities and the initial catalogue loading message use the shared spinner,
which is available before inventory scripts/styles arrive and respects reduced
motion. Headings and controls retain their prior geometry.

Native page checks now seed 3,000 archived messages and enforce a 750 ms ceiling
for destination frames and warm revisits. Observed initial results: Artefacts
121 ms cold / 105 ms warm; Capabilities 134 ms cold / 248 ms warm. Warm visits
make no inventory request. These are isolated observations on this machine, not
a guarantee for every realm or device. Content gathering on a cold visit can
still take longer; it happens after the destination frame is visible.

Focused tests passed. The final native navigation journey passed eight checks;
the page-loading journey passed 32 checks. Light/wide and dark/narrow loading
captures were reviewed, including the corrected lower-left status placement.
The design detector returned no findings. Golden review covered all four changed
pages: shared spinners, help search text and the release note.

Focused tests cover waiting-count parity, malformed records, live count changes,
archive exclusion, cache boundaries and navigation guards. Native checks cover
spinners, selection, cancellation, rapid menu changes, Back, unsent drafts,
unchanged heading/action/tab geometry, cached revisits, refresh and error recovery.
The 30-second presentation cache and its invalidation policy are unchanged.

Provider metadata review confirms the preferred defaults remain available. The
bundled Python remains 3.14.10, verified against the official release listing on
17 November 2026 during the preceding release; neither runtime nor provider
defaults changed. This follows the established unsigned maintenance beta:
Ed25519 update signing is mandatory; Windows publisher signing and clean Sandbox
acceptance remain outside the verified boundary. Publication does not restart
the owner's running app.

Evidence: `build/navigation-baseline-160.json`, `build/navigation-after-160.json`,
`build/page-loading-160.json`, `build/navigation-160.json`,
`build/release-defaults-0.99.160.json`. Final release results follow below.


The full isolated local suite passed **4,843 tests with 6 skips** in
**872.84 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/44128525361) passed
both Python jobs and relay checks. The final-source stabilization gate passed
its fault matrix, 30-round concurrent soak, history performance budgets, three
native shared-thread runs, page-work and owner workflows. Its unique evidence
directory is `build/stabilization-20261117-174108-399419`.

Packaged launcher recovery, DLL isolation, session, tray, three restart cases and
presentation recovery passed. The staged runtime passed **124
owner-workflow checks**, **32 page/loading checks** and
**8 navigation checks**. The signed previous-release upgrade
rehearsal passed **72 checks**. Packaged warm visits
with 3,000 archived messages measured **105.95 ms**
for Artefacts and **215.13 ms** for Capabilities. Packaged main and
companion recovery screenshots were reviewed in light and dark modes.

Public verification checked the Ed25519 signature, exact source commit, all
**515 tracked package files**, installer hash and
website links. Installer: **23,516,671 bytes**, SHA-256
`f24a2bafed911c876276d639f4ebcfb02939a3ac3ad8523c14c979df958c1f98`.
Package SHA-256: `a551fb9d14829f1fcbddd60f4a1a5791d6f79f521177ab3709663ac5cbd2297d`.

Evidence: `build/release-evidence-0.99.160.json`,
`build/public-verification-0.99.160.json`, `build/website-0.99.160-publication.json`,
`build/stabilization-0.99.160.json`, `build/owner-staged-0.99.160.json`,
`build/loading-staged-0.99.160.json`, `build/navigation-staged-0.99.160.json`,
`build/page-loading-160.json`, `build/navigation-160-final.json`,
`build/navigation-baseline-160.json`, `build/navigation-after-160.json`,
`build/golden-review-160.diff`, `build/design-160.json`,
`build/release-defaults-0.99.160.json` and `build/publish-0.99.160.log`.
