# v0.99.157 — shared code and obsolete-path removal

Prepared on 16 November 2026. Publication and final release gates are pending.
See the [ordered plan](SIMPLIFICATION_2026_11.md).

Removed nine unused UI helpers, their private model seed list, the unused
fail-fast connector checker and unreachable duplicate queued-turn creation.
The active connector withholding and post-wait authorization paths remain.
Memory and realm readers now share their existing flat metadata parser;
custom sections share a document wrapper; Claude JSON and streaming execution
share tool-mode selection with unchanged precedence and arguments.
Page dependencies are explicit, with package compatibility exports retained.
Add-on documentation now describes the active dashboard and Alexander consumers.

The one intended behavior correction is the static cockpit provider label:
it follows the realm default model and identifies itself as the realm default.
No saved configuration, agent model or job model is migrated.

Before the version bump, all 21 desktop golden pages passed unchanged.
A before/after comparison of 26 custom-section renders was byte-identical,
covering light/dark mode, local files, live URLs, snapshots, app assets,
overlapping precedence, widgets and missing sections. Focused and final release
checks passed 406 tests with 5 intentional skips. Generated reference checks
passed 371 tests; regolding intentionally wrote/skipped 21 snapshots. Review
found only the new Settings changelog entry, with no removed or changed HTML.
Final release results will be recorded after completion.

Live Claude/Gemini metadata and the local Codex catalogue confirm each provider's
preferred default is available. Gemini's secondary seed was not present in the
connected account's returned list; connected-provider filtering and the provider
default escape hatch remain unchanged. No model work was launched for this review.

This continues the established owner-authorized maintenance beta procedure:
Ed25519 update signing is required; Windows publisher signing and clean Sandbox
acceptance remain outside the validated boundary. The owner app is not restarted
as part of publishing.
