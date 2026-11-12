# 0.99.142 - Smooth detached thread and portrait edges

Released on 12 November 2026 from `703e32300d19dd8a36c6e04ac442687b10926ca5`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.142)
and [website](https://armada.stamih.com/) both offer v0.99.142.

A click-through native perimeter preserves WebView2's fractional-alpha boundary
pixels around detached threads and their protruding portraits. The live editor
and transcript remain in the original WebView. Captures stay in memory, follow
theme/portrait/size changes and are disposed with their window. Source and runtime
checks verify coloured partial-alpha pixels, a fully transparent conversation
centre, automatic dark palette refresh, resizing and cleanup. See
[the rendering contract](THREAD_EDGES.md).

The final enforced publisher passed **4,471 tests with six skips** in 853.56 seconds.
Both exact-commit Windows jobs passed **4,473 tests with four skips**. Validation
used the verified explicit manual workflow selector, recording its real trigger
in `build/release-evidence-0.99.142.json`.
[Windows CI](https://github.com/smikees/armada/actions/runs/43220684710).

The full gate caught missing diagnostic logging in the new preview-start fallback;
this was corrected before the final source validation. One CI job then hit the
existing section-snapshot path-validation race also observed during v0.99.141.
Twelve isolated repeats passed; the entire failed CI job passed on retry without
a source change. That unrelated snapshot issue remains a separate follow-up.

Final-source stabilization passed in **279.84 seconds**, with three **112-check**
native thread cycles. Evidence is in `build/stabilization-20261112-134450-819684`.
The bundled Python 3.14.10 runtime separately passed all **112 native thread checks**
in `build/thread-edge-bundled-0.99.142.json`. Light/dark composites were reviewed.
Actual mixed-DPI monitor transitions remain unverified.

The final installer passed all five launcher recovery points, external DLL
isolation, 16 WebView2 session checks, 68 tray checks, three 69-check restart cases
and 86 presentation checks. Main/companion light and dark recovery captures were
reviewed. The signed upgrade from v0.99.141 passed **72 checks** against these assets.

Public verification confirmed the update signature, tag/manifest commit, ZIP hash,
all **488 packaged source files**, website links and the downloaded installer hash.
The **23,403,278-byte** installer has SHA-256
`c0310618e623863e3d1eae2ae65aa12325193b4353d82cfbe5a315c0516956b7`.
The update ZIP has SHA-256
`bddca7176cdf21caaa706b36d895b78ecd7ae7dc13559dae627e81e77cc6ccd9`.
Evidence: `build/public-release-0.99.142.json`, `build/upgrade-0.99.142.json` and
`build/release-evidence-0.99.142.json`.

This continues the owner-authorized unsigned maintenance beta distribution.
Ed25519 update signing passed; trusted Windows publisher signing and clean-machine
Sandbox acceptance remain unverified. The owner app was not restarted, live realms
were not modified and the temporary worker account was left in place as requested.
