"""Beta labelling (launch plan 5.7): during the beta every surface that names the app says so, and
switching it off for 1.0 is one value (brand.CHANNEL)."""
from pathlib import Path

from armada import brand
from armada.webui import layout, welcome


def test_the_channel_is_beta_until_1_0():
    assert brand.CHANNEL == "beta"
    assert brand.window_title() == "ARMADA beta"
    assert "beta" in brand.BETA_PILL


def test_the_window_title_still_matches_the_icon_fixer():
    # app._apply_window_icon finds the window by the brand name inside its title.
    assert brand.NAME.lower() in brand.window_title().lower()


def test_nav_welcome_and_settings_show_it():
    src = Path(layout.__file__).read_text(encoding="utf-8")
    assert "{LOGO}{brand.BETA_PILL}" in src
    assert brand.BETA_PILL in welcome.render_welcome([])
    pages = (Path(layout.__file__).parent / "pages.py").read_text(encoding="utf-8")
    assert "<b>v{ver}</b>{brand.BETA_PILL}" in pages   # after </b>: RELEASING.md's version regex still matches


def test_turning_it_off_leaves_nothing_behind(monkeypatch):
    monkeypatch.setattr(brand, "CHANNEL", "")
    assert brand.window_title() == "ARMADA"
