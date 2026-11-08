# 0.99.133 — Clearer owner workflows

M11 released from `28b625e5e2b159d92e5c99709d76ff522eda7d74` on 8 November 2026. Maintainer acceptance remains pending.

Permission previews, accurate grant wording, responsive navigation/dashboard,
actionable Attention summary, keyboard-safe shared dialogs and visible serialized
layout saves. [Behavior, ownership and limitations](OWNER_WORKFLOWS.md).

The first combined focused batch passed 118 tests; the expanded compiler/adapter
batch passed 132. Native checks passed six page-work, 79 shared-window/Stop and
16 owner-journey checks, including keyboard, preview, save-order and 1024px/150% zoom.
Light/dark captures were reviewed. Both local full suites passed **4,267 tests / six skipped**;
both exact-source Windows CI jobs passed **4,269 / four skipped**. Packaged launcher
recovery/DLL isolation, session16, tray68, restart69 in each mode, presentation86
and **72 signed-upgrade checks** passed. Fresh recovery captures were reviewed.
Public manifest signature, package/source bytes, installer hash and matching website
links verified. Installer SHA-256: `33d232e18aa8c6e9300ecabb0aae832ecbfd591542b797ae2f1f81bd7859bd5f`.

Model preferences were reviewed against official provider documentation on
8 November during M10 preparation; no provider selection changes are part of this
milestone. Runtime Python 3.14.10 and launcher protocol 2 remain unchanged.
Publication continues the existing unsigned Windows beta maintenance distribution
with Ed25519-signed update manifests. Publisher signing and clean-machine WebView2
acceptance remain unverified. No owner app restart or live realm/provider test.
