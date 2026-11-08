# 0.99.133 — Clearer owner workflows

M11 candidate. Publication and maintainer acceptance are pending.

Permission previews, accurate grant wording, responsive navigation/dashboard,
actionable Attention summary, keyboard-safe shared dialogs and visible serialized
layout saves. [Behavior, ownership and limitations](OWNER_WORKFLOWS.md).

The first combined focused batch passed 118 tests; the expanded compiler/adapter
batch passed 132. Native checks passed six page-work, 79 shared-window/Stop and
16 owner-journey checks, including keyboard, preview, save-order and 1024px/150% zoom.
Light/dark captures were reviewed. Full pinned tests, exact-source Windows CI,
packaged lifecycle/recovery and signed-upgrade gates remain required.

Model preferences were reviewed against official provider documentation on
8 November during M10 preparation; no provider selection changes are part of this
milestone. Runtime Python 3.14.10 and launcher protocol 2 remain unchanged.
Publication continues the existing unsigned Windows beta maintenance distribution
with Ed25519-signed update manifests. Publisher signing and clean-machine WebView2
acceptance remain unverified. No owner app restart or live realm/provider test.
