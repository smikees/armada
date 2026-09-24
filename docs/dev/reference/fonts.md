# `armada/fonts.py`

The app's font faces — a temporary Appearance setting (v0.99.62), to become part of themes/skins.

Six families, each selectable for body text and for headings. The faces themselves, and the
measured size/line-metric corrections that let one replace another without the layout breaking,
are generated into static/fonts.css by tools/build_fonts.py; this module only knows the choices,
the defaults, and how to say "use these" to a page.

Per machine, like the colour theme: stored in appconfig as `font_body` / `font_heading`. The
defaults are the design's own (Barlow, Barlow Condensed) and emit nothing, so a page in the default
fonts is byte-for-byte what it was before this setting existed.

### `selected(role: str)`

—

### `family(role: str, slug: str)`

The CSS font-family value for `slug` in `role` — the size-corrected alias face.

### `style()`

A <style> block overriding --font-body / --font-heading, or "" for the design's own fonts. Declared on :root and .armada-dark alike, like every token the dark mode re-declares.

### `save(role: str, slug: str)`

—
