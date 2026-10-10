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

## Published evidence — 2026-10-10

- Published normal/latest [v0.99.102](https://github.com/smikees/armada/releases/tag/v0.99.102)
  from source `7e74a1751a1074fa20532cb982676206948dd377` through the enforced maintenance publisher.
- Full pinned isolated suite: **3,602 passed, 5 skipped**.
- Both Windows Python configurations and the relay check passed in
  [exact-source CI](https://github.com/smikees/armada/actions/runs/38070422057).
- Five native launcher recovery points, 16 multi-window checks and 63 packaged upgrade checks
  passed. The upgrade test moved the actual packaged app from 0.99.101 to 0.99.102.
- All four public downloads match the tested build; the Ed25519 manifest signature, package
  size/hash, source commit and all 341 packaged source files were verified.
- Published `website/index.html` with verified FTPS after backing up the previous page. Public
  HTTPS content matches the committed page after removing the hosting provider's known
  injection, and the installer downloaded from its link matches the tested build.
- The owner's running ARMADA app and unfinished work in the original checkout were preserved.

| Public artifact | SHA-256 |
| --- | --- |
| `ARMADA-Setup-0.99.102.exe` | `d564df463ced2bc4273cc960c241e28faa52da233bd79fec7d796258aebef531` |
| `armada-0.99.102.zip` | `65198b65a7f6a2f98eb9f4dd475aa7f56171ef71ea5d5bdf9bc4e6102422aec9` |
| `armada-update.json` | `a2a11ef58e47c095beabf7a2a48acdeebde11c9d4ac7d97bc1327606e0af6acb` |
| `armada-update.json.sig` | `82f2ee388114a747df2e9bfd9456b3f12be02f10d892353df453dac4ddcbac40` |
| Website source `index.html` | `33b637a39e154feefb727b1a168e139723c84846e040cd9f3fafac8d76606c5b` |

Evidence in the isolated release checkout: `build/publish102.log`,
`build/release-evidence-0.99.102.json`, `build/upgrade-0.99.102.json`,
`build/public-0.99.102-verification.json` and `build/website-0.99.102-publication.json`.
This documentation-only follow-up does not alter the tagged application source.
