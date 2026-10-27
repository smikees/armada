# 0.99.115 — stable find box and capability removal

## Changes

- The page-find panel uses a constrained grid with reserved counter/button columns and a
  flexible input. Empty, successful and unmatched queries retain the same geometry, including
  narrow windows. Tabular figures stabilize the counter; its full value is available on hover.
- Capability removal retains the existing confirmation, then marks only the matching owner,
  kind and ID as pending and inert. A short grayscale state precedes an 180 ms collapse after
  server success. Duplicate deletion and simultaneous access writes are guarded. Other cards,
  filters and expansion remain mounted. Removal does not navigate or reload the section.
- Failed requests restore the card and show a retryable error. Successful removal announces
  completion, updates the filtered list, and supports reduced-motion preferences. Animation
  cancellation cannot turn a successful server deletion into an apparent failure.

## Validation

- Node behavioral harness covers pending state, duplicate admission, scope isolation,
  concurrent access-save guard, failed-delete recovery, reduced motion and no reload.
- Twelve isolated Chromium checks passed on generated ARMADA pages, including unchanged scroll
  and sibling DOM after removal, retry after a simulated failure, and identical search control
  positions for blank, matching, unmatched and large-count states. A 420 px window fits.
- Light screenshots of pending/completed deletion and narrow search were inspected. Browser
  execution reported no script errors. The refinement retains existing theme tokens.
- A single design-detector pass reported only existing accent-border patterns outside this
  change; no new pattern was introduced. Provider metadata confirms current preferred Claude
  and Codex models and Gemini 3.8 Flash; the absent older Gemini fallback remains filtered.
- Final release gates and public download verification passed, as recorded below.

The owner application is not restarted by publication. The authorized Windows beta maintenance
installer is unsigned; compatible update manifests remain cryptographically signed.

## Publication evidence

Published 2026-10-27 as normal/latest
[v0.99.115](https://github.com/smikees/armada/releases/tag/v0.99.115) from source `6c4a54c2c23e41caa564fa68645a5afb38cc04b5` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3754 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40510667424) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- Signed compatible upgrade from 0.99.114 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values. The update signature
  verifies, and its package contains exactly 434 tracked application
  files, byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `8aefc6e6f76cd9b93d17aa7a07a62642899ccfd5f6e774ae6340f5c9b7e916df`.
- The owner's running application was not restarted. The maintenance installer remains unsigned;
  the compatible update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.115.zip` | `f2df09f755bd2b01839b87c34dbe58086ef47f6ffe5fbe6a2951da3ab3642f63` |
| `ARMADA-Setup-0.99.115.exe` | `f95050e2b6413fc1244c59c5fda63db873c9cadfdffc4bb88dcceaace35d29ec` |
| `armada-update.json` | `3a1dbe2485d9539145516b2fe9ab1a34865ebf4108673a89d80c18c2a6f5d487` |
| `armada-update.json.sig` | `2fe8bc31ef0218eb3a4224767f0128c4732ef57cf6ac07a8379789a563c8cbbe` |
