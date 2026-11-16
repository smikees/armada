# v0.99.156 — light grey skipped calendar checks

Published on 16 November 2026 from `2694d6a8932c56200ec2c0621fb86ebb85e76fe9`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.156) and
[website](https://armada.stamih.com/) offer the matching installer.

Skipped system checks had no calendar palette entry and inherited the saturated
scheduled accent as a solid background. They now use neutral light grey, with
matching dark-mode grey, a dedicated day-view dot and an explicit Skipped legend
where system occurrences can appear. The legend explains that no work was done.
Unrecognised chip states use a quiet neutral fallback. Day-rollup legends retain
their existing outcomes.

Telegram polling checks intentionally skip while the background listener is
already receiving and answering messages, preventing two pollers from competing
for the same updates. This release changes presentation and explanatory text;
execution, admission and skip decisions retain their existing behaviour.

The mandatory isolated local gate passed **4,752 tests with 6 skips**
in **841.02 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43881088708) passed
both required Python jobs and relay validation. Calendar/theme/health checks and
reviewed golden pages passed 84 focused tests. Golden review proves that Jobs
and Overview change only the Skipped legend/style additions; Settings and help
change only the release note and skipped-check explanation. The generated
reference records the optional legend argument. The scoped design scan is clean.

The System jobs layout probe passed **57 checks**, including
scaled dark mode and horizontal scrolling. Freshly packaged code passed
**124 owner-workflow checks** and **48 calendar browser checks**.
The calendar checks cover all three views, neutral grey fills,
matching legends, readable contrast and desktop/narrow light/dark layouts.
Skipped uses `#e8e8e8` with `#555555` text in light mode (**6.08:1**) and `#333333`
with `#d6d6d6` text in dark mode (**8.69:1**).

Mandatory packaged launcher, session, tray, restart and presentation-recovery
checks passed, as did the signed previous-release upgrade rehearsal
(**72 checks**). This presentation-only change does
not span admission, persistence, history reads or desktop lifecycle, so the
separate extended stabilization gate is outside its required scope.

Public verification checked the update signature, release commit, all
**511 tracked package files**, installer hash and
website links. Installer: **23,515,898 bytes**, SHA-256
`b1b0b61de058330c1545683a2e898dae78850a34bad30d84ab1f61b2b3987aaa`. Package SHA-256:
`2ac63e9cbda8d26efd74ac36209df8c0ae1abd5578fb4f2bd3f57143fe43294c`.

Evidence: `build/release-evidence-0.99.156.json`,
`build/public-verification-0.99.156.json`, `build/website-0.99.156-publication.json`,
`build/owner-staged-0.99.156.json`, `build/calendar-staged-0.99.156.json`,
`build/skipped-system-layout-grey.json`, `build/calendar-skipped-preview/checks.json`
and `build/release-defaults-0.99.156.json`.

Provider catalogue metadata was reviewed on 16 November without model work;
each provider's preferred default remains available. The packaged runtime
continues to use Python 3.14.10, the current patch in the 3.14 line
([official releases](https://www.python.org/downloads/)).
This continues the owner-authorized maintenance beta: update assets are
Ed25519-signed; Windows publisher signing and clean Sandbox acceptance remain
unverified. The owner's running app was not restarted to publish.
