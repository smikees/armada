"""Colour mode: light · dark · system.

It was written to localStorage and never read back, so it was a property of whatever URL Settings
navigated to rather than a preference — and 'System' could never even show as selected, because
the radio was checked from how the current page happened to be rendering.
"""
from pathlib import Path

import pytest

from armada import appconfig
from armada.webui import layout, pages

_MODEBOOT_JS = Path(layout.__file__).with_name("static").joinpath("js", "modeboot.js")


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    monkeypatch.setattr(appconfig, "_path", lambda: tmp_path / "config.json")


def _mode_html(mode):
    appconfig.save({"appearance": mode})
    return layout._theme_style()


def test_the_mode_is_stored_per_machine_next_to_the_theme():
    appconfig.save({"appearance": "dark"})
    assert layout.appearance_mode() == "dark"
    assert appconfig.get("appearance") == "dark"


def test_an_unset_or_junk_mode_falls_back():
    assert layout.appearance_mode() == layout.APPEARANCE_DEFAULT
    appconfig.save({"appearance": "aubergine"})
    assert layout.appearance_mode() == layout.APPEARANCE_DEFAULT


def test_dark_renders_dark_server_side():
    appconfig.save({"appearance": "dark"})
    assert layout.dark_default() is True


def test_system_renders_light_and_lets_the_browser_correct_it():
    """Only the browser knows what the OS is set to. Rendering light and correcting in a head
    script avoids both a redirect and a flash."""
    appconfig.save({"appearance": "system"})
    assert layout.dark_default() is False
    boot = layout._theme_style()
    assert "/static/js/modeboot.js" in boot, "the boot script must be loaded"
    js = _MODEBOOT_JS.read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in js
    assert "armada-dark" in js


def test_the_boot_script_runs_only_in_system_mode():
    for m in ("light", "dark"):
        assert "prefers-color-scheme" not in _mode_html(m), f"{m} needs no probing"


def test_the_boot_script_survives_running_before_body_exists():
    """It's in <head>, so document.body is null when it first runs — setting the class only on
    <body> would silently do nothing on first paint."""
    _mode_html("system")
    js = _MODEBOOT_JS.read_text(encoding="utf-8")
    assert "documentElement.classList" in js
    assert "DOMContentLoaded" in js, "and it has to catch up once the body is there"


def test_the_mode_follows_the_os_changing_mid_session():
    _mode_html("system")
    assert "addEventListener(\"change\"" in _MODEBOOT_JS.read_text(encoding="utf-8")


def test_every_page_honours_the_saved_mode_not_just_the_url():
    """Twelve handlers read `"dark" in self._query()` directly, which is why the mode applied to
    the page Settings navigated to and was lost on the next click.

    The GET handlers that render `dark=self._dark()` now live across serve.py and its
    armada/routes/ mixins (Phase 2, 2.3 split serve.py by area) rather than in one file, so this
    reads the combined source of all of them."""
    root = Path(__file__).resolve().parents[1] / "armada"
    serve_src = root.joinpath("serve.py").read_text(encoding="utf-8")
    routes_src = "".join(p.read_text(encoding="utf-8")
                         for p in sorted(root.joinpath("routes").glob("*.py")))
    assert "def _dark(self)" in serve_src
    # _dark's own docstring and implementation are the one place allowed to read the query
    # directly — carve that one method's block out, then nothing outside it (in serve.py or any
    # routes/ mixin) should still read "dark" from the query.
    dark_fn = serve_src.split("def _dark(self)")[1].split("\n    def ")[0]
    rest = serve_src.replace(dark_fn, "", 1) + routes_src
    assert '"dark" in self._query()' not in rest, \
        "no handler should read the query directly any more"
    assert (serve_src + routes_src).count("dark=self._dark()") >= 10


def test_the_url_override_still_works():
    """Embeds and 'send someone a dark page' both rely on ?dark=1."""
    src = Path(__file__).resolve().parents[1].joinpath("armada", "serve.py").read_text(encoding="utf-8")
    fn = src.split("def _dark(self)")[1].split("\n    def ")[0]
    assert '"dark" in self._query()' in fn and "dark_default()" in fn


def test_the_radio_is_checked_from_the_saved_mode():
    """Deriving it from the rendered darkness meant System snapped back to Light the instant you
    chose it — it renders light, so the radio re-checked Light."""
    src = Path(pages.__file__).read_text(encoding="utf-8")
    block = src.split('name="mc-mode"')[1].split(">")[0]
    assert "_mode" in block
    assert '"dark" if dark else "light"' not in block


def test_saving_the_mode_goes_to_the_server():
    js = Path(pages.__file__).with_name("static").joinpath("js", "settings.js").read_text(encoding="utf-8")
    fn = js.split("async function mcSetMode(v){")[1].split("\n// ")[0]
    assert "/api/save-appearance" in fn and "mode:v" in fn
    assert "localStorage" not in fn, "storing it client-side is what made it unreadable"
    assert "?dark=1" not in fn, "the mode is a preference now, not a URL flag"


def test_the_endpoint_validates_the_mode():
    # _save_appearance lives in armada/routes/settings.py (Phase 2, 2.3 split serve.py by area).
    src = Path(__file__).resolve().parents[1].joinpath(
        "armada", "routes", "settings.py").read_text(encoding="utf-8")
    fn = src.split("def _save_appearance(self")[1].split("\n    def ")[0]
    assert "APPEARANCE_MODES" in fn and "unknown colour mode" in fn


def test_telegram_sits_after_engine_in_app_settings():
    src = Path(pages.__file__).read_text(encoding="utf-8")
    tab = src.split("app_tab = (")[1].split("\n\n")[0]
    assert tab.index('sect("Engine"') < tab.index('sect("Telegram"') < tab.index('sect("Notifications"')
