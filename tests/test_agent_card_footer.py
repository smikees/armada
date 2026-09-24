"""The minister card's two footer groups, and the job page's action bar.

The card footer used to be six counts in an even line with the appointed date pushed to the far
right — six things that look equivalent but are not, plus a date that belongs to the person rather
than to the tally. The counts now split: what the agent is working on and with (goals, memories,
active jobs) on the left, what it can reach (connectors, extensions, skills, plugins) on the right,
and the appointment sits under the portrait.
"""
import datetime
import json
import re
from pathlib import Path

import pytest

from armada import reader
from armada.webui import realmpages as R
from armada.webui import pages as P

WEBUI = Path(R.__file__).parent


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "Cabinet-realm"
    ad = root / "agents" / "finance"
    (ad / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({
        "id": "finance", "display": "Warren", "role": "Minister of Finance",
        "appointed": "2026-09-17"}), encoding="utf-8")
    for jid, on in (("alpha", True), ("beta", True), ("gamma", False)):
        (ad / "jobs" / f"{jid}.json").write_text(json.dumps({
            "id": jid, "name": jid.title(), "cron": "0 9 * * *", "prompt": "p",
            "kind": "prompt", "enabled": on}), encoding="utf-8")
    return root


def _card(realm, aid="finance"):
    m = reader.read(str(realm))
    html = R._realm_ministers(m, realm, datetime.date.today())
    i = html.index(f'href="/agent/{aid}" class="mc-agent')
    rest = html[i:]
    nxt = rest.find('class="mc-agent', 40)
    return rest[:nxt] if nxt > 0 else rest


def _counts(card):
    return {m.group(2): int(m.group(1)) for m in re.finditer(r'title="(\d+) ([a-z ]+)"', card)}


# --------------------------------------------------------------------------- the jobs count

def test_the_footer_carries_active_jobs(realm):
    assert _counts(_card(realm)).get("active jobs") == 2, "a job that is off was counted"


def test_the_jobs_count_uses_the_clock_play_icon(realm):
    from armada.icons import ICONS
    assert "M12 7v5l2 2m3 8l5-3l-5-3z" in ICONS["clock-play"], "not tabler/clock-play"
    assert "M12 7v5l2 2m3 8l5-3l-5-3z" in _card(realm)


def test_jobs_comes_after_memories(realm):
    card = _card(realm)
    order = [m.group(1) for m in re.finditer(r'title="\d+ ([a-z ]+)"', card)]
    assert order[:3] == ["goals", "memories", "active jobs"], order


def test_the_old_total_jobs_line_is_gone(realm):
    """Two counts of the same thing on one card, disagreeing, is worse than one."""
    assert not re.search(r">\d+ jobs</div>", _card(realm))


# --------------------------------------------------------------------------- the two groups

def test_the_capabilities_are_pushed_right(realm):
    card = _card(realm)
    assert "margin-left:auto" in card, "the two groups are not separated"
    right = card.split("margin-left:auto", 1)[1]
    for label in ("connectors", "extensions", "skills", "plugins"):
        assert f' {label}"' in right, f"{label} is not in the right group"


def test_the_left_group_is_goals_memories_jobs(realm):
    card = _card(realm)
    left = card.split("margin-left:auto", 1)[0]
    for label in ("goals", "memories", "active jobs"):
        assert f' {label}"' in left, f"{label} is not in the left group"


def test_all_seven_counts_are_still_shown(realm):
    assert len(_counts(_card(realm))) == 7


# --------------------------------------------------------------------------- the appointment

def test_appointed_sits_under_the_portrait(realm):
    card = _card(realm)
    assert "Appointed 2026-09-17" in card
    assert card.index("Appointed") < card.index("border-top:1px solid var(--color-divider)"), \
        "appointed is still in the footer"


def test_the_date_is_stacked_under_its_icon(realm):
    """The avatar column is 44px wide; a date beside the icon does not fit in it."""
    card = _card(realm)
    blk = card[card.index("Appointed"):][:600]
    assert "flex-direction:column" in blk


# --------------------------------------------------------------------------- the card's two columns

def test_the_week_strip_floats_rather_than_holding_a_column(realm):
    """As a third column it narrowed every line below it too, which broke a role title across two
    lines in a card with room to spare."""
    card = _card(realm)
    assert "float:right" in card
    i = card.index("float:right")
    assert card.index("width:11px;height:11px") > i, "the float does not wrap the strip"


def test_the_role_and_profile_run_the_full_column(realm):
    """They sit after the float in source order, so their lines reach past where it ends."""
    card = _card(realm)
    role = card.index("text-transform:uppercase")
    assert card.index("float:right") < role, "the strip must come first for the text to flow under it"


def test_everything_below_keeps_the_portrait_indent(realm):
    """Nothing runs to the card's left edge — the portrait column holds that whitespace open."""
    card = _card(realm)
    body = card.split('<div style="flex:none">', 1)[1]
    assert "float:right" in body, "the text column is no longer beside the portrait"
    assert "flex:1;min-width:0" in body


def test_the_appointment_is_not_in_the_footer_row(realm):
    card = _card(realm)
    footer = card[card.index("border-top:1px solid var(--color-divider)"):]
    assert "Appointed" not in footer, "the date is still competing with the tallies"


# --------------------------------------------------------------------------- the job action bar

def _job_page(realm):
    return P.render_job(reader.read(str(realm)), realm, "finance", "alpha")


def test_the_job_bar_is_sized_like_an_expanded_row(realm):
    """Same four actions, two views — they should not look like two products."""
    from armada.webui import agentframe as AF
    row = AF._tab_jobs(reader.read(str(realm)), realm, reader.read(str(realm)).agents[0],
                       datetime.date.today())
    bar = _job_page(realm).split("Back to jobs")[0]
    assert "btn-sm" in bar, "the bar still uses the larger buttons"      # small size, .btn-sm (UI audit B2)
    assert "btn-sm" in row


def test_delete_sits_in_the_line_not_at_the_far_edge(realm):
    bar = _job_page(realm)
    seg = bar[bar.index("Back to jobs"):][:900]
    assert "mcDeleteJobPage" in seg
    assert "margin-left:auto" not in seg, "delete is still pushed to the far edge"


def test_the_bar_keeps_all_four_actions(realm):
    bar = _job_page(realm)
    for token in ("mcSaveJob", "mcRunJob", "Back to jobs", "mcDeleteJobPage"):
        assert token in bar
