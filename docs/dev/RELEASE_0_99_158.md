# v0.99.158 — compact job proposals and readable cadence

Prepared on 17 November 2026. Final release gates and publication are pending.

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
106 tests. The native proposal journey passed 14 checks and the existing native
readiness/approval journey passed 19 checks. The final batched visual review
covered Armada II light mode, collapsed and expanded rows, and narrow dark mode
with enlarged text. The mechanical design scan found only existing, unchanged
rules elsewhere in the shared stylesheet; no finding belongs to this change.

This is a presentation-only release. It does not change admission, persistence,
history reads or desktop lifecycle, so the extended stabilization gate is outside
its required scope. Full isolated tests, exact-source CI, packaged native gates,
signed upgrade and staged owner/proposal journeys remain mandatory.

Provider metadata review confirmed all preferred defaults are available. The
packaged runtime remains Python 3.14.10, checked against the
[official Python release listing](https://www.python.org/doc/versions/).
This continues the established unsigned maintenance beta: Ed25519 update signing
is required; Windows publisher signing and clean Sandbox acceptance remain
outside the verified boundary. The owner's running app is not restarted to publish.
