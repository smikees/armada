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

The enforced publication command validated the exact committed source with the full isolated
suite, successful Windows CI, staged native launcher/session checks and signed-asset packaged
upgrade checks. The original repository review also completed successfully after Claude’s reset;
no capability was added or installed.

This continues the standing owner-authorized unsigned Windows beta maintenance distribution.
The installer remains unsigned; update manifests use Ed25519 signatures. Runtime and bootstrap
compatibility are unchanged. Trusted publisher signing and clean Windows Sandbox GUI acceptance
remain open. Publishing does not restart the owner's running app.

## Publication evidence

Published [v0.99.97](https://github.com/smikees/armada/releases/tag/v0.99.97) on
9 October 2026 from source commit `5ecc448b6fa77a44b8dc561417527ab88ddad04f`.

- The final isolated gate passed **3,485 tests with 5 expected skips** in 511.56 seconds.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/37951059537)
  passed both Python 3.12.10 and current Python 3.12, plus the offline PHP relay checks.
- Installer staging passed all **5 native recovery interruption points** and **16 WebView2
  multi-window session checks**.
- The exact signed-asset packaged upgrade passed **63 real-page, restart and cleanup checks**.
- All four assets were freshly downloaded from the public release. ARMADA's own verifier
  accepted the manifest signature; its version, commit, ZIP size and ZIP hash matched.
  The installer download matched the locally verified build.
- GitHub reports this as the latest normal release, neither draft nor prerelease.

Public SHA-256 values:

| Asset | SHA-256 |
| --- | --- |
| ARMADA-Setup-0.99.97.exe | `27a653f28ddb02e1eaea89bb0962b5131951c9d6921ed5361d744875429d683a` |
| armada-0.99.97.zip | `3ab886533ab00698c760e356bb4a59508b070203d846691bfa29cddf180d75c9` |
| armada-update.json | `f79a43d032d71fe9dc540649dae393098397e6d6d1a8dcb489ab30256a0a9ff8` |
| armada-update.json.sig | `dbad32e57464bd128a0b808f888c37afa0e0a3df463ddc9712ca60eb293274c3` |

The owner's running application was not restarted. Compatible installations can use Settings →
Check for updates → Restart to update. Signing limitations above remain unchanged.
