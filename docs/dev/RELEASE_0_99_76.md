# ARMADA 0.99.76 release verification

This release addresses new-team model selection, unattended Windows probes and
Gemini's missing task-folder context. Published as the next unsigned beta; 0.99.75 users can update in-app.

## Behavior

- New wizard teams choose among connected engines using the policy in
  `armada/engine/defaults.py`. Models must appear in vendor metadata; otherwise
  use that provider's default and automatic effort. Save defaults before preflight.
- Alexander's settings no longer choose team defaults. Existing/adopted realm
  choices and agent/job overrides are preserved.
- Background provider, capability, quota and Git probes use CREATE_NO_WINDOW and
  STARTF_USESHOWWINDOW/SW_HIDE. Interactive sign-in actions remain explicit.
- Gemini's isolated custom agent now gets the real task folder as absolute Windows
  context. No extra filesystem permission or global setting is added. Permission
  failures retain original diagnostics and record requested tool paths.

## Verification

- Focused provider/setup/selection tests: 145 passed before the Gemini follow-up.
- Final focused defaults/background/Gemini/catalogue checks: 73 passed.
- Native Gemini reproduction: explicit fixture folder listing and read succeeded;
  asking for the current directory without explicit context guessed `/workspace`
  and failed with the user's exact headless `read_file` denial. The same request
  after the fix listed the approved Windows fixture directory and returned DONE.
  No user realm, broker connector, scheduled job, or global CLI permission was changed.
- Real Windows child process: GetConsoleWindow returned zero with background options.
- Golden HTML review: the provider-default option, new changelog and settings help
  text account for the changes; no unrelated page-layout change.
- Final isolated default suite: 3,055 passed, five skipped (386.37 seconds).
- Exact source-commit Windows CI (Python 3.12.10 and current 3.12) and PHP relay: passed.
  https://github.com/smikees/armada/actions/runs/37208052615
- Packaged imports, server startup, timezone support and native-launcher recovery at all
  five interruption points passed. Update signature, ZIP contents, size and SHA-256 verified.
- Source commit: `188f116d36c704a93a7ab53c377044f2f491a225`.
- Installer SHA-256: `a1100592ad461f255c0e036949e0b59193d841f6c8cbe24a0af3410424f3106c`.
- Runtime remains `py3.12-abe4061a3fa70426`, compatible with 0.99.75.

## Distribution

This maintenance release continues the owner's requested no-fee unsigned-beta
distribution and request for fixes in a new version. The installer remains unsigned
by a Windows publisher; Application Control error 4551 is not fixed. Its update
manifest is Ed25519-signed, a separate guarantee. Trusted publisher signing and
clean-Sandbox GUI acceptance remain unverified; the previous WebView2 prerequisite
failure (0x80040902) remains unresolved. No general release-gate or acceptance
checkbox is changed. These limitations are retained in the release notes and website.

The standard publisher still requires signing and Sandbox acceptance. The existing
unsigned beta distribution was continued manually for this maintenance release after
isolated tests, exact-commit CI and package verification; this is recorded as a
release-specific deviation, not a successful standard-gate run.

Published assets reference the tested source commit above; the later documentation
commit records distribution without changing the packaged application. Only the
website landing page is replaced, with backup; the report relay stays unchanged.

Public latest-release downloads were retrieved and their manifest signature, version,
runtime, ZIP size/hash and installer hash verified. The live website links to 0.99.76.
