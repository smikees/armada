# 0.99.135 — Immediate menu feedback

Candidate, 8 November 2026. Publication is pending.

Menu selections show the destination and a loading view immediately while the
server prepares the content. Slow navigation can be stopped without discarding
the outgoing page's fields or scroll position. Other menus remain usable.
[Research, implementation and limits](NAVIGATION_FEEDBACK.md).

The synthetic delayed-response baseline showed no feedback while waiting. The
new controller responded in 2.5ms, within the native probe's 100ms ceiling (DOM
feedback, not physical monitor latency). All four native navigation scenarios,
six page-work checks and 79 shared-window checks passed. Light/wide and dark/1024px
captures and the intentional golden-page diffs were reviewed. Focused navigation,
boundary and documentation checks: **371 passed / one skipped**. Full-suite,
exact-source CI, packaged lifecycle and signed-upgrade gates remain required.

The first candidate passed 4,314 local tests (six skipped), but exact-source CI
exposed an existing simultaneous-launch race. A deterministic synthetic process
reproduced the same missing-owner failure: the kernel lock is held before its
owner state file is published. The duplicate now waits up to ten seconds for
that state, with a clear timeout instead of misidentifying an older server.
Two regression tests cover delayed publication and the timeout; all 23 focused
instance/startup checks passed. The revised source must pass fresh full-suite,
CI, native startup and stabilization gates before publication.
No owner app restart or live realm/provider testing.

Provider model defaults were reviewed against official documentation during M10
on 8 November; this release makes no model or provider changes. Python 3.14.10 and
launcher protocol 2 are unchanged. Distribution continues the existing unsigned
Windows beta maintenance path, with Ed25519-signed update manifests. Windows
publisher signing and clean-machine WebView2 acceptance remain open.
