# v0.99.161 — synchronized menu and page transitions

Prepared on 17 November 2026. Publication awaits the final-source release gates.

The previous release selected the destination immediately while deliberately
keeping outgoing content visible. This could show Artefacts selected above the
Capabilities inventory. Navigation now switches both visible states together:
the destination title and loading spinner replace the previous content below the
main menu as soon as navigation starts. Old agent headers, breadcrumbs, subtabs
and custom-section iframes are covered as part of the same transition.

Outgoing regions stay in their original DOM with unchanged geometry. They become
hidden, inert and excluded from accessibility; cancellation restores their prior
inert and aria-hidden values, fields, scroll and selection. The loading view tracks
the menu's bottom edge when its layout changes. Browser document navigation still
owns requests, realm binding, history, cancellation and redirects. Native errors
clear the transition too. The prior inventory cache and archive-count fix remain.

The native probe holds document responses to expose the exact pre-response state.
It verifies Capabilities → Artefacts, Artefacts → Capabilities, thread → Artefacts
and custom sections, plus cancellation, rapid selection, Back and unsent drafts.
Its hidden WebView2 fixture explicitly delivers resize after changing the native
window size because occluded renderers defer animation-frame-driven delivery.

This change is confined to navigation presentation. It does not change admission,
persistence, history reads or native desktop lifecycle; the additional stabilization
gate is not required by the release procedure for this scope. The full suite,
exact-source Windows CI, packaged lifecycle/recovery checks, owner workflows,
page-loading/navigation journeys and signed upgrade rehearsal remain required.

Provider defaults and the Python 3.14.10 runtime are unchanged. This follows the
established unsigned maintenance beta: update packages are Ed25519-signed;
Windows publisher signing and clean Sandbox acceptance remain outside the verified
boundary. Publication does not restart the owner's running app.

The focused JavaScript guards passed. The native navigation probe passed 11
checks, with the synchronized state visible in 6.2 ms while the response was held.
Light/wide, dark/narrow and thread-origin captures were reviewed: only the
destination heading and spinner remain below the menu. The design detector found
no issues. The only changed golden page adds the new owner-facing release note.

Evidence: `build/navigation-161.json`, `build/golden-review-161.diff`,
`build/design-161.json`, `build/release-defaults-0.99.161.json`.
Final release results follow after the gates.
