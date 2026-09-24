"""Who may use which capability.

The rule: the realm holds the catalogue, a coordinator may use all of it, everyone else may use
only what they have been granted, and everyone can SEE all of it so they know what to ask for.

The inversion this encodes is the important part. Before, an empty agent toolkit meant "inherit
everything" and only a realm-wide off switch could stop an agent. Empty now means nothing.
"""
import json

import pytest

from armada import capabilities as C
from armada import runner


def _realm(tmp_path, cat=None, agents=None):
    r = tmp_path / "realm"
    (r / "agents").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({
        "name": "R",
        "toolkit": cat if cat is not None else {
            "connectors": [{"id": "ibkr", "name": "IBKR"}],
            "extensions": [{"id": "windows-mcp", "name": "windows-mcp"},
                           {"id": "filesystem", "name": "filesystem"}],
            "skills": [{"id": "xlsx", "name": "xlsx"}],
            "plugins": [],
        }}), encoding="utf-8")
    for aid, spec in (agents or {"hand": {"coordinator": True}, "warren": {}}).items():
        (r / "agents" / aid).mkdir(parents=True, exist_ok=True)
        (r / "agents" / aid / "agent.json").write_text(
            json.dumps({"id": aid, "display": aid.title(), **spec}), encoding="utf-8")
    return r


def _names(inv):
    return sorted(c.get("name") for k in C.KINDS for c in inv[k])


# --------------------------------------------------------------------------- the catalogue

def test_the_realm_holds_everything(tmp_path):
    r = _realm(tmp_path)
    assert _names(C.catalogue(r)) == ["IBKR", "filesystem", "windows-mcp", "xlsx"]


def test_find_locates_by_id_or_name_case_insensitively(tmp_path):
    r = _realm(tmp_path)
    assert C.find(r, "windows-mcp")[0] == "extensions"
    assert C.find(r, "IBKR")[0] == "connectors"
    assert C.find(r, "ibkr")[0] == "connectors"
    assert C.find(r, "nope") == (None, None)


# --------------------------------------------------------------------------- the coordinator

def test_the_coordinator_may_use_the_whole_catalogue(tmp_path):
    r = _realm(tmp_path)
    assert _names(C.usable(r, "hand")) == ["IBKR", "filesystem", "windows-mcp", "xlsx"]


def test_a_realm_wide_off_switch_beats_even_the_coordinator(tmp_path):
    r = _realm(tmp_path, cat={"connectors": [{"id": "ibkr", "name": "IBKR", "enabled": False}],
                              "extensions": [], "skills": [], "plugins": []})
    assert _names(C.usable(r, "hand")) == []


def test_no_coordinator_means_nobody_inherits_everything(tmp_path):
    r = _realm(tmp_path, agents={"warren": {}, "galen": {}})
    assert C.has_coordinator(r) is False
    assert _names(C.usable(r, "warren")) == []
    assert _names(C.usable(r, "galen")) == []


# --------------------------------------------------------------------------- ordinary agents

def test_an_agent_with_no_grants_may_use_nothing(tmp_path):
    """The inversion. This test is the whole point of the change."""
    r = _realm(tmp_path)
    assert _names(C.usable(r, "warren")) == []


def test_a_grant_makes_exactly_one_capability_usable(tmp_path):
    r = _realm(tmp_path)
    assert C.grant(r, "warren", "filesystem")["ok"]
    assert _names(C.usable(r, "warren")) == ["filesystem"]
    assert C.may_use(r, "warren", "filesystem") is True
    assert C.may_use(r, "warren", "windows-mcp") is False


def test_granting_twice_is_harmless(tmp_path):
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem")
    assert C.grant(r, "warren", "filesystem").get("already") is True
    assert len(C.grants(r, "warren")["extensions"]) == 1


def test_a_grant_cannot_invent_a_capability(tmp_path):
    r = _realm(tmp_path)
    assert C.grant(r, "warren", "does-not-exist")["ok"] is False
    assert _names(C.usable(r, "warren")) == []


def test_a_grant_cannot_revive_a_realm_wide_off(tmp_path):
    r = _realm(tmp_path, cat={"connectors": [], "extensions": [
        {"id": "windows-mcp", "name": "windows-mcp", "enabled": False}], "skills": [], "plugins": []})
    assert C.grant(r, "warren", "windows-mcp")["ok"] is False


def test_revoke_takes_it_away(tmp_path):
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem")
    assert C.revoke(r, "warren", "filesystem")["ok"]
    assert C.may_use(r, "warren", "filesystem") is False


def test_the_coordinator_cannot_be_revoked_piecemeal(tmp_path):
    """Its access follows the role; a per-capability revoke would silently do nothing."""
    r = _realm(tmp_path)
    res = C.revoke(r, "hand", "filesystem")
    assert res["ok"] is False and "coordinator" in res["error"].lower()


