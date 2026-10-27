# 0.99.116 — Armada II usage bars

## Changes

- Armada II subscription readings use 80 px rounded tracks, warm neutral backgrounds,
  green/amber/red fills, IBM Plex Mono labels, and dashed outlines for unavailable readings.
  Dark mode supplies its own palette. Missing and stale telemetry retain their existing labels
  and accessibility descriptions; zero usage remains a measured zero.
- Armada II opts into amber at 50% and red at 90%. Other themes retain their original fill
  colors and thresholds through CSS-variable fallbacks. Countdown labels say "Reset in…".
- Narrower Overview windows reserve a second header row before readings arrive, preventing
  clipping and content shifts. Very narrow windows shorten tracks equally and allow scrolling.

## Validation

- Focused usage, theme, UI-refinement and dark-token tests passed before release preparation.
- Isolated Chromium checks on rendered Overview HTML covered 760, 1100, 1280, 1440 and 1920 px
  windows: equal track widths, dashed missing values, reset text within provider columns, and
  the dark palette. Wide, stacked and dark screenshots were inspected.
- The design hook reported no deterministic issues in the theme stylesheet. Existing provider
  fetching, cache, account connections and reporting semantics are unchanged.
- Provider metadata confirms the preferred Claude and Codex models and Gemini 3.8 Flash.
  The absent older Gemini fallback remains filtered; defaults need no change.
- Final release gates and public download verification passed, as recorded below.

The owner application is not restarted by publication. The authorized Windows beta maintenance
installer is unsigned; compatible update manifests remain cryptographically signed.

## Publication evidence

Published 2026-10-27 as normal/latest
[v0.99.116](https://github.com/smikees/armada/releases/tag/v0.99.116) from source `b25049b20322def05ade39564bd105819b17c81b` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3756 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40530066664) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- Signed compatible upgrade from 0.99.115 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values. The update signature
  verifies, and its package contains exactly 434 tracked application
  files, byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `6b541d314e23e044d43d42c529d1d9be5a69181a5f109a1a9295140101f2c438`.
- The owner's running application was not restarted. The maintenance installer remains unsigned;
  the compatible update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.116.zip` | `652402cde08df7a22a65015dde8253509c27e84d8d99cf558d541bdb84408feb` |
| `ARMADA-Setup-0.99.116.exe` | `44e28ef532ead3986ffac2003ecc5a1f9ee0772f0a9407103b978f370f3f15ad` |
| `armada-update.json` | `cd7a55abad5f6e732039cd363eaf53827b363f3046cf1d519aa357a129c0570a` |
| `armada-update.json.sig` | `81abc006f2456d77f8ce400edd7abf4e01c306d5f78ff9dbebb03b377ce0ee90` |
