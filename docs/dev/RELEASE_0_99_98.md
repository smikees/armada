# 0.99.98 verification

This maintenance release fixes misleading connector sign-in feedback and empty configuration
copy controls introduced with the provider connection UI in 0.99.97.

## Diagnosis and validation

- The installed Codex CLI returned `Dynamic client registration not supported` for Google Drive
  before opening a browser. ARMADA previously discarded stdout/stderr and treated process
  launch as sign-in. Google Drive requires a pre-registered OAuth client specific to Codex.
- The Codex setup response had an empty snippet. Shared button styling overrode the copy
  button's `hidden` attribute, leaving a visible action that copied empty text.
- Connector sign-in is now bounded and observed through the existing owned process supervisor.
  Failures remain visible; an Open sign-in page action appears only for an issued HTTPS OAuth
  URL. Completed sign-in still requires a live connection check.
- Codex setup returns valid TOML, with an explicit placeholder Google OAuth client ID when
  required. Clipboard fallback, exact copy feedback and empty-text protection cover WebView
  hosts where the browser Clipboard API is unavailable.
- Focused connector, Claude failure, process lifetime and capabilities regressions passed.
  A browser fixture verified exact clipboard readback for both normal and fallback paths,
  empty copy control visibility and a 430 px layout without horizontal overflow or console errors.
- An actual Codex CLI invocation against an isolated loopback OAuth fixture confirmed that
  its authorization URL is emitted on stdout. No real connector authorization was changed,
  no browser consent was completed and no live job ran.
- Installed provider metadata confirmed all release-default model preferences (14 Claude,
  7 Codex and 4 Gemini entries). Existing provider/model choices remain unchanged.
- The first full gate caught the repository's broad-exception logging guard. The login worker
  now logs only an unexpected exception's class, preserving the sanitized UI reason without
  logging OAuth credentials. The corrected source is revalidated before publication.

See [technical details](CONNECTOR_PROVIDER_CONNECTIONS.md) and the linked official provider
and Google setup references. The enforced publisher completed the isolated full suite,
exact-source Windows CI, staged native session and signed-asset packaged upgrade gates before
publication. The evidence below records the corrected source that passed those checks.

This continues the standing owner-authorized unsigned Windows beta distribution. The installer
remains unsigned; update manifests are Ed25519-signed. Runtime, bootstrap compatibility,
existing realm grants and model defaults are unchanged. The owner's app is not restarted.

## Publication evidence

Published [v0.99.98](https://github.com/smikees/armada/releases/tag/v0.99.98) on
9 October 2026 from source commit `43eed8879c28964db7add60d6f26a14005f9c3f5`.

- The final isolated gate passed **3,505 tests with 5 expected skips** in 488.97 seconds.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/37957633753)
  passed Python 3.12.10, current Python 3.12 and the offline PHP relay checks.
- Installer staging passed all **5 native recovery interruption points** and **16 WebView2
  multi-window session checks**.
- The exact signed-asset packaged upgrade passed **63 real-page, restart and cleanup checks**.
- All four assets were freshly downloaded from the public release. ARMADA's verifier accepted
  the update manifest signature and its version, commit, ZIP size and ZIP hash. All **336**
  packaged source files matched the reviewed source. The installer download matched the build.
- GitHub reports this as the latest normal release, neither draft nor prerelease.

Public SHA-256 values:

| Asset | SHA-256 |
| --- | --- |
| ARMADA-Setup-0.99.98.exe | `638379002290a478c8bfe9f1b8ae58ead41f50978b2b513afb4bb7fb1930d101` |
| armada-0.99.98.zip | `2c384cf884ccf6b0c4341c3d82b944659a525d64a238daa4b812ae39a9d1adc5` |
| armada-update.json | `09a778fc0fe02ae3ea7e1871f1f6713698cb8d43dfa35840ecb759d6c9dea254` |
| armada-update.json.sig | `c628a7d11f7c2219cf556bf9465a52d4985bbaf1ca1a49aade5d808b6d62a56c` |

Compatible installations can use Settings → Check for updates → Restart to update.
The owner's running application was not restarted or otherwise modified.
