"""The app's font faces — a temporary Appearance setting (v0.99.62), to become part of themes/skins.

Six families, each selectable for body text and for headings. The faces themselves, and the
measured size/line-metric corrections that let one replace another without the layout breaking,
are generated into static/fonts.css by tools/build_fonts.py; this module only knows the choices,
the defaults, and how to say "use these" to a page.

Per machine, like the colour theme: stored in appconfig as `font_body` / `font_heading`. The
defaults are the design's own (Barlow, Barlow Condensed) and emit nothing, so a page in the default
fonts is byte-for-byte what it was before this setting existed.
"""
from __future__ import annotations

from . import appconfig

CHOICES = {                       # slug -> label (the label is the family name in fonts.css)
    "barlow": "Barlow",
    "barlow-condensed": "Barlow Condensed",
    "montserrat": "Montserrat",
    "nunito-sans": "Nunito Sans",
    "quicksand": "Quicksand",
    "roboto": "Roboto",
}
DEFAULTS = {"body": "barlow", "heading": "barlow-condensed"}
KEYS = {"body": "font_body", "heading": "font_heading"}


def selected(role: str) -> str:
    v = str(appconfig.get(KEYS[role], DEFAULTS[role]) or DEFAULTS[role])
    return v if v in CHOICES else DEFAULTS[role]


def family(role: str, slug: str) -> str:
    """The CSS font-family value for `slug` in `role` — the size-corrected alias face."""
    return f'"ARMADA {role.title()} {CHOICES[slug]}", system-ui, sans-serif'


def style() -> str:
    """A <style> block overriding --font-body / --font-heading, or "" for the design's own fonts.
    Declared on :root and .armada-dark alike, like every token the dark mode re-declares."""
    parts = [f"--font-{role}:{family(role, selected(role))}"
             for role in ("body", "heading") if selected(role) != DEFAULTS[role]]
    return f"<style>:root,.armada-dark{{{';'.join(parts)}}}</style>" if parts else ""


def save(role: str, slug: str) -> dict:
    if role not in KEYS or slug not in CHOICES:
        return {"ok": False, "error": "unknown font"}
    appconfig.save({KEYS[role]: slug})
    return {"ok": True, "role": role, "font": slug, "family": family(role, slug)}
