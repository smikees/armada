# 0.99.102 verification

Settings appearance and version-row refinements. This release is prepared from the published
0.99.101 source in an isolated checkout; unrelated capability-search work remains unshipped.

## Behavior

- Font-family choices preview immediately in the sample without saving. Both menus use the
  same body-calibrated font aliases at 14 px, while the sample uses the actual heading/body
  aliases. The existing Save and Cancel controls retain their meaning.
- Default size is a separate saved preference (`font_size_default`). Shortcut adjustments
  persist the current `font_size` without changing the Ctrl+0 target. Old configurations adopt
  their existing size as the default. Both preferences use the authenticated appearance API,
  validation, atomic configuration writes, and cross-window synchronization.
- The version text aligns lower beside the logo, the button gap grows from 12 to 20 px, and
  the beta pill receives an optical vertical correction. Existing colours, controls and layout
  remain the visual reference.

## Validation and release boundary

The development checks passed: 251 Settings/snapshot/documentation tests, browser verification
of both font previews and a saved 16 px Ctrl+0 target, and 39 isolated native desktop checks.
Light/dark and narrower-window rendering were inspected. The owner's preferences and running
app were not changed. Publication additionally requires the full pinned suite, exact-source
Windows CI, native recovery/session checks and the signed-asset packaged upgrade gate.

Provider defaults and runtime compatibility are unchanged. Existing catalogue validation and
provider-default fallback remain in place; this release does not change provider model claims.
This continues the owner-authorized unsigned maintenance beta distribution. Update manifests
are Ed25519-signed; installer Authenticode and clean Windows Sandbox acceptance are not claimed.
Publication includes the matching version and download links on https://armada.stamih.com.
