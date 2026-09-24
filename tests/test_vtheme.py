"""Unit tests for the visual-theme registry (theme-as-data)."""
import re
from armada import vtheme


def test_default_theme_has_empty_override():
    # the built-in ARMADA skin lives in brand.css, so its override must be empty (renders unchanged)
    assert vtheme.theme_css(vtheme.DEFAULT) == ""
    assert vtheme.theme_style(vtheme.DEFAULT) == ""


def test_unknown_theme_is_inert():
    assert vtheme.theme_css("does-not-exist") == ""
    assert vtheme.theme_style("does-not-exist") == ""


def test_alternate_theme_overrides_accent_scales():
    css = vtheme.theme_css("ember")
    assert css.startswith(":root{")
    # base + full 100..900 scale for both accent tokens
    for step in ("", "-100", "-500", "-600", "-900"):
        assert f"--color-accent{step}:" in css
        assert f"--color-accent-2{step}:" in css
    # 600 anchors to the base colour
    assert f"--color-accent-600:{vtheme.THEMES['ember']['accent']}" in css


def test_generated_colours_are_valid_hex():
    css = vtheme.theme_css("forest")
    for val in re.findall(r":(#[0-9a-f]{6})", css):
        assert re.fullmatch(r"#[0-9a-f]{6}", val)


def test_style_tag_wraps_css():
    style = vtheme.theme_style("plum")
    assert style.startswith('<style id="mc-vtheme">:root{') and style.endswith("</style>")


def test_swatch_returns_two_colours():
    a, b = vtheme.swatch("slate")
    assert a.startswith("#") and b.startswith("#")
