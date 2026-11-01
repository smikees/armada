# `armada/desktop_navigation.py`

Keep private desktop navigation inside its authenticated WebView2 profile.

The default pywebview popup handler opens *every* URL in the system browser.
That browser does not share the desktop's local-session cookie. Never pass a
bootstrap credential to it, or promote a popup from an untrusted content frame.

### `local_route(value, base)`

Return a route only for the exact app origin, without URL credentials.

### `trusted_page(route)`

Exclude same-origin fallback documents that are deliberately sandboxed.

### `handle_popup(backend, args, base)`

Return True when a local popup was handled (including refused frames).

### `recover_document(backend, args, base)`

Repair a lost desktop cookie on a document GET, never replay an API action.

### `install(base_url)`

Install before creating any window; base_url follows the bound server port.
