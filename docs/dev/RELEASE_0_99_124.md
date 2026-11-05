# 0.99.124 — Maintain the bundled Windows runtime

M3 of the [stabilization plan](STABILIZATION_PLAN_2026_11.md). The release uses
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
- Expanded runtime/update/build/release/signing/reference checks: 363 passed.
- The isolated build host exposed script-directory-dependent release imports.
  Explicit repository-package imports fixed them; 42 focused checks then passed.
- Final pinned publisher gate: **4,001 passed, 6 skipped** in 636.15 seconds.
- Exact-source Windows CI: **4,003 passed, 4 skipped** on both Python 3.14.10
  and current 3.14. The PHP relay passed 23 assertions without network access.
- Each full suite reported one Python 3.14 `SyntaxWarning` for the pre-existing
  voice-queue `return` inside `finally`. Its exception-preservation cleanup is
  tracked under M8; it is not hidden by a warning filter.
- Final packaged launcher recovery passed five interruption points, WebView2
  sessions 16 checks, tray lifecycle 68, and each visible/tray/busy restart 69.
- Signed 0.99.123 to 0.99.124 boundary/compatible-upgrade rehearsal: 74 checks
  passed. The old tag requires an installer before any code download, preserving
  installed code and synthetic pending work; the compatible native update then
  passes under the new runtime.
- Additional preflight ran actual Python 3.12.10 with the previous signed client
  and candidate `d95201a`. It also refused without downloading/staging code or
  changing synthetic work. The final application payload is identical; `e3bd5f2`
  changes only release-helper imports and their tests.
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

## Clean-machine rehearsal and remaining limits

Windows Sandbox on Windows 11 Enterprise 10.0.26100 rehearsed the exact published
installer hash below. The report completed with **23 passed checks and one failure**:
WebView2 was absent after both Microsoft's standalone installer and elevated
bootstrapper returned `-2147219198`. Clean-machine GUI acceptance is therefore
**not passed** under the existing maintenance exception.

ARMADA installation, bundled Python/ARMADA/WebView imports, timezone data, shortcuts,
uninstall, synthetic user-data preservation and reinstall passed. Without WebView2,
ARMADA showed its actionable startup error and left no background server running.
The report, dependency logs, screenshot and hash-bound evidence are retained under
`build/sandbox-runs/20261105-164107`. An earlier candidate rehearsal reproduced the
same prerequisite failure; its different installer hash is not used as final evidence.

The compiled runtime worked with installed WebView2 in the mandatory native gates
on the development host. Those results do not substitute for clean-PC acceptance.
The full installer still force-stops processes in its chosen install directory;
finish active work and quit ARMADA first. Cooperative full-installer handover and
trusted ARMADA publisher signing remain separate work.

## Publication

Published 5 November 2026 through the mandatory maintenance publisher under the
continuing stabilization/release authorization and existing unsigned beta procedure.

- [Release v0.99.124](https://github.com/smikees/armada/releases/tag/v0.99.124)
  targets `e3bd5f23b43c1d5d04e29fbfc1500c70c2e1f073`.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/42053916350)
  passed both Python jobs and the relay job. The slower pinned job completed
  successfully; the publisher waited for it before building/uploading.
- All four public assets verified: Ed25519 manifest signature, package size/hash,
  changed source module bytes and final installer hash.
- [armada.stamih.com](https://armada.stamih.com/) returns HTTPS 200 with matching
  version, release and installer links. FTPS deployment backed up replaced files,
  verified uploaded hashes and replaced the entry page last.
- Local evidence: `build/release-evidence-0.99.124.json`,
  `build/upgrade-0.99.124.json`, `build/runtime-boundary-old-python-0.99.124.json`,
  and `build/public-0.99.124/verification.json`.

| Artifact | SHA-256 |
|---|---|
| Published installer | `071545eeb0290ae57a42f31fc6e2f56a4cd654a243d01471f2bf8af699e31d1c` |
| Signed-manifest package | `0c2504a611d1a03ca0a8b47e82a4252b52514768f220388c29ef1d5153bacb0c` |

Windows publisher signing and clean-machine GUI acceptance remain unverified;
update-manifest signing is a separate guarantee. Maintainer acceptance is pending.
The owner installation was neither updated nor restarted.
