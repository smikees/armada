"""Small pieces of chrome that were each saying the wrong thing.

The Overview header grew twice after load — once when the usage fetch filled the KPIs, once when
the limits fetch filled the bars — and shoved the grid down under it both times. The section-edit
button kept its pencil after you'd entered edit mode, so the only sign it had worked was a colour
change on the button itself. The cost pill said "uses your quota" in a column where every row does.
And the Jobs legend said "7-day health" over a strip that is three days back, today, three forward.
"""
import datetime
import json
import re
from pathlib import Path

import pytest

from armada import reader
from armada.webui import agentbits as AB
from armada.webui import layout as LAY
from armada.webui import pages as P
from armada.webui import realmpages as R

STATIC = Path(R.__file__).parent / "static" / "js"


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "Cabinet-realm"
    (root / "agents" / "finance" / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps(
        {"name": "Cabinet", "sections": [{"name": "Usage", "widget": "usage"}]}), encoding="utf-8")
    (root / "agents" / "finance" / "agent.json").write_text(
        json.dumps({"id": "finance", "display": "Warren"}), encoding="utf-8")
    (root / "agents" / "finance" / "jobs" / "alpha.json").write_text(json.dumps(
        {"id": "alpha", "name": "Alpha", "cron": "0 9 * * *", "prompt": "p"}), encoding="utf-8")
    return root


# --------------------------------------------------------------------------- the header's height

def test_the_header_has_a_fixed_height(realm):
    html = P.render_dashboard(reader.read(str(realm)), realm)
    ovh = html[html.index('id="mc-ovh"'):]
    ovh = ovh[:ovh.index(">")]
    assert "height:76px" in ovh and "box-sizing:border-box" in ovh


def test_the_limits_box_cannot_grow(realm):
    """It is empty at load, two bars a moment later, and a wrapped sentence when unavailable."""
    html = P.render_dashboard(reader.read(str(realm)), realm)
    box = html[html.index('id="mc-hdr-limits"'):]
    box = box[:box.index(">")]
    assert "height:62px" in box and "overflow:hidden" in box


def test_a_kpi_cell_cannot_grow_or_wrap(realm):
    html = P.render_dashboard(reader.read(str(realm)), realm)
    assert 'class="mc-kpi" style="height:62px;white-space:nowrap"' in html


def test_the_kpi_value_still_arrives_late(realm):
    """The fix is a reserved space, not a removed skeleton."""
    html = P.render_dashboard(reader.read(str(realm)), realm)
    assert "mc-skel" in html and "data-v=" in html


# --------------------------------------------------------------------------- the edit toggle

def test_the_nav_carries_both_edit_glyphs(realm):
    html = LAY._nav(reader.read(str(realm)), "Overview")
    assert "mc-sec-on" in html and "mc-sec-off" in html
    from armada.icons import ICONS
    assert ICONS["edit-off"][:40] in html, "not fluent/edit-off-16-regular"


def test_the_off_glyph_is_hidden_until_edit_mode(realm):
    html = LAY._nav(reader.read(str(realm)), "Overview")
    off = html[html.index("mc-sec-off"):][:60]
    assert "display:none" in off


def test_edit_off_is_drawn_on_its_own_grid():
    from armada.icons import _ICON_VB
    assert _ICON_VB["edit-off"] == "0 0 16 16", "a 16-grid icon on a 24 viewBox draws quarter-size"


def test_the_toggle_swaps_the_glyph_and_leaves_the_background():
    js = (STATIC / "section_edit.js").read_text(encoding="utf-8")
    assert "el.style.background=MC_GREY;" in js, "the button still tints itself"
    assert "var(--color-accent-100)" not in js
    assert ".mc-sec-on" in js and ".mc-sec-off" in js


def test_the_toggle_retitles_itself():
    js = (STATIC / "section_edit.js").read_text(encoding="utf-8")
    assert "Done editing sections" in js


# --------------------------------------------------------------------------- the cost pill

def test_the_quota_pill_is_shorter_and_carries_the_dial():
    pill = R._job_cost_pill("prompt", 0, 0)
    assert ">uses quota<" in pill.replace("</span>uses quota", ">uses quota<")
    assert "uses quota" in pill and "uses your quota" not in pill
    from armada.icons import ICONS
    assert ICONS["quota"][:30] in pill, "not eos-icons/quota"


def test_the_estimate_pill_carries_it_too():
    """Both say "this run costs subscription"; only one of them knows how much."""
    pill = R._job_cost_pill("prompt", 14000, 5)
    from armada.icons import ICONS
    assert ICONS["quota"][:30] in pill
    assert "≈14k / run" in pill


def test_a_command_job_is_still_free_and_undialled():
    pill = R._job_cost_pill("command", 0, 0)
    from armada.icons import ICONS
    assert ">free</span>" in pill and ICONS["quota"][:30] not in pill


# --------------------------------------------------------------------------- the legend

def test_the_legend_says_what_the_strip_covers():
    leg = AB._status_legend()
    assert "-/+3D job outcome and outlook" in leg
    assert "7-day health" not in leg


def test_the_legend_still_lists_every_status():
    leg = AB._status_legend()
    for label in AB._HEALTH_WORST:
        assert label in leg, label


def test_the_legend_matches_the_window_it_describes():
    """If the Jobs week stops being ±3 days, this label becomes a lie."""
    assert (AB._WEEK_BACK, AB._WEEK_FWD) == (3, 3)
