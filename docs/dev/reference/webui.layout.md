# `armada/webui/layout.py`

Page chrome / layout (carved from _core.py in Phase 3).

The title bar, top nav (realm switcher + tabs + user sections), page shell (<head> + body
frame) and KPI header, plus per-app visual-theme injection. Imports lower layers + assets
(never _core); _core re-imports these so page renderers keep calling _page_shell()/_nav().

### `appearance_mode()`

light · dark · system — per machine, alongside the theme.

### `dark_default()`

Should the server render dark? 'system' renders light and lets the browser correct it — only the browser knows what the OS is set to.

### `_mode_boot()`

Apply the OS colour scheme when the mode is 'system'.

### `_theme_style()`

—

### `_titlebar(realm)`

—

### `_nav(realm, active: str='Overview', sec_edit: bool=False)`

—

### `_htok(n)`

Token count formatted EXACTLY like usage.js's htok(), so the server-rendered header value and the value usage.js writes on load are byte-identical — no visible 'jump' on every Overview visit.

### `_kpis(realm, tok30=None, usd30=None)`

—

### `_page_shell(realm, active_tab: str, title: str, body: str, dark: bool=False, sec_edit: bool=False)`

—
