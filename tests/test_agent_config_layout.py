"""Agent Configure page layout.

The page had a two-column grid where one cell carried a long helper paragraph and its neighbour
didn't, plus a bare filler <div> to force a row break. The result was Model and Effort landing in
different rows, visibly offset. These guard the fixed shape: the inbox fields live in their own
section, the grid has no filler cells, and Advanced is last.
"""
import re

from armada.webui import agentframe


FIELD = "display:block;width:100%"
LBL = "font-size:10px"


def _a2a(on=True):
    return agentframe._a2a_box(on, "<option>x</option>", "<option>y</option>", FIELD, LBL)


def _adv():
    return agentframe._agent_advanced_box("<option>m</option>", "", FIELD, LBL)


def test_inbox_fields_live_under_one_master_switch():
    html = _a2a(True)
    assert 'id="c-a2a"' in html and 'class="mc-toggle-sl"' in html
    assert 'id="c-freq"' in html and 'id="c-accepts"' in html
    # both fields sit inside the switched container, so they grey out together
    fields = html.index('id="c-a2a-fields"')
    assert fields < html.index('id="c-freq"') < html.index('id="c-accepts"')


def test_the_switch_is_on_by_default_and_greys_the_fields_when_off():
    on, off = _a2a(True), _a2a(False)
    # the inline handler also mentions `.checked`, so look at the input tag itself
    assert 'id="c-a2a" checked' in on and 'id="c-a2a" checked' not in off
    assert "opacity:.45;pointer-events:none" in off
    assert "opacity:.45" not in on, "nothing should look disabled while the switch is on"


def test_both_columns_of_the_a2a_grid_carry_helper_text():
    """The original misalignment came from one column having a helper paragraph and the other not.
    align-items:start makes unequal heights harmless either way."""
    html = _a2a()
    assert html.count("font-size:11px;color:var(--text-muted)") == 2
    assert "align-items:start" in html


def test_advanced_is_a_visible_section_heading_not_a_muted_label():
    html = _adv()
    assert agentframe._SECTION_H in html
    assert "text-transform:uppercase" not in html.split("</summary>")[0], \
        "Advanced read as a field label when it was small uppercase muted text"
    assert "mc-adv-caret" in html, "it needs an affordance showing it opens"
    assert "rotate(90deg)" in html, "and the caret should turn when it does"


def test_configure_grid_has_no_filler_cells_and_advanced_comes_last():
    src = (agentframe.__file__)
    body = open(src, encoding="utf-8").read()
    conf = body[body.index("def _tab_configure"):]
    conf = conf[:conf.index("\ndef ", 10)]
    assert "<div></div>" not in conf, "a bare filler cell is what pushed Model out of line"
    assert conf.index("_a2a_box") < conf.index("_agent_advanced_box"), \
        "Advanced belongs at the end, after agent-to-agent"
    for marker in ("c-soul", "c-mandate", "c-tenets"):
        assert conf.index(marker) < conf.index("_a2a_box"), \
            "agent-to-agent goes below the soul/mission/tenets fields"


def test_colour_sits_with_the_cosmetic_fields_not_after_the_behavioural_ones():
    """Name, role, profile, colour — how the agent looks. Autonomy, model, effort — how it acts."""
    for path, colour, autonomy in (
            (agentframe.__file__, "c-color", "c-autonomy"),
            (agentframe.__file__.replace("agentframe.py", "realmpages.py"), "n-color", "n-autonomy")):
        body = open(path, encoding="utf-8").read()
        assert body.count(colour) == 1, f"{colour} should appear exactly once"
        assert body.index(colour) < body.index(autonomy), \
            f"{colour} belongs above {autonomy}"


def test_realm_settings_define_the_defaults_agents_inherit(tmp_path):
    """The per-agent page offers 'inherit realm default' — this is where that default is set."""
    from armada.webui import pages
    (tmp_path / "realm.json").write_text('{"name":"t"}', encoding="utf-8")
    html = pages._a2a_defaults_box(tmp_path)
    assert 'id="st-a2a"' in html and 'class="mc-toggle-sl"' in html
    assert 'id="st-a2a-cadence"' in html and 'id="st-a2a-accepts"' in html
    assert 'id="st-a2a" checked' in html, "agent-to-agent is on by default"
    # defaults preselected from the inbox module, not hard-coded twice
    from armada import inbox
    assert f'value="{inbox.DEFAULT_CADENCE}" selected' in html
    assert f'value="{inbox.DEFAULT_ACCEPTS}" selected' in html


def test_realm_switch_off_greys_its_defaults(tmp_path):
    from armada.webui import pages
    (tmp_path / "realm.json").write_text('{"name":"t","inbox":{"enabled":false}}', encoding="utf-8")
    html = pages._a2a_defaults_box(tmp_path)
    assert 'id="st-a2a" checked' not in html
    assert "opacity:.45;pointer-events:none" in html


def test_realm_settings_save_sends_the_a2a_block():
    js_path = re.sub(r"agentframe\.py$", "static/js/settings.js",
                     agentframe.__file__.replace("\\", "/"))
    js = open(js_path, encoding="utf-8").read()
    assert "mcA2APayload" in js and "inbox:mcA2APayload()" in js
    assert "if(!t)return undefined" in js, \
        "an older layout without the section must not silently clear the settings"


def test_save_sends_the_switch():
    js_path = re.sub(r"agentframe\.py$", "static/js/agent.js", agentframe.__file__.replace("\\", "/"))
    js = open(js_path, encoding="utf-8").read()
    assert "enabled:!document.getElementById('c-a2a')" in js
