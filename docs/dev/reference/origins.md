# `armada/origins.py`

Where untrusted content is served from (launch plan 5.8a, THREAT_MODEL T3).

The app's pages and its API share one origin, http://127.0.0.1:8756. Anything served on that origin
runs with the whole API in reach — and some of what ARMADA shows it didn't write: a section's local
mini-site (someone's HTML and JavaScript), a mirrored copy of an external page, an HTML or SVG file an
agent attached to a thread. A script in any of those could, until v0.99.58, call /api/chat-stream and
start an agent turn with the owner's permissions.

So that content is served from a second, content-only server on the next port (8757 by default): a
different origin, so its scripts can't read the app's pages, the app refuses its POSTs (Origin ≠ Host)
and its cross-site GETs (Sec-Fetch-Site), and the frames that show it may not navigate the app window.
It still has an origin of its own — unlike a `sandbox` without allow-same-origin — so a mini-site's
localStorage (its theme toggle, its last edition) keeps working.

Layering: webui renders URLs through `content_url()`; serve sets the port once the server is bound.
Nothing here imports the web layer.

### `set_content_port(port: int | None)`

—

### `content_port()`

—

### `content_url(path: str)`

The URL untrusted content at `path` is served from. Without a content server (a test that renders a page directly, or one that failed to bind) the path stays relative, and the app's own server sends it with a CSP sandbox instead — see serve.Handler._send.

### `is_active(name: str)`

—
