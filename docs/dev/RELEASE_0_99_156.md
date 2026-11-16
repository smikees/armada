# v0.99.156 — explain skipped calendar checks

Prepared on 16 November 2026. Publication checks are pending.

Skipped system checks were passed through by the calendar API but had no palette
entry. Week/month chips therefore used the saturated scheduled accent as a solid
background, with no matching legend item. They now use a light grey tint, with
matching light/dark ink, a dedicated day-view dot and an explicit Skipped legend
where system occurrences can appear. The legend explains that no work was done.
Unrecognised chip states fall back to a quiet neutral instead of the accent.

Telegram polling checks intentionally skip while the background listener is
already receiving and answering messages, preventing two pollers from competing
for Telegram updates. This changes presentation; system-job execution and
skip decisions retain their existing behaviour.

Existing calendar/theme/health and reviewed golden-page checks passed 84 tests.
Production calendar previews passed 48 browser checks covering all three views,
neutral grey styling, matching legend
colours, readable text contrast and desktop/narrow light/dark layouts.
Skipped text contrast is 6.08:1 in light mode and 8.69:1 in dark mode.
The required System jobs layout probe passes 57 checks, including scaled dark
mode and horizontal scrolling. The scoped mechanical design scan reports no
findings. Golden review proves Jobs and Overview change only the Skipped
legend/style additions; Settings and help change only the release note and
the skipped-check explanation.

Full local gate, exact-source CI, native installer/upgrade checks, packaged owner
workflows and public download verification remain pending. This presentation-only
change does not alter admission, persistence, history reads or desktop lifecycle;
the separate clean-source stabilization gate is outside its required scope.

This continues the owner-authorized maintenance beta. Update assets use Ed25519
signatures; Windows publisher signing and clean Sandbox acceptance remain
unverified. Publication does not restart the owner's running app.
