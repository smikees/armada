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


def test_alternate_themes_have_distinct_dark_foregrounds_and_fills():
    for theme in ('ember', 'forest', 'plum', 'slate'):
        css = vtheme.theme_css(theme)
        light, dark = css.split(':root.armada-dark,.armada-dark{')
        light_tokens = dict(re.findall(r'(--[\w-]+):(#[0-9a-f]{6})', light))
        dark_tokens = dict(re.findall(r'(--[\w-]+):(#[0-9a-f]{6})', dark))
        assert light_tokens.keys() == dark_tokens.keys()
        assert all(light_tokens[key] != dark_tokens[key] for key in dark_tokens)
        assert sum(vtheme._hex(dark_tokens['--color-accent-100'])) < 150
        assert sum(vtheme._hex(dark_tokens['--color-accent'])) > 400
