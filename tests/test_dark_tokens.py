"""Derived colour tokens must resolve against the DARK palette in dark mode.

A CSS custom property's `var()` is substituted where the property is declared, and descendants
inherit the already-substituted value. `--text-muted: color-mix(in srgb, var(--color-text) 55%, …)`
declared only on `:root` therefore bakes in the light ink, and `.armada-dark` on `<body>` —
which redefines `--color-text` — never reaches it: every muted label, pill and hover in dark mode
was near-black on near-black. Found 2026-09-24 by the Phase 4 audit; the fix declares derived
tokens on `:root,.armada-dark`. This keeps it that way.
"""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "armada" / "webui" / "static"


def _rules(css: str):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        yield " ".join(m.group(1).split()), m.group(2)


def test_every_token_built_from_another_token_is_redeclared_for_dark_mode():
    offenders = []
    for name in ("industry.css", "brand.css"):
        for sel, body in _rules((STATIC / name).read_text(encoding="utf-8")):
            for prop, val in re.findall(r"(--[\w-]+)\s*:\s*([^;}]*)", body):
                if "var(" in val and ".armada-dark" not in sel:
                    offenders.append(f"{name}: {sel} {{ {prop} }}")
    assert not offenders, ("a custom property defined from another var() must be declared on "
                           "':root,.armada-dark' so it re-resolves in dark mode:\n  " + "\n  ".join(offenders))


def test_the_derived_tokens_exist_on_both_selectors():
    css = (STATIC / "brand.css").read_text(encoding="utf-8")
    sels = [sel for sel, body in _rules(css) if "--text-muted:" in body]
    assert sels == [":root,.armada-dark"], sels


def _declared(css: str, want_dark: bool) -> set:
    out = set()
    for sel, body in _rules(css):
        is_dark = ".armada-dark" in sel
        if is_dark == want_dark or (want_dark and is_dark):
            out |= set(re.findall(r"(--color-[\w-]+)\s*:", body))
    return out


def test_every_palette_token_the_ui_uses_has_a_dark_value():
    """A --color-* step used by a component but missing from .armada-dark keeps its light value in
    dark mode — how the usage bars' tracks and the widget headers stayed light grey."""
    css = "".join((STATIC / n).read_text(encoding="utf-8") for n in ("industry.css", "brand.css"))
    dark = _declared(css, True)
    webui = STATIC.parent
    used = set()
    for f in list(webui.rglob("*.py")) + list((STATIC / "js").glob("*.js")) + [STATIC / "brand.css"]:
        used |= set(re.findall(r"var\((--color-[a-z0-9-]+)\)", f.read_text(encoding="utf-8")))
    missing = sorted(used - dark)
    assert not missing, f"used in the UI but no dark value in .armada-dark: {missing}"


def test_no_hardcoded_light_surfaces_in_the_stylesheet():
    css = re.sub(r"/\*.*?\*/", "", (STATIC / "brand.css").read_text(encoding="utf-8"), flags=re.S)
    hits = re.findall(r"background:\s*(#e[0-9a-f]{2,5}|#f[0-9a-f]{2,5}|white)\b", css, flags=re.I)
    # #fff stays legal: white on a filled control (the toggle knob, primary buttons) is the
    # documented exception in DESIGN_TOKENS.md. Near-white SURFACES are what break dark mode.
    hits = [h for h in hits if h.lower() not in ("#fff", "#ffffff")]
    assert not hits, hits


def test_every_class_the_design_system_promises_exists():
    """DESIGN_SYSTEM.md marks the classes Phase 4 migrates onto as *new*; F1 adds them. A class the
    spec names but the stylesheet lacks would make a Haiku ticket silently do nothing."""
    spec = (Path(__file__).resolve().parents[1] / "docs" / "dev" / "DESIGN_SYSTEM.md").read_text(encoding="utf-8")
    css = (STATIC / "brand.css").read_text(encoding="utf-8")
    promised = set()
    for chunk in re.findall(r"\*new\*\s*((?:`[^`]+`[\s,+/a-z]*)+)", spec):
        for cls in re.findall(r"`\.([\w-]+)(?:\.[\w-]+)?", chunk):
            promised.add(cls)
    missing = sorted(c for c in promised if not re.search(r"\." + re.escape(c) + r"\b", css))
    assert promised and not missing, missing
