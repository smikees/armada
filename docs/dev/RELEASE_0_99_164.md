# v0.99.164 — remembered window sizes and easier conversation editing

Published on 23 November 2026 from `27f10d6f4e0999666f0949be87363c24f8634eb8`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.164) and
[website](https://armada.stamih.com/) offer the matching installer.

Detached threads remember their individual dimensions across close/reopen and app
restart. Normal restore bounds are saved when a window is minimized or maximized.
An oversized saved window scales proportionally into 80% of the current monitor's
usable area, then its position is clamped on screen. Invalid preferences fall back
to the default size. See [window sessions](WINDOW_SESSIONS.md).

The main and detached composers use a plain-text editable surface with measured
hanging indents for bullets and numbers, including nesting. Draft, selection,
voice and steering APIs retain their existing plain-text contract. Native undo,
paste, line joining, numbered continuation and wrapped glyph alignment are checked
in WebView2. No rich-text markup is submitted.

Windows paths in conversation prose and inline code open their folder through the
existing explicit-click reveal action. Files are selected in their containing
folder. Inline-code appearance and ordinary text styles are preserved; fenced
code stays literal. Explicit Markdown file links retain their document opener,
and explicit directory links can now open directories. Rendering never accesses
the filesystem. Existing runnable-file safeguards remain in place.

Python's [official release list](https://www.python.org/doc/versions/) was checked
on 23 November 2026: 3.14.10 remains the current patch in the supported 3.14 branch.
The bundled runtime is unchanged. Provider metadata confirmed all first-choice
release preferences remain available; existing model settings and defaults are unchanged.

This release uses the standing maintenance beta procedure: Ed25519-signed update
assets and an unsigned Windows installer. Windows publisher signing and clean
Sandbox acceptance are not claimed. Publication does not restart the owner's app.

The full isolated local suite passed **4,935 tests with 6 skips** in
**716.79 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/45211151233) passed
both Python jobs and relay. The final-source stabilization gate passed fault
recovery, 30-round concurrent soak, history performance, three native thread-window
cycles, page-work and owner workflows. Its evidence is retained in
`build/stabilization-20261123-165833-273655`.

The freshly packaged runtime passed **124 owner-workflow checks**
and **266 thread-window checks**. Native checks cover per-thread
size restoration, proportional fitting on a smaller screen, actual wrapped-glyph
alignment for bullets and numbers, multiline selection, native undo/redo and paste,
typing, list continuation, local-path styling and both views' folder click actions.

Packaged launcher recovery, DLL isolation, authenticated sessions, tray lifecycle,
restart and presentation recovery passed. The signed previous-release upgrade
rehearsal passed **72 checks**. Public verification
checked the Ed25519 manifest signature, exact source commit, all
**519 tracked package files**, installer hash and
matching website version and download links. Installer: **23,544,283
bytes**, SHA-256 `371ff1ce5da4698945625257db9d53ae3de134bc749c3a5a935732600c6e703e`.
Package SHA-256: `0abf4d5ca1a882384853b4d4462042db14dcaffe795fc245e311d3db09ff63b6`.

The public update is available through Settings. The owner's running application
was not restarted or upgraded as part of publication.

Evidence: `build/release-evidence-0.99.164.json`,
`build/public-verification-0.99.164.json`, `build/website-0.99.164-publication.json`,
`build/stabilization-0.99.164.json`, `build/owner-staged-0.99.164.json`,
`build/thread-staged-0.99.164.json`, `build/release-defaults-0.99.164.json`,
`build/golden-review-164.diff` and `build/publish-0.99.164.log`.
