"""An agent's own Capabilities tab, and the open-state of a card you drop an agent into.

Both were the same class of bug: the page said something that used to be true. The agent tab
claimed realm capabilities are inherited by every agent and listed the whole catalogue, so it and
the realm page disagreed about the same fact — the worse kind of wrong, because either one alone
looks authoritative.
"""
import json
from pathlib import Path

import pytest

from armada import capabilities as C
from armada import reader
from armada.webui import capabilities as UI

_CAPDRAG_JS = Path(UI.__file__).with_name("static").joinpath("js", "capdrag.js")


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "Cabinet-realm"
    (r / "agents").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({
        "name": "Cabinet", "owner": "M",
        "toolkit": {"connectors": [{"id": "ibkr", "name": "IBKR"}],
                    "extensions": [{"id": "filesystem", "name": "filesystem"},
                                   {"id": "windows-mcp", "name": "windows-mcp"}],
                    "skills": [], "plugins": []}}), encoding="utf-8")
    for aid, disp, coord in (("hand", "Marcus", True), ("finance", "Warren", False)):
        (r / "agents" / aid).mkdir(parents=True, exist_ok=True)
        (r / "agents" / aid / "agent.json").write_text(json.dumps(
            {"id": aid, "display": disp, "coordinator": coord, "role": "R"}), encoding="utf-8")
    return r


def _agent(r, aid):
    m = reader.read(str(r))
    return m, next(a for a in m.agents if a.id == aid)


# --------------------------------------------------------------------------- the agent tab

def test_the_inheritance_claim_is_gone(realm):
    m, a = _agent(realm, "finance")
    html = UI._tab_skills(m, realm, a)
    assert "inherited by every" not in html


def test_an_ungranted_agent_is_not_shown_capabilities_as_its_own(realm):
    """The reported bug: the tab listed the realm catalogue as though the agent had it."""
    m, a = _agent(realm, "finance")
    html = UI._tab_skills(m, realm, a)
    usable_part = html.split("In the realm, not available to")[0]
    for name in ("IBKR", "filesystem", "windows-mcp"):
        assert name not in usable_part, f"{name} listed as Warren's when it isn't"


def test_a_granted_capability_appears_as_the_agents_own(realm):
    C.grant(realm, "finance", "filesystem")
    m, a = _agent(realm, "finance")
    html = UI._tab_skills(m, realm, a)
    usable_part = html.split("In the realm, not available to")[0]
    assert "filesystem" in usable_part
    assert "windows-mcp" not in usable_part


def test_the_rest_of_the_realm_is_counted_but_not_listed(realm):
    """A first version listed everything the agent could NOT use. That restated the realm page in
    full on a page about one agent, so it's a count now — the number tells you there's more, the
    realm page is where it lives."""
    C.grant(realm, "finance", "filesystem")
    m, a = _agent(realm, "finance")
    html = UI._tab_skills(m, realm, a)
    assert "<b>1</b> of <b>3</b>" in html
    assert "IBKR" not in html and "windows-mcp" not in html


def test_the_count_matches_the_grant_model(realm):
    C.grant(realm, "finance", "filesystem")
    m, a = _agent(realm, "finance")
    html = UI._tab_skills(m, realm, a)
    assert "<b>1</b> of <b>3</b>" in html


def test_the_coordinator_tab_explains_the_role_instead(realm):
    m, a = _agent(realm, "hand")
    html = UI._tab_skills(m, realm, a)
    assert "can use every capability in the realm" in html
    assert "In the realm, not available to" not in html
    for name in ("IBKR", "filesystem", "windows-mcp"):
        assert name in html


def test_the_tab_points_at_where_access_is_changed(realm):
    m, a = _agent(realm, "finance")
    assert 'href="/skills"' in UI._tab_skills(m, realm, a)


def test_agent_tab_cards_carry_no_availability_column(realm):
    """That column belongs on the realm page, where the roster is. Here it would be noise."""
    C.grant(realm, "finance", "filesystem")
    m, a = _agent(realm, "finance")
    html = UI._tab_skills(m, realm, a)
    assert "mcCapDrop" not in html


# --------------------------------------------------------------------------- open state

def test_a_drop_preserves_which_cards_were_open(realm):
    """Granting reloads the page, which closed the card you had just dropped into."""
    html = UI._realm_skills(reader.read(str(realm)), realm)
    assert "/static/js/capdrag.js" in html, "the page must load the script that defines these"
    js = _CAPDRAG_JS.read_text(encoding="utf-8")
    assert "mcCapSaveOpen" in js and "mcCapRestoreOpen" in js
    drop = js.split("async function mcCapDrop")[1].split("async function")[0]
    # captured synchronously, before the fetch, so nothing in between can change it
    assert drop.index("mcCapSaveOpen()") < drop.index("fetch(")


def test_removing_an_agent_preserves_it_too(realm):
    js = _CAPDRAG_JS.read_text(encoding="utf-8")
    rm = js.split("async function mcCapRemoveAgent")[1]
    assert rm.index("mcCapSaveOpen()") < rm.index("fetch(")


def test_the_restore_is_one_shot(realm):
    """Persisting open state across ordinary navigation would be a different, surprising feature."""
    js = _CAPDRAG_JS.read_text(encoding="utf-8")
    fn = js.split("function mcCapRestoreOpen")[1].split("function ")[0]
    assert "removeItem" in fn


def test_cards_are_keyed_so_they_can_be_reopened(realm):
    html = UI._realm_skills(reader.read(str(realm)), realm)
    assert 'data-cap="filesystem"' in html and 'data-kind="extensions"' in html
