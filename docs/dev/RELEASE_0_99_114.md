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
- Release gates and public publication evidence will be recorded after they complete.

Reviews still use the existing sealed read-only reviewer. No account connection, agent model,
production job, or owner application restart is part of this release. The authorized maintenance
installer is unsigned; compatible updates remain Ed25519-signed.
