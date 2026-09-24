"""The coordinator wears one mark, in every place that names an agent.

It used to be the word "coordinator" in a pill on the minister card and nowhere else — so the
role was invisible on the Register, on the agent page and in the threads header, and where it did
show it spent the width of a word on a fact about the agent that the name column already wanted.
"""
import json

import pytest

from armada import reader
from armada.icons import ICONS, _icon
from armada.webui import agentbits as AB, agentframe as AF, realmpages as R, widgets as W


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "realm"
    root.mkdir()
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    for aid, disp, coord in (("marcus", "Marcus", True), ("warren", "Warren", False)):
        d = root / "agents" / aid
        d.mkdir(parents=True)
        (d / "agent.json").write_text(json.dumps(
            {"id": aid, "display": disp, "coordinator": coord, "role": "Strategy"}),
            encoding="utf-8")
    return root


def _agents(realm):
    r = reader.read(str(realm))
    return r, {a.id: a for a in r.agents}


def test_the_icon_exists_and_is_drawn():
    assert ICONS.get("laurel"), "the laurel is missing from the registry"
    assert "<svg" in _icon("laurel", 16)


def test_the_mark_says_what_it_means():
    """An unexplained glyph is a worse label than the word it replaced."""
    assert 'title="Coordinator agent"' in AB._coord_mark()


def test_the_agent_page_header_marks_the_coordinator(realm):
    r, by_id = _agents(realm)
    head = AF._agent_header(r, realm, by_id["marcus"])
    assert 'title="Coordinator agent"' in head


def test_an_ordinary_agent_carries_no_mark(realm):
    r, by_id = _agents(realm)
    assert 'title="Coordinator agent"' not in AF._agent_header(r, realm, by_id["warren"])


def test_the_register_row_marks_the_coordinator(realm):
    import datetime
    r, by_id = _agents(realm)
    row = W._reg_row(by_id["marcus"], realm, datetime.date.today(), coord=True, realm=r)
    assert 'title="Coordinator agent"' in row
    plain = W._reg_row(by_id["warren"], realm, datetime.date.today(), coord=False, realm=r)
    assert 'title="Coordinator agent"' not in plain


def test_the_minister_card_uses_the_mark_not_the_word(realm):
    import datetime
    r, _ = _agents(realm)
    cards = R._realm_ministers(r, realm, datetime.date.today())
    assert 'title="Coordinator agent"' in cards
    assert ">coordinator</span>" not in cards, "the old word-shaped pill is still there"


def test_the_appoint_modal_shows_the_mark_beside_the_checkbox(realm):
    """So the mark is learnable where you set it, not only where it appears."""
    r, _ = _agents(realm)
    form = R._new_agent_form(r, "")
    assert "Is coordinator" in form
    assert 'title="Coordinator agent"' in form
