# `armada/app.py`

Native desktop window for ARMADA (SPEC §13 — the app wrapper).

Wraps the existing local web cockpit (serve.py) in a real OS window via pywebview, so ARMADA
feels like an app rather than a browser tab. The server runs in a background thread on
127.0.0.1; the window points at it. Everything else — Update & Restart, streaming chat,
the dashboard — is unchanged, because it's the same server underneath.

`webview` is imported lazily inside run(), so the stdlib `armada serve` path stays
dependency-free; only `armada app` needs pywebview installed.

### `_alexander_bounds(main, area, width=520, height=720, gap=10)`

Place a companion beside the main window, within this monitor's working area.

### `_alexander_position()`

pywebview uses logical pixels; WinForms working areas use physical pixels.

### class `_AlexanderCompanionAPI`

The companion's close control can destroy only its own native window.

- `_AlexanderCompanionAPI.__init__(self)` — —
- `_AlexanderCompanionAPI.close_window(self)` — Close Alexander without closing the cockpit or losing saved conversation history.

### `_shape_alexander(window)`

Clip the Windows form to the portrait and panel; transparent margins stay click-through.

### `open_alexander(request: dict | None=None)`

Show Alexander in his own native window, reusing one that is already open.

### `_clear_alexander(window)`

—

### `show_main(*, href: str='', report: str='')`

Apply Alexander's navigation/report cards in the main cockpit window.

### `_fatal(msg: str)`

Report a startup failure by every channel that might actually be seen.

### `_server_matches(url: str, realm: str)`

Recognize the same realm without asking the dashboard to render.

### `_wait_until_up(url: str, realm: str, timeout: float=15.0)`

—

### `_free_port_pair(after: int)`

Find separate app/content ports when the default belongs to another server.

### `_set_app_user_model_id()`

Windows: declare our own AppUserModelID so the taskbar stops using pythonw.exe's identity.

### `_retire_scheduler_run_key()`

Remove the sign-in scheduler entry made by older Armada installers.

### `_apply_window_icon()`

Windows: force the ARMADA icon onto our top-level window(s) via WM_SETICON, once they exist.

### `webview2_version()`

The installed WebView2 Runtime's version, or "" if there's none — Microsoft's documented check: a `pv` value above 0.0.0.0 under EdgeUpdate\Clients, machine-wide or per user.

### `_startup_html()`

Self-contained loading view, available before the local server is ready.

### `run(realm: str, port: int=8756, title: str='')`

Open ARMADA in a native window. Blocks until the window is closed.

### `_quit_windows(main, *, close_main=True)`

Exit the GUI. An owner-bound scheduler stops when this process exits.
