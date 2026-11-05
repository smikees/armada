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

Pending full pinned gate, exact-source Windows CI, packaged native and signed
upgrade checks, exact-installer Sandbox rehearsal and public asset/website checks.
Focused installer/runtime/update tests and the native child probe passed. The
Sandbox script now reproduces a locked existing CRT and verifies refusal preserves
both it and its marker before testing normal installation.

The existing unsigned-maintenance distribution remains in force. ARMADA publisher
signing and clean-machine WebView2 GUI acceptance are not claimed; record the
actual exact-installer rehearsal result here before completing release evidence.

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