def test_usable_reports_the_realms_current_entry_not_a_stale_copy(tmp_path):
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem")
    cfg = json.loads((r / "realm.json").read_text(encoding="utf-8"))
    for e in cfg["toolkit"]["extensions"]:
        if e["id"] == "filesystem":
            e["description"] = "scoped to Work2"
    (r / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    fs = [c for c in C.usable(r, "warren")["extensions"] if c["id"] == "filesystem"][0]
    assert fs["description"] == "scoped to Work2"


# --------------------------------------------------------------------------- visibility

def test_everyone_sees_the_whole_catalogue(tmp_path):
    """An agent that can't know a tool exists can't ask for it."""
    r = _realm(tmp_path)
    assert _names(C.visible(r, "warren")) == ["IBKR", "filesystem", "windows-mcp", "xlsx"]


def test_requestable_is_what_is_visible_but_not_usable(tmp_path):
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem")
    assert _names(C.requestable(r, "warren")) == ["IBKR", "windows-mcp", "xlsx"]


def test_the_coordinator_has_nothing_to_request(tmp_path):
    r = _realm(tmp_path)
    assert _names(C.requestable(r, "hand")) == []


# --------------------------------------------------------------------------- enforcement

def test_ungranted_mcp_capabilities_are_denied_at_the_engine(tmp_path):
    r = _realm(tmp_path)
    pats = C.denied_tool_patterns(r, json.loads(
        (r / "agents" / "warren" / "agent.json").read_text(encoding="utf-8")))
    assert pats == ["mcp__filesystem", "mcp__ibkr", "mcp__windows-mcp"]


def test_a_granted_capability_is_not_denied(tmp_path):
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem")
    a = json.loads((r / "agents" / "warren" / "agent.json").read_text(encoding="utf-8"))
    assert "mcp__filesystem" not in C.denied_tool_patterns(r, a)
    assert "mcp__windows-mcp" in C.denied_tool_patterns(r, a)


def test_the_coordinator_is_denied_only_what_the_realm_switched_off(tmp_path):
    r = _realm(tmp_path, cat={"connectors": [{"id": "ibkr", "name": "IBKR", "enabled": False}],
                              "extensions": [{"id": "filesystem", "name": "filesystem"}],
                              "skills": [], "plugins": []})
    a = json.loads((r / "agents" / "hand" / "agent.json").read_text(encoding="utf-8"))
    assert C.denied_tool_patterns(r, a) == ["mcp__ibkr"]


def test_skills_are_not_claimed_to_be_enforced(tmp_path):
    """Skills have no per-call MCP handle, so no pattern is emitted for one. The module says so;
    this pins it, because a silent half-enforcement would be worse than none."""
    r = _realm(tmp_path)
    assert not any("xlsx" in p for p in C.denied_tool_patterns(r, {"id": "warren"}))


def test_the_runner_uses_the_grant_model(tmp_path):
    r = _realm(tmp_path)
    a = json.loads((r / "agents" / "warren" / "agent.json").read_text(encoding="utf-8"))
    assert runner._disallowed_tools(r, a) == C.denied_tool_patterns(r, a)


# --------------------------------------------------------------------------- what agents are told

def test_the_context_separates_mine_from_the_realms(tmp_path):
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem")
    txt = runner._capabilities_context(r, r / "agents" / "warren")
    assert "[Your capabilities" in txt and "filesystem" in txt
    assert "you may NOT use these yet" in txt
    assert "windows-mcp" in txt.split("you may NOT use these yet")[1]


def test_an_agent_with_nothing_is_told_so_plainly(tmp_path):
    r = _realm(tmp_path)
    txt = runner._capabilities_context(r, r / "agents" / "warren")
    assert "None yet" in txt


def test_the_context_tells_the_agent_how_to_ask(tmp_path):
    r = _realm(tmp_path)
    txt = runner._capabilities_context(r, r / "agents" / "warren")
    assert C.REQUESTS_DIR in txt and "reason" in txt
    assert "Do NOT attempt to use one" in txt


def test_the_coordinator_gets_no_request_instructions(tmp_path):
    """Nothing to ask for, so the paragraph would be noise it might act on anyway."""
    r = _realm(tmp_path)
    txt = runner._capabilities_context(r, r / "agents" / "hand")
    assert "you may NOT use these yet" not in txt


# --------------------------------------------------------------------------- requests

def test_a_request_grants_nothing_by_itself(tmp_path):
    r = _realm(tmp_path)
    assert C.request(r, "warren", "filesystem", "need to read the CSVs", thread="main")["ok"]
    assert C.may_use(r, "warren", "filesystem") is False
    assert C.count_requests(r) == 1


def test_approving_a_request_grants_it_and_remembers_the_thread(tmp_path):
    r = _realm(tmp_path)
    C.request(r, "warren", "filesystem", "reason", thread="taxes")
    res = C.approve_request(r, "warren", "filesystem")
    assert res["ok"] and C.may_use(r, "warren", "filesystem") is True
    assert C.granted_in_thread(r, "warren", "filesystem", "taxes") is True
    assert C.granted_in_thread(r, "warren", "filesystem", "main") is False
    assert C.count_requests(r) == 0


def test_a_capability_granted_by_the_owner_is_not_new_to_any_thread(tmp_path):
    """The badge distinguishes 'just gained this here' from 'already had it'."""
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem", via="user")
    assert C.granted_in_thread(r, "warren", "filesystem", "main") is False


def test_rejecting_a_request_removes_it_and_grants_nothing(tmp_path):
    r = _realm(tmp_path)
    C.request(r, "warren", "filesystem", "reason", thread="main")
    assert C.reject_request(r, "warren", "filesystem")["ok"]
    assert C.count_requests(r) == 0 and C.may_use(r, "warren", "filesystem") is False


def test_requesting_something_already_held_is_a_no_op(tmp_path):
    r = _realm(tmp_path)
    C.grant(r, "warren", "filesystem")
    assert C.request(r, "warren", "filesystem", "x").get("already") is True
    assert C.count_requests(r) == 0


def test_a_request_for_an_unknown_capability_is_refused(tmp_path):
    r = _realm(tmp_path)
    assert C.request(r, "warren", "made-up", "x")["ok"] is False
    assert C.count_requests(r) == 0
