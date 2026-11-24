# v0.99.166 — independent engines and latest-message navigation

Prepared on 24 November 2026. Final release gates and publication are pending.

Claude, OpenAI and Gemini now have independent account-wide execution pools.
The previous shared account and realm caps could queue an OpenAI conversation
behind Claude, particularly when a critical job reduced the realm to one ordinary
slot. Each engine retains two slots, with one reserved when that engine has an
approved critical job. Different models on the same engine share its pool.
Commands retain their separate pool of two and maintenance wrappers their one
separate slot. Conversation serialization, fair realm turns, bounded queues,
cross-process ownership, Stop and post-queue permission validation remain in place.

Opening a thread or minister keeps the latest message visible through late font,
image, formula and viewport layout. Turn-size observation covers visible windows;
the existing snapshot refresh also settles hidden WebView2 windows, where resize
callbacks are deferred. Manual scrolling or transcript interaction stops this
initial following, preserving reading position. Returning through browser history
opens at the latest message and re-enables normal reading controls.

New regressions fail against the preceding behavior: independent same-realm engine
capacity, engine-specific critical reservation, and late transcript growth in
JavaScript and real hidden WebView2 geometry. Native navigation checks cover
thread clicks, minister revisits, unsent drafts and manual scrolling.

Read-only provider metadata on 24 November confirmed that all first-choice model
defaults remain available. Defaults and the previously verified Python 3.14.10
bundled runtime are unchanged.

This release follows the standing maintenance beta procedure: Ed25519-signed
update assets and an unsigned Windows installer. Windows publisher signing and
clean Sandbox acceptance are not claimed. Publication does not restart the owner's app.

Final validation and publication evidence will be recorded after the gates pass.
