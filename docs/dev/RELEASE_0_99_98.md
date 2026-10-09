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
and Google setup references. The enforced publisher must complete the isolated full suite,
exact-source Windows CI, staged native session and signed-asset packaged upgrade gates before
publication. Publication evidence will be recorded below after those checks pass.

This continues the standing owner-authorized unsigned Windows beta distribution. The installer
remains unsigned; update manifests are Ed25519-signed. Runtime, bootstrap compatibility,
existing realm grants and model defaults are unchanged. The owner's app is not restarted.
