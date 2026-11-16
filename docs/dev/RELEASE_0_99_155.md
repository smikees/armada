# v0.99.155 — thread drafts and matching list markers

Prepared on 16 November 2026. Publication checks are pending.

Drafts previously used the entire page URL as their identity. Visiting Memories
and returning to Threads omits the thread query, so a remembered conversation
looked under a different storage key. Drafts now follow the rendered realm,
agent and thread identity, preserving separate drafts in each view. Existing
URL-keyed drafts migrate when their page is visited, and native recovery accepts
the current page's previous keys. Empty drafts remain cleared.

The composer uses two original circular glyphs with equal outlines and matching
vertical centres. Main items are filled and sub-items hollow. The font maps only
the two markers, preserving the selected body font for text and indentation;
no runtime font-building dependency is added.

The production draft-controller regression reproduces the original loss before
the change. The hidden WebView2 navigation probe passes the actual agent-section
links, remembered sub-thread, exact multiline text and clearing checks. The
separate marker comparison passes 19 browser checks for geometry, fill, alignment,
scaling and unchanged prose/spacing across the seven body fonts.

The focused desktop, thread, run-control and font suite passes 108 tests.
The 21 deliberately regenerated page snapshots change only the user-guide
search text and current changelog. Generated module references remain unchanged.
Read-only provider catalogue review confirms each preferred default remains
available. Python 3.14.10 remains the current 3.14 maintenance release
([official releases](https://www.python.org/downloads/)).

Full local gate, exact-source CI, clean-source stabilization, packaged lifecycle
and upgrade checks, staged owner workflows and public downloads remain pending.

This continues the owner-authorized unsigned maintenance beta. Update assets
use Ed25519 signatures; Windows publisher signing and clean Sandbox acceptance
remain unverified. Publication does not restart the owner's running app.
