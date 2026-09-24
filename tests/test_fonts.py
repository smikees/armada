"""Appearance → Fonts (temporary, v0.99.62). The default is the design's own pair and changes
nothing; any other face is a size-corrected alias so swapping one in doesn't break the layout."""
import re
from pathlib import Path

import pytest

from armada import appconfig, fonts

STATIC = Path(fonts.__file__).resolve().parent / "webui" / "static"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_six_families_and_the_design_defaults():
    assert len(fonts.CHOICES) == 6
    assert fonts.DEFAULTS == {"body": "barlow", "heading": "barlow-condensed"}


def test_the_default_emits_nothing(home):
    assert fonts.style() == ""


def test_a_choice_is_saved_and_emitted_for_light_and_dark(home):
    assert fonts.save("body", "montserrat")["ok"]
    css = fonts.style()
    assert ':root,.armada-dark{' in css and '--font-body:"ARMADA Body Montserrat"' in css
    assert "--font-heading" not in css
    assert fonts.save("heading", "roboto")["ok"] and '--font-heading:"ARMADA Heading Roboto"' in fonts.style()


def test_unknown_values_are_refused_and_ignored(home):
    assert fonts.save("body", "comic-sans")["ok"] is False
    assert fonts.save("footer", "roboto")["ok"] is False
    appconfig.save({"font_body": "comic-sans"})
    assert fonts.selected("body") == "barlow"


def test_every_face_exists_with_its_licence_and_size_correction():
    css = (STATIC / "fonts.css").read_text(encoding="utf-8")
    for slug, label in fonts.CHOICES.items():
        assert (STATIC / "fonts" / f"OFL-{slug}.txt").is_file(), slug
        for w in (400, 500, 600, 700):
            assert (STATIC / "fonts" / f"{slug}-{w}.woff2").is_file(), (slug, w)
        for role in ("Body", "Heading"):
            rules = re.findall(r'@font-face\{font-family:"ARMADA ' + role + " " + re.escape(label) + r'";[^}]*\}', css)
            assert len(rules) == 4, (role, label)
            assert all("size-adjust:" in r and "ascent-override:" in r and "font-display:block" in r for r in rules)


def test_the_design_fonts_are_not_resized_in_their_own_role():
    css = (STATIC / "fonts.css").read_text(encoding="utf-8")
    assert 'font-family:"ARMADA Body Barlow";src:url(/static/fonts/barlow-400.woff2) format("woff2");font-weight:400;font-style:normal;font-display:block;size-adjust:100.0%' in css
    assert '"ARMADA Heading Barlow Condensed";src:url(/static/fonts/barlow-condensed-600.woff2)' in css


def test_the_picker_is_in_settings():
    src = (STATIC.parent / "pages.py").read_text(encoding="utf-8")
    assert "_font_picker()" in src and 'onchange="mcSetFont(this)"' in src
