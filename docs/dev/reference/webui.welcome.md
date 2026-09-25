# `armada/webui/welcome.py`

The first-run page (launch plan 5.3): what the app shows when there is no realm to open.

Before 5.3, `armada app` with nothing to open printed a sentence to a console that pythonw doesn't
have and exited. Since 5.3 the server starts without a realm ("welcome mode", see
serve.Handler._route_welcome_*) and every page is the first-run page. Since 6.4 that page is the
first half of the setup wizard (webui/setup_wizard.py); this module keeps the entry point and the
suggested folder.

### `suggested_root()`

Where to suggest ARMADA's folder when none is set: `ARMADA` in the user's home folder.

### `render_welcome(realms: list | None=None, note: str='', dark: bool=False)`

—
