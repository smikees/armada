# 0.99.97 verification

This maintenance release adds independent connector connection controls for Claude, Codex
and Gemini, makes recorded operational job errors visible as warnings, and preserves useful
Claude refusal messages in skill reviews and conversations.

[Connector implementation](CONNECTOR_PROVIDER_CONNECTIONS.md),
[operational result behavior](JOB_RESULT_OPERATIONAL_WARNINGS.md) and
[skill review diagnosis](SKILL_REVIEW_FAILURE.md) describe the changes and boundaries.

## Validation before publication

- Connector verification passed 539 focused tests and all 20 page snapshots. Browser checks
  covered independent provider actions, inline Gemini setup, error recovery and narrow layout
  using fixture data; no real connector authorization was changed.
- Skill-review validation passed 80 related tests, including 13 new regressions. Actual sealed
  Claude invocations reproduced the quota refusal and confirmed the fixed explanation reaches
  the catalogue response. The review exposes only WebFetch and WebSearch.
- Installed provider metadata confirmed both release-preference candidates for each provider.
  Existing model defaults and the provider-default escape hatch remain unchanged.
- Generated API references and intentional page snapshots are reviewed before the release gate.

The enforced publication command must still validate the exact committed source with the full
isolated suite, successful Windows CI, staged native launcher/session checks and signed-asset
packaged upgrade checks. Publication evidence will be recorded after those checks succeed.

This continues the standing owner-authorized unsigned Windows beta maintenance distribution.
The installer remains unsigned; update manifests use Ed25519 signatures. Runtime and bootstrap
compatibility are unchanged. Trusted publisher signing and clean Windows Sandbox GUI acceptance
remain open. Publishing does not restart the owner's running app.
