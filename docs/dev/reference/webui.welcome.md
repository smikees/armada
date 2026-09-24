# `armada/webui/welcome.py`

The first-run page (launch plan 5.3): what the app shows when there is no realm to open.

Before this, `armada app` with nothing to open printed a sentence to a console that pythonw doesn't
have and exited — a new user double-clicked the icon and nothing happened at all. Now the server
starts without a realm ("welcome mode", see serve.Handler._route_welcome_*) and every page is this
one: choose ARMADA's folder, create a first realm or open one you already have, and — because
nothing works without it — the Claude sign-in bar. Creating or opening a realm switches the server
into it; from then on it's the normal app.

Deliberately small. The guided setup (Phase 6) replaces the middle of this page; the page itself —
the mode, the routes it may call, the switch at the end — is what 6 builds on.

### `suggested_root()`

Where to suggest ARMADA's folder when none is set: `ARMADA` in the user's home folder.

### `_tpl_cards()`

—

### `_known_realms(realms: list)`

—

### `_q(s: str)`

—

### `render_welcome(realms: list | None=None, note: str='', dark: bool=False)`

—
