"""What the engine is told to withhold, and auto-discovery (used ⇒ listed at realm level).

These tests used to assert the permissive rule: a capability switched on for the realm was usable
by any agent, and only an explicit `enabled: false` withheld it. That is the behaviour the grant
model deliberately inverts — an agent gets what it was granted and nothing else — so they now pin
the new rule, including the case the old ones were really protecting: the coordinator.
"""
import json

from armada import capabilities as C
from armada import runner


def _realm(tmp_path, toolkit, agents=None):
    (tmp_path / "realm.json").write_text(json.dumps({"toolkit": toolkit}), encoding="utf-8")
    for aid, spec in (agents or {}).items():
        d = tmp_path / "agents" / aid
        d.mkdir(parents=True, exist_ok=True)
        (d / "agent.json").write_text(json.dumps({"id": aid, **spec}), encoding="utf-8")
    return tmp_path


def _agent(r, aid):
    return json.loads((r / "agents" / aid / "agent.json").read_text(encoding="utf-8"))


def test_an_agent_without_grants_is_denied_everything(tmp_path):
    """The inversion: being switched on for the realm is not permission to use it."""
    r = _realm(tmp_path, {"connectors": [{"id": "telegram", "enabled": True},
                                         {"id": "brightdata", "enabled": False}],
                          "plugins": [{"id": "nimble", "enabled": False}],
                          "skills": [{"id": "docx"}]},        # skills aren't MCP tools
               agents={"warren": {}})
    assert runner._disallowed_tools(r, _agent(r, "warren")) == [
        "mcp__brightdata", "mcp__nimble", "mcp__telegram"]


def test_a_granted_capability_is_allowed_through(tmp_path):
    r = _realm(tmp_path, {"connectors": [{"id": "telegram"}, {"id": "brightdata"}]},
               agents={"warren": {}})
    C.grant(r, "warren", "telegram")
    assert runner._disallowed_tools(r, _agent(r, "warren")) == ["mcp__brightdata"]


def test_the_coordinator_keeps_everything_the_realm_has_on(tmp_path):
    """The old 'enabled by default is not blocked' contract survives — for the role it was really
    describing."""
    r = _realm(tmp_path, {"connectors": [{"id": "telegram"},
                                         {"id": "brightdata", "enabled": False}]},
               agents={"hand": {"coordinator": True}})
    assert runner._disallowed_tools(r, _agent(r, "hand")) == ["mcp__brightdata"]


def test_skills_emit_no_denial_pattern(tmp_path):
    """No per-call MCP handle exists for a skill, so nothing is emitted rather than something that
    looks like enforcement and isn't."""
    r = _realm(tmp_path, {"skills": [{"id": "docx"}, {"id": "xlsx", "enabled": False}]},
               agents={"warren": {}})
    assert runner._disallowed_tools(r, _agent(r, "warren")) == []


def test_a_capability_with_no_id_cannot_be_denied_by_pattern(tmp_path):
    """Nothing to match on. It stays out of the agent's context instead."""
    r = _realm(tmp_path, {"connectors": [{"name": "Hand-added thing"}]}, agents={"warren": {}})
    assert runner._disallowed_tools(r, _agent(r, "warren")) == []


def test_record_used_adds_new_servers(tmp_path):
    r = _realm(tmp_path, {"connectors": []})
    runner._record_used_capabilities(r, ["mcp__github__search_issues", "Bash",
                                         "mcp__github__create_pr", "mcp__slack__post"])
    conns = json.loads((r / "realm.json").read_text(encoding="utf-8"))["toolkit"]["connectors"]
    assert {c["id"] for c in conns} == {"github", "slack"}
    assert all(c.get("discovered") for c in conns)


def test_record_used_skips_known(tmp_path):
    r = _realm(tmp_path, {"connectors": [{"id": "github", "name": "GitHub"}]})
    runner._record_used_capabilities(r, ["mcp__github__x"])
    conns = json.loads((r / "realm.json").read_text(encoding="utf-8"))["toolkit"]["connectors"]
    assert len(conns) == 1   # not duplicated


def test_discovery_lands_at_realm_level_and_grants_nobody(tmp_path):
    """Otherwise 'first use wins' becomes a way around the grant model, discovered by the owner
    only if they happen to notice a new row."""
    r = _realm(tmp_path, {"connectors": []}, agents={"warren": {}})
    runner._record_used_capabilities(r, ["mcp__slack__post"])
    assert C.find(r, "slack")[0] == "connectors"          # in the catalogue
    assert C.may_use(r, "warren", "slack") is False       # granted to nobody
    assert "mcp__slack" in runner._disallowed_tools(r, _agent(r, "warren"))
