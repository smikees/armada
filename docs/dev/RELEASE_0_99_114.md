# 0.99.114 verification

## Changes

- Capabilities serves a standard page shell first, then fetches its inventory fragment. Grant
  calculations are cached only within one render, avoiding stale permission data across requests.
  The measured owner-realm inventory fell from a 4.2-second profiled render to 0.73 seconds under the same profiler (about 0.5 seconds without profiling);
  reader plus shell took about 80 ms. These are local samples, not a performance guarantee.
- Grant/revoke updates return only the affected availability label, chips and filter IDs. Provider
  inventories are excluded from the inline write path. Other controls and expansion remain intact.
- Durable review workers save atomic realm-scoped records under the app data directory. Three
  concurrent reviews per realm are allowed; duplicate submissions share the running task. Reports
  survive navigation/restart; interrupted tasks require an explicit retry. The UI shows 20 recent
  targets. Cache keys include the review protocol and verified source identity (GitHub commit or
  local skill file fingerprint); unverified sources and failed reviews are never reused.
- GitHub repository links in Search route directly to review. Per-report Add state replaces the
  shared global association, preventing one report from accidentally adding another candidate.
- Ctrl+F searches visible section text using DOM ranges and CSS highlights, preserving message
  markup and editor state. It handles inline formatting, nested scrollers, live updates, match
  navigation and Escape. Closed disclosures and hidden tabs are excluded, like editor drafts.

## Validation

- Focused capability/review tests passed, including changed versions, policy changes,
  restart recovery, duplicate launch, realm separation, and no provider launch on inline grants.
- Isolated Chromium browser checks passed for loading, grant/revoke without reload, direct GitHub
  review with sources disabled, navigation recovery while running and after completion, correct
  per-report Add, match highlighting, keyboard navigation, live content, and a 420px search box.
  Light/dark 1440px screenshots were inspected; no browser script errors were reported.
- The bounded Impeccable pass preserved the incumbent Operate design. The single detector scan
  reported only pre-existing accent-border rules elsewhere in brand.css; those are outside this
  refinement. New controls use the existing panel, border, radius and text tokens.
- Provider defaults were checked against current metadata: both Claude preferences and both Codex
  preferences are present. Gemini lists the primary 3.8 Flash; the older 3.7 fallback is absent.
  Existing catalogue filtering and provider-default fallback remain unchanged.
- Final release gates and public download verification passed, as recorded below.

Reviews still use the existing sealed read-only reviewer. No account connection, agent model,
production job, or owner application restart is part of this release. The authorized maintenance
installer is unsigned; compatible updates remain Ed25519-signed.

## Publication evidence

Published 2026-10-27 as normal/latest
[v0.99.114](https://github.com/smikees/armada/releases/tag/v0.99.114) from source `b9a2ff41fa3b5cdf4a68de3eaf1cbb95c729d342` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3751 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40501918220) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- Signed compatible upgrade from 0.99.113 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values. The update signature
  verifies, and its package contains exactly 434 tracked application
  files, byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `4b0210aa5dfa5b1233f3a77a9edaaa7745cddaf16da13d85f42ce4e1d34dd2ed`.
- The owner's running application was not restarted. The maintenance installer remains unsigned;
  the compatible update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.114.zip` | `8a6db32538541f98a5bfefb49283cb08eb5c460350fbe508b5847b65edf022db` |
| `ARMADA-Setup-0.99.114.exe` | `916bfc6d89188d4cdb5f369f2c005dc1fc6207e76b48b212270e2ee571b055e9` |
| `armada-update.json` | `e65eb286502002e4ba8384beb5ba3816bf9a8ea9319cdf607ab3fbd189688734` |
| `armada-update.json.sig` | `a5029ae81d35ff428cdeb5e0ac9e62673ffe6f596dda38a2beb98eed5d110f23` |
