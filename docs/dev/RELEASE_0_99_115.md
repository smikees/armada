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
- Release gates and public publication evidence will be recorded after they complete.

The owner application is not restarted by publication. The authorized Windows beta maintenance
installer is unsigned; compatible update manifests remain cryptographically signed.
