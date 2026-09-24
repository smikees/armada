# `armada/assets.py`

Static-asset plumbing — how server-rendered pages reference the CSS/JS served from webui/static.

`CSSV` is a cache-buster derived from the stylesheets' mtimes, so a CSS edit + restart forces
browsers to refetch. `js()` builds a <script src> tag for an externalized JS module (kept out of
webui.py for smaller diffs / lintability); the per-module tags are pre-built here. `CSS_LINKS` is
the stylesheet <link> pair, cache-buster baked in, used in every page's <head>.

### `js(name: str)`

Reference an externalized JS module served from webui/static/js/. Keeps big scripts out of webui.py (lintable, smaller diffs).
