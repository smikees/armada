# Detached thread edge compositing

Windows regions have binary coverage. Clipping the WebView directly to an ellipse
and rounded panel discards Chromium's fractional-alpha boundary pixels, making
the avatar and window corners appear jagged.

`thread_edge.Edge` displays a narrow perimeter from WebView2's transparent
CapturePreview on a non-activating, click-through owned layered window. The real
WebView is clipped two logical pixels inward; the captured band extends three
pixels inward to overlap the opaque boundary. The middle of the overlay stays
fully transparent, so the conversation, caret and editor remain live. The
existing shadow is retained. No desktop background is sampled or baked in.

Captures remain in memory and are disposed after extracting the band. One capture
can run at a time. Native movement repositions the overlay without recapturing;
resizing/DPI changes invalidate its dimensions. Browser theme, portrait and header
updates request coalesced captures. Continuous updates cannot postpone capture
indefinitely. A stale or unavailable initial capture leaves the previous native
clip intact. The overlay, timer, bitmap and event handlers are owned by the form
and released on close, including a completed capture awaiting its UI callback.

The native probe checks fractional coloured alpha at the portrait, a transparent
conversation centre, automatic dark palette refresh, matching browser/perimeter
colours, resizing, normal conversation operations and overlay cleanup. Light and
dark composites use an orange backdrop to expose hard boundaries and fringes.
Actual mixed-DPI monitor transitions still need hardware validation; the overlay
refuses previews whose physical dimensions do not match the current viewport.

Local validation on 12 November 2026: 68 affected/reference tests and 112 native
thread checks passed. The generated light/dark composites were reviewed. Evidence:
`build/thread-edge-final.json`; all conversations and provider responses were
synthetic. The installed app and live realm were not restarted or modified.

This implementation is separate from API billing work. Version 0.99.142 is in
release validation. Do not combine it with concurrent billing edits without
reviewing and testing the resulting source commit.
