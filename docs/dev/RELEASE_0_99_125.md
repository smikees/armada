# 0.99.125 — Prevent locked and incomplete runtime upgrades

Installer correction before M4 of the stabilization plan. A browser helper was
observed loading ARMADA's private CRT; the full installer could not replace it.
Skipping left an older DLL beside the new Python, despite a current install marker.

The launcher clears inherited DLL search state and uses process-local directories.
Native child probes reproduce the old inheritance and verify the new host from
both clean and legacy parents. Setup checks for locked or inaccessible files
before deleting/replacing anything and asks the owner to quit applications first.
It no longer force-stops ARMADA during upgrade. Uninstall behavior is unchanged.

Setup also verifies the copied payload against hashes embedded in the installer
before copying the compatibility marker. Missing, different or skipped files
cannot produce a successful setup. This is not a transactional whole-directory
installer: failures after copying begins can still require rerunning Setup.
Automatic Setup logs preserve diagnostic evidence.

Launcher protocol 2 is part of the runtime tag. **0.99.124 and earlier require the
full installer**, since package updates do not replace the native host. Python
3.14.10 and dependency pins are unchanged. The previously authorized local owner
repair is separate; this release does not restart the owner's app.

## Validation and publication

Published on GitHub and armada.stamih.com from
`19100202f724c1e7f93e96f3b6efce928170bca6` on 5 November 2026.

- Mandatory pinned local suite: **4,010 passed, six skipped**.
- Exact-source Windows CI [42065618407](https://github.com/smikees/armada/actions/runs/42065618407):
  **4,012 passed, four skipped** on each of Python 3.14 and 3.14.10; relay passed.
- Packaged native gates: five launcher recovery checks; clean/legacy parent DLL
  isolation; 16 WebView2 session checks; 68 tray checks; 69 checks in each visible,
  tray and busy restart case; **74 signed upgrade checks**.
- Exact released installer Sandbox rehearsal: **26 passed; one prerequisite failure**.
  Locked CRT refusal returned exit 7 and preserved the DLL/marker. Normal installation
  verified all payload hashes before the marker. Imports, timezone, missing-WebView2
  recovery, uninstall, user-data preservation and reinstall passed.
- Both WebView2 prerequisite installers returned `-2147219198` in Sandbox.
  Clean-machine GUI acceptance remains unverified. This is a recorded maintenance
  distribution exception, not a full clean-machine pass.
- Public manifest signature, package size/hash/source bytes, installer hash and
  HTTPS website version/release/download links verified. Owner app was not restarted.

Installer SHA-256:
`f54bbb7597af644fa58298936b3dc8907d8918a32bc6c804a62b16248540c699`

Package SHA-256:
`1761eb61f0f51314e520d4445ac98232fa6bbc440c8bddf75087f99c1f21b81b`

Runtime tag: `py3.14.10-7bc0018406bbe195`. Local ignored evidence includes
`build/release-evidence-0.99.125.json`, `build/sandbox-runs/20261105-175513/`,
`build/public-0.99.125/verification.json` and the publisher/website logs.
The earlier candidate rehearsal also had 26 passes and the same prerequisite
failure; only the final rehearsal above identifies the public installer bytes.

The installer remains without ARMADA publisher signing; update manifests are
Ed25519-signed. Publisher signing and maintainer acceptance remain pending.
CI's existing Python 3.14 warning in `voice_turns.py` is tracked for M8 cleanup.

## References reviewed 5 November 2026

DLL search inheritance and process-local loading:
[Microsoft DLL search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order).
Pre-install refusal and installation ordering:
[Inno Setup events](https://jrsoftware.org/ishelp/topic_scriptevents.htm),
[installation order](https://jrsoftware.org/ishelp/topic_installorder.htm).

Provider preferences are unchanged after reviewing official
[Claude](https://platform.claude.com/docs/en/models/opus-5-5/overview),
[Codex](https://developers.openai.com/api/docs/models/gpt-6.1-sol), and
[Gemini](https://aistudio.google.com/docs/models/gemini-3.8-flash) metadata.
Actual selection continues to use the connected provider's catalogue.
