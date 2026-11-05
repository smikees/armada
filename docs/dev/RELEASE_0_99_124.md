# 0.99.124 — Maintain the bundled Windows runtime

M3 of the [stabilization plan](STABILIZATION_PLAN_2026_11.md). The candidate uses
Python 3.14.10 and updated upstream security libraries. Runtime definition,
launcher DLL, path configuration, wheel ABI and signed update requirement share
one source. Tags include the Python patch so later security refreshes cannot
silently leave the old interpreter in place.

**Upgrading from 0.99.123 or earlier requires the full installer.** Let active
work finish, quit ARMADA, then run the installer. Realms and settings remain in
their existing folders. Compatible updates work normally after installing the
new runtime. This release changes no provider adapter or model preference.

The installer carries a verified upstream component inventory and a generated
inventory of the actual staged libraries and packages. The release probe checks
that the previous signed client refuses the new runtime before downloading code,
then rehearses the compatible update after the new runtime is present.

## Validation

- Official runtime archive hash, upstream inventory and Python Software Foundation
  signatures verified; nine pinned package metadata advisory checks completed.
- Python.NET/WebView2 imports and compiled launcher/native tray preflight passed
  on Python 3.14.10; the native preflight covered 68 lifecycle checks.
- Focused runtime/update/build/visibility suites passed; final pinned gate,
  exact-source CI, packaged boundary/upgrade and Sandbox evidence pending.
- Synthetic profiles only. No owner app restart, installation or live provider job.

See [runtime security](RUNTIME_SECURITY.md) for provenance, upgrade semantics,
test coverage and the remaining full-installer handover limitation. The existing
unsigned Windows beta and clean-machine acceptance limits remain explicit.
Implementation verification does not imply maintainer acceptance.

## Provider metadata review

The November 5 review remains applicable; defaults are unchanged and actual
selection still uses the connected provider's catalogue. Official references:
[Claude](https://platform.claude.com/docs/en/models/opus-5-5/overview),
[Codex](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Gemini](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

## Publication

Pending. Record exact source/CI, package and installer hashes, native/runtime
boundary evidence, Sandbox outcome and public website/download verification.
