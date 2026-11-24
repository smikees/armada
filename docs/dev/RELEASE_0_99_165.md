# v0.99.165 — detached shadows and editable steering

Prepared on 24 November 2026. Final release gates and publication are pending.

Detached-window shadows and antialiased edges now remain immediately above their
own window, below any foreground thread. Previously each refresh used
ShowWindow(SW_SHOWNOACTIVATE), which could raise a background decoration over a
front window. Both decorators now use a shared SetWindowPos operation that places
them beside their owner without activating or reordering that owner. This covers
delayed startup captures, movement, hiding and re-showing overlapping threads.
Normal Windows activation still brings the selected window and its decorations
forward together. The saved-size and restart cascade behavior is unchanged.

OpenAI's voice controls incorrectly disabled the composer for every active run,
overriding the steering state immediately after each thread poll. They now lock
input only for an active local or remote audio session or audio teardown. Ending
audio re-enables text drafting/steering even if the agent is still working. The
thread state updater respects the same audio ownership. Drafts and Stop retain
their existing behavior.

The HWND regression runs on a private Windows desktop and checks real native
stacking after refresh, hide/re-show and activation changes. Browser regressions
cover voice controls during ordinary work, active audio, audio ending and draft
preservation. The hidden WebView2 journey now switches to the OpenAI layout and
inserts text using native editing in both main and detached steering composers,
then verifies focus and editability survive polling and acknowledged delivery.
Repeated native validation also exposed late font loading during list measurement.
The composer recalculates hanging indents when lazy-loaded marker fonts finish;
the geometry test waits for fonts before comparing actual rendered glyph positions.

Python's [official release list](https://www.python.org/doc/versions/) was checked
on 24 November 2026: 3.14.10 remains the current patch in the supported 3.14 branch.
The bundled runtime is unchanged. Read-only provider metadata confirmed all
first-choice defaults remain available; existing defaults and model settings are unchanged.

This release follows the standing maintenance beta procedure: Ed25519-signed
update assets and an unsigned Windows installer. Windows publisher signing and
clean Sandbox acceptance are not claimed. Publication does not restart the owner's app.

Final validation and publication evidence will be recorded after the gates pass.
