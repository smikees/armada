# `armada/startup.py`

Desktop activation and startup failure reporting, including console-free launches.

### `report_failure(error, *, gui=False)`

Keep diagnostics even when startup fails before the server/window exists.

### `serve_with_desktop(realm, port)`

Serve until stopped, or open the same owner/server in a native desktop on request.
