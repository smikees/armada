# `armada/brand.py`

ARMADA brand surface — the single place that defines the app's visible identity.

Everything user-visible that *names or pictures* the product lives here: the name, the logo/mark
markup, the about blurb, the logo/icon asset filenames, and the window/page title format. A future
rebrand (or a white-label) should be a one-file edit — change the constants here and the titlebar,
window title, About panel, and OS icon all follow.

Out of scope on purpose: the COLOUR palette (CSS custom properties in webui/static/*.css) and prose
inside docstrings/CLI logs — those aren't part of the app's visual chrome. The realm's own icon
(uploaded per realm) is separate too; this is the ARMADA product brand.

### `_asset_v(asset: str)`

Cache-buster so a new logo shows at once instead of waiting out the browser's cache.

### `window_title()`

The OS window title: 'ARMADA beta' during the beta, 'ARMADA' after.

### `page_title(sub: str='')`

Browser-tab / OS-window title: 'ARMADA — <sub>' (or just the name).

### `icon_path()`

Absolute path to the OS window/taskbar icon file.
