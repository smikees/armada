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
SIZE_DEFAULT = 13
SIZE_MIN = 10
SIZE_MAX = 26


def reference_size() -> int:
    """Reference text size in pixels; invalid saved preferences keep the design default."""
    value = appconfig.get('font_size', SIZE_DEFAULT)
    return value if type(value) is int and SIZE_MIN <= value <= SIZE_MAX else SIZE_DEFAULT


def save_size(value) -> dict:
    """Persist a validated whole-pixel reference without changing font families."""
    if type(value) is not int or not SIZE_MIN <= value <= SIZE_MAX:
        return {'ok':False, 'error':f'Font size must be a whole number from {SIZE_MIN} to {SIZE_MAX} px.'}
    try:
        appconfig.save({'font_size':value})
    except OSError as exc:
        return {'ok':False, 'error':str(exc)}
    return {'ok':True, 'font_size':value}


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
    size = reference_size()
    if size != SIZE_DEFAULT:
        parts += [f'--mc-font-reference:{size}', f'--mc-font-scale:{size / SIZE_DEFAULT:.8f}']
    return f"<style>:root,.armada-dark{{{';'.join(parts)}}}</style>" if parts else ""


def save(role: str, slug: str) -> dict:
    if role not in KEYS or slug not in CHOICES:
        return {"ok": False, "error": "unknown font"}
    appconfig.save({KEYS[role]: slug})
    return {"ok": True, "role": role, "font": slug, "family": family(role, slug)}
