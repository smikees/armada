# `armada/app.py`

Native desktop window for ARMADA (SPEC §13 — the app wrapper).

Wraps the existing local web cockpit (serve.py) in a real OS window via pywebview, so ARMADA
feels like an app rather than a browser tab. The server runs in a background thread on
127.0.0.1; the window points at it. Everything else — Update & Restart, streaming chat,
the dashboard — is unchanged, because it's the same server underneath.

`webview` is imported lazily inside run(), so the stdlib `armada serve` path stays
dependency-free; only `armada app` needs pywebview installed.

### `_fatal(msg: str)`

Report a startup failure by every channel that might actually be seen.

### `_wait_until_up(url: str, timeout: float=15.0)`

—

### `_set_app_user_model_id()`

Windows: declare our own AppUserModelID so the taskbar stops using pythonw.exe's identity.

### `_apply_window_icon()`

Windows: force the ARMADA icon onto our top-level window(s) via WM_SETICON, once they exist.

### `webview2_version()`

The installed WebView2 Runtime's version, or "" if there's none — Microsoft's documented check: a `pv` value above 0.0.0.0 under EdgeUpdate\Clients, machine-wide or per user.

### `run(realm: str, port: int=8756, title: str='')`

Open ARMADA in a native window. Blocks until the window is closed.
