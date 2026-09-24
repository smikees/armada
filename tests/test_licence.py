"""Licence (launch plan 5.9, ADR-007): the repo and the app say PolyForm Noncommercial, source-
available, never MIT or "open source", and the third-party notices cover what actually ships."""
import re
from pathlib import Path

from armada import brand

ROOT = Path(__file__).resolve().parents[1]


def test_licence_file_names_polyform_and_carries_the_required_notice():
    t = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "PolyForm Noncommercial License 1.0.0" in t
    assert "https://polyformproject.org/licenses/noncommercial/1.0.0" in t
    assert re.search(r"^Required Notice: Copyright", t, re.M)
    assert "MIT" not in t


def test_nothing_user_facing_says_mit_or_open_source():
    for f in [ROOT / "README.md", *(ROOT / "docs" / "user").glob("*.md")]:
        t = f.read_text(encoding="utf-8")
        assert "MIT licensed" not in t, f
        assert "open source" not in t.lower() or "not open source" in t.lower(), f
    assert "Source-available" in brand.LICENCE and "open source" not in brand.LICENCE.lower()


def test_settings_about_shows_the_licence():
    src = (ROOT / "armada" / "webui" / "pages.py").read_text(encoding="utf-8")
    assert "brand.LICENCE" in src and "brand.LICENCE_URL" in src


def test_every_bundled_font_is_in_the_notices():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    static = ROOT / "armada" / "webui" / "static"
    fonts = [p.name for p in static.rglob("*") if p.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2")]
    assert fonts, "expected the Barlow webfonts"
    for name in fonts:
        family = "Barlow" if name.startswith("barlow") else name
        assert family in notices, f"{name} ships but isn't credited in THIRD_PARTY_NOTICES.md"
