# 0.99.94 verification

The Jobs and Edit job dry-run section now uses the same disclosure component as
Prompt, Output and Run history: the shared 14-pixel chevron, heading typography,
spacing, indentation and divider. Its title is **Dry run history**. Both pickers
use the existing run-output select styling; body text uses the same 13-pixel
scale as production output. The duplicate Dry run action above the sections is
removed; Start dry run remains inside the expanded section.

The obsolete shortcut handler and its production-button disabling exception are
removed. Production and dry-run execution, selection and cancellation remain
independent. User documentation follows the new disclosure entry point.

The native Jobs probe opens the actual disclosure and checks its computed styles,
shared icon, alignment and single launch control, in addition to the existing
model selection, disabled-job, Stop, history and inspector authorization paths.
Both desktop and narrow layouts are required, with light/dark visual evidence.

Runtime and provider execution are unchanged. Release-owned provider preferences
retain connected-provider filtering and the provider-default fallback. This
continues the existing owner-authorized unsigned Windows beta distribution;
update manifests remain Ed25519-signed. Trusted publisher signing and clean-
Sandbox GUI acceptance remain outstanding.

## Validation and publication

- Job-row and dry-run tests: **78 passed**. Snapshot and documentation-reference
  verification: **179 passed**. Python imports and both edited JavaScript syntax
  checks passed. Module references are current.
- The native WebView2 probe passed **16 checks at 1280 pixels and 16 at 660 pixels**.
  Light/desktop and dark/narrow rendered evidence was reviewed together; the
  shared disclosure, picker styling and body scale match the neighboring sections.
- Only two HTML snapshots changed: the handbook search text and the new changelog
  entry. Both diffs were reviewed.
- The required single Impeccable detector pass found seven existing brand.css
  warnings in untouched styles (accent borders, a capability stripe and an image
  comment). None belongs to the new rules; preserving the existing application
  appearance is part of this bounded polish request.

The enforced publisher must still pass the complete pinned isolated suite,
exact-source Windows CI, compiled-launcher recovery, branded native sessions and
the exact signed-package upgrade checks. Final publication and public-download
verification will be recorded here after those gates complete.
