# v0.99.159 — resizable Register and stable page loading

Prepared on 17 November 2026. Final release gates and publication are pending.

Register columns have pointer and keyboard resize handles. Widths are local
presentation preferences keyed by the document's immutable realm identity, shared
with promoted Register sections. Arrow keys resize, Shift makes smaller changes,
and Home/double-click restores a column. Pointer cancellation restores the prior
width; rows retain their navigation behavior and the table scrolls horizontally.

The outgoing-page loading replacement is removed. Navigation marks its link
without changing the current title, agent frame, content, scroll or draft. Native
document navigation, authentication, cancellation and Back remain browser-owned.
The delayed-navigation test retains the eight-second cancel recovery.

Artefacts and Capabilities now serve lightweight destination frames first. Heading,
actions and tabs are identical before and after loading; only the inventory region
changes. Cold content uses an authenticated request and ordered first-party scripts.
Warm navigation includes the cached body directly, avoiding another loading phase.
The new Artefacts content endpoint is covered by the normal authentication and
realm-binding checks. The existing capabilities loader is replaced by a shared one.

The process-local cache lasts 30 seconds from rendering, has eight-entry and total
size bounds, and is keyed by canonical realm path plus page. App POSTs invalidate
it before and after dispatch, fencing in-flight renders; reload/Refresh bypasses
it. External edits can remain visible as the earlier snapshot for up to 30 seconds.
Nothing is persisted to a realm, and cached markup never authorizes a mutation.

Focused verification passed **427 tests**, including the reviewed golden pages
and generated references. Native page/loading checks cover populated content,
correct destination frames from a thread, unchanged heading/action/tab geometry,
warm revisits without inventory requests, refresh, failures/retry and Register
resizing/persistence in narrow enlarged-text dark mode. The bounded visual review
found a clipped-header issue and corrected it; the confirmation pass passed. The
design detector reported no findings in the changed targets. The existing Overview
subscription header can overlap at 900 px with enlarged text; it is outside this
change and no Overview header styling was changed.

The navigation probe's loaded-event injector raced rapid document replacement;
the test bridge is now embedded in its synthetic documents. Product startup code
is unchanged. The final native navigation journey passed seven checks with
2.5 ms link feedback while the destination response was held, without test-bridge
errors. Full release gates are recorded below after they finish.

In the small synthetic route fixture, a warm Artefacts request took 17.16 ms
(previously 23.69 ms) and Capabilities 18.28 ms (previously 39.11 ms). These are
single server-side observations, not a user latency guarantee. The stronger
acceptance evidence is the native revisit check: no inventory request and no
loading placeholder on either warm page. Native click-to-content observations
were 101 ms and 225 ms respectively. Both destinations had zero measured heading,
action and tab geometry shift while their content arrived.

Provider metadata review confirmed the preferred defaults remain available.
The bundled runtime remains Python 3.14.10, verified against the official Python
release listing on 17 November 2026 during the preceding release; no runtime or
provider defaults changed. This continues the established unsigned maintenance
beta: Ed25519 update signing remains mandatory; Windows publisher signing and
clean Sandbox acceptance remain outside the verified boundary. The owner's
running app is not restarted to publish.
