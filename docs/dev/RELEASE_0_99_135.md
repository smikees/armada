# 0.99.135 — Immediate menu feedback

Released from `28d444da0e27c32026d3eaaf9c92bccd72dfaee1` on 8 November 2026.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.135) and
[website](https://armada.stamih.com/) published and verified.

Menu selections show the destination and a loading view immediately while the
server prepares the content. Other menus remain usable; slow navigation can be
stopped without discarding the outgoing page's fields or scroll position.
[Research, implementation and limits](NAVIGATION_FEEDBACK.md).

The synthetic delayed-response baseline showed no feedback while waiting. The
navigation controller responded in **2.6ms** in the final navigation probe,
within its 100ms ceiling (visible DOM state, not physical monitor latency).
All four native navigation scenarios passed. Light/wide and dark/1024px captures
and intentional golden-page diffs were reviewed. This improves feedback latency;
it does not claim that large Artefacts collections finish gathering instantly.

The first candidate passed 4,314 local tests (six skipped), but Windows CI
exposed an existing simultaneous-launch race. A deterministic synthetic process
reproduced the missing-owner failure: the kernel lock is held before its owner
state file is published. A duplicate now waits up to ten seconds for that state,
with a clear timeout instead of misidentifying an older background server.
Two regression tests cover delayed publication and the bounded timeout.

The revised publisher passed **4,316 tests / six skipped**. Both
[exact-source Windows CI jobs](https://github.com/smikees/armada/actions/runs/42515817069)
passed **4,318 / four skipped**. Native startup passed 17 checks. The final
clean-source stabilization gate passed in 210.46s, including faults, concurrent
stress, history budgets, three 79-check native-window cycles, six page-work
checks and 16 owner-workflow checks. Evidence directory:
`build/stabilization-20261108-203555-390091`.

Packaged launcher recovery/DLL isolation, 16 session checks, 68 tray checks,
69 checks in each restart mode, 86 presentation checks and **72 signed-upgrade
checks** passed. Fresh main/companion light/dark recovery captures were reviewed.
Public update signatures, package/source bytes, installer hash and matching
website version/release/download links verified. Installer SHA-256:
`5ff9251b48ea6c5f156f6c11e5acb6e815f13b8d4576638fc018218e85dc4330`.
No owner app restart or live realm/provider testing.

Provider model defaults were reviewed against official documentation during M10
on 8 November; this release makes no model or provider changes. Python 3.14.10 and
launcher protocol 2 are unchanged. Distribution continues the existing unsigned
Windows beta maintenance path, with Ed25519-signed update manifests. Windows
publisher signing, clean-machine WebView2 acceptance and maintainer product
acceptance remain open.
