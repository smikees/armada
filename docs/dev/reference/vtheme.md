# `armada/vtheme.py`

Visual themes — theme-as-data (Phase 2).

A visual theme is just data: two base brand colours (and optionally fonts) from which a full
token override is generated and injected into the page <head> as a `:root` block. The base
theme "armada" is the app's built-in skin defined in brand.css, so its override is EMPTY —
selecting it renders exactly as before. Alternate themes emit a `:root{…}` block that overrides
the accent token scales, reskinning the whole UI without touching any component.

Per-app (global): the chosen theme id lives in appconfig (~/.armada/config.json).

### `_hex(c: str)`

—

### `_mix(base: str, other: str, pct: float)`

Mix `pct` of `other` into `base` (0..1), return #rrggbb.

### `_scale(prefix: str, base: str)`

—

### `swatch(theme_id: str)`

—

### `theme_css(theme_id: str)`

The :root override body for a theme, or '' for the default/unknown (inherits brand.css).

### `theme_style(theme_id: str)`

A <style> tag to drop after the base stylesheets, or '' for the default theme.
