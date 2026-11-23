# v0.99.164 — remembered window sizes and easier conversation editing

Prepared on 23 November 2026. Final release gates and publication are pending.

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

Final validation and publication evidence will be recorded after the gates pass.
