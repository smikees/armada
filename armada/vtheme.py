"""Visual themes — theme-as-data (Phase 2).

A visual theme is just data: two base brand colours (and optionally fonts) from which a full
token override is generated and injected into the page <head> as a `:root` block. The base
theme "armada" is the app's built-in skin defined in brand.css, so its override is EMPTY —
selecting it renders exactly as before. Alternate themes emit a `:root{…}` block that overrides
the accent token scales, reskinning the whole UI without touching any component.

Per-app (global): the chosen theme id lives in appconfig (~/.armada/config.json).
"""
from __future__ import annotations

DEFAULT = "armada"


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(base: str, other: str, pct: float) -> str:
    """Mix `pct` of `other` into `base` (0..1), return #rrggbb."""
    br, bg, bb = _hex(base)
    orr, og, ob = _hex(other)
    r = round(br + (orr - br) * pct)
    g = round(bg + (og - bg) * pct)
    b = round(bb + (ob - bb) * pct)
    return f"#{r:02x}{g:02x}{b:02x}"


# tint (toward white) / shade (toward black) ramp; 600 == base, matching brand.css's convention
_STOPS = {
    "100": ("#ffffff", 0.90), "200": ("#ffffff", 0.74), "300": ("#ffffff", 0.55),
    "400": ("#ffffff", 0.32), "500": ("#ffffff", 0.13), "600": (None, 0.0),
    "700": ("#000000", 0.16), "800": ("#000000", 0.33), "900": ("#000000", 0.50),
}


def _scale(prefix: str, base: str) -> str:
    out = [f"{prefix}:{base}"]
    for step, (toward, pct) in _STOPS.items():
        val = base if toward is None else _mix(base, toward, pct)
        out.append(f"{prefix}-{step}:{val}")
    return ";".join(out)


# id -> {name, accent, accent2}. armada is the built-in (empty override).
THEMES: dict[str, dict] = {
    "armada": {"name": "ARMADA", "accent": "#0b3f86", "accent2": "#12a3b8"},
    "ember":  {"name": "Ember",  "accent": "#b4531f", "accent2": "#c99230"},
    "forest": {"name": "Forest", "accent": "#2f6d4f", "accent2": "#6a9b3f"},
    "plum":   {"name": "Plum",   "accent": "#6a3d9a", "accent2": "#b0559a"},
    "slate":  {"name": "Slate",  "accent": "#3f5670", "accent2": "#5c8ea8"},
}


def swatch(theme_id: str) -> tuple[str, str]:
    t = THEMES.get(theme_id) or THEMES[DEFAULT]
    return t["accent"], t["accent2"]


def theme_css(theme_id: str) -> str:
    """The :root override body for a theme, or '' for the default/unknown (inherits brand.css)."""
    if theme_id == DEFAULT or theme_id not in THEMES:
        return ""
    t = THEMES[theme_id]
    return ":root{" + _scale("--color-accent", t["accent"]) + ";" \
           + _scale("--color-accent-2", t["accent2"]) + "}"


def theme_style(theme_id: str) -> str:
    """A <style> tag to drop after the base stylesheets, or '' for the default theme."""
    css = theme_css(theme_id)
    return f'<style id="mc-vtheme">{css}</style>' if css else ""
