# Dashboard and settings polish — 0.99.153

Calendar source filters use a shared local preference and retain individual System
entries in every view. The Armada mark uses the existing logo alpha mask with currentColor.
Descriptions render through the existing safe Markdown renderer with one-line collapse.
Running job rows combine owned command markers and active admission tickets, deduplicated
by agent/job, with existing activity refreshes removing completed work.

Run controls validate before saving other form fields and use the overall settings Save.
Cross-agent proposal permission lives in machine-owned agent policy. Upgrade snapshots
owner-appointed coordinators; later profile edits cannot enable this permission. Explicit
legacy permissions migrate before the realm form replaces its visible choices. Owner
team edits and newly appointed coordinators initialize the new defaults.

Dirty state is document-local and compares form snapshots. Successful saves establish
only their submitted snapshot, preserving later edits. Failed saves retain the highlight.
No form values enter browser storage. Reduced-motion users see a static highlight.

Custom section templates were missing the `.mc-appscroll` container used by the existing
navigation controller, so their navigation bypassed loading feedback. All section
variants now provide it. The native delayed-response check covers this path.

The budget is explicitly an estimate; see [API fallback](API_FALLBACK.md). No provider
budget or live job approval is changed by this release. Shared bullet input uses four
spaces and hollow nested markers, and the saved Markdown parser accepts both markers.

Regression coverage includes proposal migration/defaults, regular-agent authorization,
invalid budgets, incomplete receipts, calendar filtering, dirty-state reversal and edits
during a save, custom templates, descriptions, running-job deduplication, and native
owner journeys plus both thread windows. Exact-source release evidence is recorded
separately after publication.
