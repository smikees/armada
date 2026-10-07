# ARMADA 0.99.89 verification

This maintenance release applies the owner’s detached-thread refinements and the requested
Microsoft Fluent window-new-24-regular icon.

## Scope

- Detach thread moves to each thread’s three-dot menu, below Pin/Unpin.
- The compact header groups agent, realm, thread title and compaction information beside the
  portrait and color crescent. Title editing and the close control remain independent of dragging.
- Detached messages retain text attribution and controls while hiding the avatar columns.
  The main conversation retains its existing layout; both views still share saved messages.
- The corner grip enters Windows’ native bottom-right sizing loop, with minimum dimensions.
  Keyboard arrow keys on the grip resize in small increments.
- A click-through, non-activating alpha window draws a soft shadow around the shaped frame.
  It follows movement, size, visibility and DPI changes and releases its resources on close.
  A decorative failure is logged without preventing use of the conversation.

No runtime dependency, storage schema or bootstrap protocol changed. Existing compatible
installations use the signed package update. Publication does not restart the running app.

## Verification

- Focused thread-window tests: **13 passed**.
- Actual hidden WebView2 thread-window probe: **35 checks passed**, including entry into the
  real Windows sizing loop, keyboard resizing, shadow pixel alpha and cleanup, two-way messages,
  live progress and Stop, original-realm binding, close/reopen and narrow/long-label layouts.
- Normal and narrow layouts were reviewed in light and dark mode. The mechanical design scan
  reported existing shared-stylesheet findings outside the changed rules.
- Native startup/recovery probe: **8 checks passed**, including Settings recovery and clean close.
- Enforced full Windows regression suite: **3,306 passed, 5 skipped in 464.54 seconds**.
- Exact-source Windows CI passed on Python 3.12.10 and current 3.12, with the relay check:
  [run 37667201462](https://github.com/smikees/armada/actions/runs/37667201462).
- Packaged launcher recovery: **5 interruption points passed**.
- Packaged WebView2 session: **16 checks passed**.
- Signed v0.99.88 → v0.99.89 upgrade rehearsal: **63 checks passed**.

The native probe cancels its sizing loop without moving the owner’s cursor. Tests use synthetic
realms and deterministic replies; no provider is called and no live realm is changed.

## Provider and runtime review — 2026-10-07

The same-day [0.99.88 review](RELEASE_0_99_88.md#provider-and-runtime-review--2026-10-07)
was checked against the unchanged release preferences and runtime. Provider choices remain
filtered by the connected account’s catalogue, with provider-default fallback. This release
retains embedded Python 3.12.10 and does not include the later source-only 3.12 security fixes.

## Distribution boundaries

Publication uses the existing owner-authorized maintenance beta path. Update manifests are
Ed25519-signed; Windows publisher signing and clean-Sandbox installer acceptance remain open.
The installer may be blocked by Application Control (error 4551). The mandatory packaged native
upgrade gate and recoverable update journal remain in place.

## Publication

Published **2026-10-07T18:39:40Z** as the normal latest release:
[ARMADA v0.99.89](https://github.com/smikees/armada/releases/tag/v0.99.89).

- Source commit: 1fd7dba6e84f4190a0d32577cb574cb07ab23db3.
- Installer: 20,415,448 bytes; SHA-256
  35c11ce5874d236b88513e4d9a2df97b8c4082a0b2815f13b9bf2db203dab9cf.
- Update archive: 5,474,800 bytes; SHA-256
  73df5d37c0113e7bc2cc771e86a5167491a8a9a8f50fbce9b485c4025de2fdc2.
- All four public asset sizes and digests match the built files. The public latest manifest's
  Ed25519 signature and a fresh archive download were verified; updated native/UI files match
  the release source byte for byte.
- The installed v0.99.88 updater downloaded and staged v0.99.89. Desktop readiness and the
  running instance identity were preserved; no restart was requested.

Evidence is retained under build/verification-0.99.89/, build/publish-0.99.89.log,
build/release-evidence-0.99.89.json and build/upgrade-0.99.89.json.
