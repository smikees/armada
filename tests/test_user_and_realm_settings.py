"""Where each setting lives.

Timezone moved out of User settings into Realm settings: it's what the scheduler runs *this
realm's* jobs against, so one person keeping two realms in two timezones was impossible while it
hung off their profile. The owner's free-text "About you" went the other way — it's about the
person, not the realm, and it lands in the System memory every agent reads.
"""
import json

from armada import memory
from armada.webui import pages


def _realm(tmp_path, user=None, tz=None):
    cfg = {"name": "T", "user": dict(user or {})}
    if tz:
        cfg["timezone"] = tz
    (tmp_path / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    (tmp_path / "memory").mkdir(exist_ok=True)
    return tmp_path


def test_timezone_is_offered_in_realm_settings_not_user_settings():
    src = open(pages.__file__, encoding="utf-8").read()
    assert 'id="st-tz"' in src, "the realm tab owns the timezone picker now"
    assert 'id="us-tz"' not in src, "it should be gone from the user tab, not merely duplicated"


def test_about_you_is_offered_in_user_settings():
    src = open(pages.__file__, encoding="utf-8").read()
    assert 'id="us-about"' in src
    assert "About you" in src


def test_saving_user_settings_no_longer_sends_a_timezone():
    js = open(pages.__file__.replace("pages.py", "static/js/user.js"), encoding="utf-8").read()
    assert "timezone:" not in js.split("function mcTzUpdate")[0]
    assert "about:" in js


def test_saving_realm_settings_sends_the_timezone():
    js = open(pages.__file__.replace("pages.py", "static/js/settings.js"), encoding="utf-8").read()
    assert "timezone:(document.getElementById('st-tz')" in js


def test_timezone_appears_under_realm_in_the_system_memory(tmp_path):
    r = _realm(tmp_path, user={"name": "Mihai"}, tz="Europe/Madrid")
    body = memory.system_digest(r)
    realm_block = body.split("## Realm")[1].split("##")[0]
    owner_block = body.split("## Owner")[1].split("##")[0]
    assert "Europe/Madrid" in realm_block
    assert "Europe/Madrid" not in owner_block, "it's a realm fact, not a fact about the person"


def test_a_timezone_saved_the_old_way_still_shows_up(tmp_path):
    """Realms written before the move kept it under user; it must not silently vanish."""
    r = _realm(tmp_path, user={"name": "Mihai", "timezone": "Europe/Bucharest"})
    assert "Europe/Bucharest" in memory.system_digest(r).split("## Realm")[1]


def test_about_you_reaches_every_agent_verbatim(tmp_path):
    about = "I think in writing.\nDon't hedge — say when something is a bad idea."
    r = _realm(tmp_path, user={"name": "Mihai", "about": about})
    owner_block = memory.system_digest(r).split("## Owner")[1].split("##")[0]
    for line in about.splitlines():
        assert line in owner_block


def test_an_empty_about_adds_nothing(tmp_path):
    r = _realm(tmp_path, user={"name": "Mihai", "about": "   "})
    assert "In their own words" not in memory.system_digest(r)


def test_the_realms_current_icon_is_marked_on_load():
    """It used to be marked only after you clicked one, so the page opened showing no selection at
    all — you couldn't tell which icon your realm actually had."""
    src = open(pages.__file__, encoding="utf-8").read()
    assert "_SETICON_ON if ic == _cur_icon" in src
    js = open(pages.__file__.replace("pages.py", "static/js/settings.js"), encoding="utf-8").read()
    fill = pages._SETICON_ON.replace("background:", "").rstrip(";")
    assert fill in js, "the click handler must paint the same fill the server does"


def test_an_uploaded_image_marks_no_tile():
    """An uploaded icon isn't one of the tiles, so marking one would be a lie about what's in use."""
    src = open(pages.__file__, encoding="utf-8").read()
    assert '_cur_icon = "" if _uploaded' in src


def test_new_realm_sits_with_the_page_not_inside_the_realm_section():
    src = open(pages.__file__, encoding="utf-8").read()
    assert 'right_html=new_realm_btn' in src
    header = src.index("new_realm_btn =")
    realm_sect = src.index('sect("Realm"')
    assert header > realm_sect, "the button should no longer be built inside the Realm section"
    assert src.count("mcNewRealmOpen(event)") == 1, "one New realm button, not two"


def test_page_title_right_html_is_not_escaped_but_right_still_is():
    from armada.webui import _base
    assert "<button>x</button>" in _base._page_title("T", right_html="<button>x</button>")
    assert "&lt;b&gt;" in _base._page_title("T", right="<b>")


def test_saving_realm_settings_rebuilds_the_system_memory():
    """The timezone is in that memory, so changing it has to regenerate — this was only wired to
    the user-settings save before the move."""
    import armada.routes.realm as _realm_routes  # _save_realm_settings lives here (Phase 2, 2.3)
    src = open(_realm_routes.__file__, encoding="utf-8").read()
    assert '_refresh_system("realm-settings")' in src


# --------------------------------------------------------------- what counts as advanced

def test_the_workspace_folder_sits_under_advanced():
    """It is the only setting on the page about the machine rather than the realm, and under Realm
    identity it read as a routine field. It is neither routine nor identity."""
    src = open(pages.__file__, encoding="utf-8").read()
    body = src[src.index("def render_settings"):]
    adv = body.index('id="st-advanced"')
    assert body.index("_workspace_box(realm, cfg)") > adv, "still outside Advanced"
    assert body.count("_workspace_box(realm, cfg)") == 1, "moved, not copied"
    assert "Workspace &amp; portability" in body


def test_opening_advanced_scrolls_it_into_view():
    """Same behaviour as the agent's Configure page — one helper, wired by ontoggle."""
    src = open(pages.__file__, encoding="utf-8").read()
    body = src[src.index("def render_settings"):]
    assert 'ontoggle="mcRevealSection(this)"' in body
    assert "_REVEAL_JS" in body, "the handler has to be on the page that calls it"


def test_the_reveal_helper_is_shared_not_copied():
    from armada.webui import _base, agentframe
    assert agentframe._REVEAL_JS is _base._REVEAL_JS
    assert open(pages.__file__, encoding="utf-8").read().count("function mcRevealSection") == 0
