# v0.99.158 — compact job proposals and readable cadence

Published on 17 November 2026 from `9d99109f48dd6d2a79f43244af1f31a7a139e6a8`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.158) and
[website](https://armada.stamih.com/) offer the matching installer.

Proposed jobs now start as compact, collapsed disclosure rows. Expanding a row
shows each changed field above two equal-width values, with 12 px body text,
safe Markdown formatting, preserved line breaks and inline deletion/insertion
marks. The repeated prompt preview and one-third-width Field column are removed.
Long values scroll within a bounded comparison. Narrow containers stack the
values; keyboard users can focus and scroll the comparison. Run settings and
retained access have separate disclosures. New proposals retain their complete
prompt rather than a 600-character excerpt.

Diffing preserves the full reviewed values and escapes untrusted content.
Formatting-only and hidden link-destination changes fall back to source display;
otherwise unchanged text is left unmarked. Large repetitive edits have bounded
comparison work. The review token, approval/rejection APIs, tool-choice warnings,
saved-job isolation and approval sealing are unchanged.

Job cadence now describes the scheduler's expanded fields, including minute/hour
steps, lists, named weekdays/months, nth weekdays and day-of-month/day-of-week OR
semantics. `*/15 15-16 * * 1-5` becomes `weekdays every 15 min, 15:00–16:45`.
Invalid schedules say they need review. No schedule or execution logic is changed.

Focused checks passed 119 tests; the final formatting edge-case follow-up passed
106 tests. The native proposal journey passed 16 checks and the existing native
readiness/approval journey passed 19 checks. The final batched visual review
covered Armada II light mode, collapsed and expanded rows, and narrow dark mode
with enlarged text. The mechanical design scan found only existing, unchanged
rules elsewhere in the shared stylesheet; no finding belongs to this change.
The final contrast check found the inherited secondary grey below 4.5:1 on the
panel surface. It now uses the stronger shared text token; the native journey
also enforces 4.5:1 contrast in both light and dark themes.

This is a presentation-only release. It does not change admission, persistence,
history reads or desktop lifecycle, so the extended stabilization gate is outside
its required scope. Full isolated tests, exact-source CI, packaged native gates,
signed upgrade and staged owner/proposal journeys remain mandatory.

Provider metadata review confirmed all preferred defaults are available. The
packaged runtime remains Python 3.14.10, checked against the
[official Python release listing](https://www.python.org/doc/versions/).
This continues the established unsigned maintenance beta: Ed25519 update signing
is required; Windows publisher signing and clean Sandbox acceptance remain
outside the verified boundary. The owner's running app was not restarted to publish.

The mandatory isolated local suite passed **4,829 tests with 6 skips**
in **912.86 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/44086479108) passed
both Python jobs and relay validation. Generated-reference checks passed 371
tests. Golden review found only added help text and the new Settings release
entry; existing content was unchanged.

Packaged launcher recovery, DLL isolation, session, tray, three restart cases and
presentation recovery passed. The staged package passed **124
owner-workflow checks** and **16 proposal checks**, including
light/dark contrast, narrow enlarged-text layout, complete formatted comparisons,
collapsed state, bounded scrolling, readable cadence and actual approval sealing.
The signed previous-release upgrade rehearsal passed **72 checks**.
The packaged main-window and companion recovery screenshots were reviewed in
light and dark modes; text and controls were readable without clipping.

Public verification checked the Ed25519 update signature, exact source commit,
all **512 tracked package files**, the downloaded
installer hash and matching website links. Installer: **23,515,101
bytes**, SHA-256 `9d42517714d1105cd68731550e2720e34b93c1e4b09bc8b4cd98a0d8ab1823b4`.
Package SHA-256: `098e47816ec058f24085734ad31d99cdef9194082b53d652bc9bf7ee3ae1d712`.

Evidence: `build/release-evidence-0.99.158.json`,
`build/public-verification-0.99.158.json`, `build/website-0.99.158-publication.json`,
`build/owner-staged-0.99.158.json`, `build/proposal-staged-0.99.158.json`,
`build/proposal-ui-158-final.json`, `build/proposal-ui-158-contrast.json`,
`build/job-readiness-158.json`, `build/release-defaults-0.99.158.json` and
`build/publish-0.99.158.log`. The initial release run was stopped before
publication to include the measured contrast correction; only the final commit
and its complete successful gate results were used for publication.
