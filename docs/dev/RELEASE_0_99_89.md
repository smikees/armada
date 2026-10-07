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
- Final regression, exact-source CI and packaged upgrade results are recorded after publication.

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

Pending the enforced release gate. Evidence will be retained under build/verification-0.99.89/,
build/publish-0.99.89.log, build/release-evidence-0.99.89.json and build/upgrade-0.99.89.json.
