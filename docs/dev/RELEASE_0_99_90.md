# ARMADA 0.99.90 verification

This release applies the owner’s second detached-window polish pass.

## Scope

- The native shadow uses a Gaussian alpha falloff fitted to the supplied Windows reference.
  It extends farther below and beside the frame, without a hard outer cutoff.
- The shadow mask follows the same silhouette as the native frame. Removing the expanded
  clear mask and CSS border eliminates the bright gap at the window edge.
- The avatar protrudes 16px above the header instead of 32px, preserving its size while freeing
  vertical space for the conversation. Only detached-thread geometry changes.
- The avatar and header have subtle shadows; the header uses the Overview header’s elevation
  values. The activity dot is 14px instead of 19px. Close has equal top and right insets.
- Corner resizing, text-only messages, shared-thread controls and the regular Detach thread
  icon remain in place. The shadow remains click-through and never takes focus.

No runtime dependency, storage schema or bootstrap protocol changed. Publishing stages a
compatible signed update without restarting the running desktop.

## Verification

- Focused thread-window and desktop lifecycle tests: **24 passed**.
- Actual hidden WebView2 thread-window probe: **43 checks passed**, including shadow
  falloff against the reference, absence of a clear seam, frame/header geometry, native
  resizing, close/reopen, shadow cleanup and shared conversation behavior.
- Normal and narrow layouts were reviewed in light and dark mode. A composite using the
  actual native shadow bitmap, form region and captured WebView pixels was reviewed on the
  reference’s plain orange background. This verifies the rendered layers without moving
  or covering the owner’s windows.
- Existing mechanical design-scan findings are outside the changed rules.
- Native startup/recovery: **8 checks passed**, including Settings recovery and clean close.
- Final regression, exact-source CI and packaged upgrade results are recorded after publication.

The probe uses synthetic realms and deterministic replies. The owner’s screenshots and
personal conversation data are not included in the repository or release.

## Provider and runtime review — 2026-10-07

The same-day [0.99.88 review](RELEASE_0_99_88.md#provider-and-runtime-review--2026-10-07)
was checked against the unchanged provider preferences and runtime. Connected-account
catalogue filtering and provider-default fallback remain in place. Embedded Python remains
3.12.10; this maintenance package does not include later source-only 3.12 security fixes.

## Distribution boundaries

Publication follows the existing owner-authorized maintenance beta path. Update manifests
are Ed25519-signed. Windows publisher signing and clean-Sandbox installer acceptance remain
open; the unsigned installer may be blocked by Application Control (error 4551).
The packaged native upgrade gate and recoverable update journal remain mandatory.

## Publication

Pending the enforced release gate. Evidence will be retained under build/verification-0.99.90/,
build/publish-0.99.90.log, build/release-evidence-0.99.90.json and build/upgrade-0.99.90.json.
