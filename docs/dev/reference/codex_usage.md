# `armada/codex_usage.py`

Account-wide OpenAI limits through Codex's authenticated app-server protocol.

No credentials are read by Armada and no model turn is started. The short-lived subprocess
only initializes and reads account/rateLimits/read; failures never become a fabricated 0%.

### `_read_limits(timeout=20)`

—

### `_window(raw, fallback)`

—

### `_normalize(raw)`

—

### `fetch()`

Cache account readings for one minute, including failures; never block a page render.

### `cached_plan()`

Return a known plan without delaying provider cards on an account probe.
