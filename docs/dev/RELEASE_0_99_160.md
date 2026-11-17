# v0.99.160 — prompt inventory navigation and loading spinners

Prepared on 17 November 2026. Publication awaits the final-source release gates.

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
`build/release-defaults-0.99.160.json`. Final release results follow after the gates.
