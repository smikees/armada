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
- Release gates and public publication evidence will be recorded after they complete.

The owner application is not restarted by publication. The authorized Windows beta maintenance
installer is unsigned; compatible update manifests remain cryptographically signed.
