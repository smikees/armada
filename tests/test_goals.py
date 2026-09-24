"""Goals: CRUD, agent mapping (coordinator always mapped), and core-context injection."""
from armada import goals, memory


def _mk_realm(tmp_path):
    (tmp_path / "goals").mkdir()
    for aid in ("marcus", "warren", "steve"):
        (tmp_path / "agents" / aid / "memory").mkdir(parents=True)
    return tmp_path


def test_save_list_and_fields(tmp_path):
    _mk_realm(tmp_path)
    stem = goals.save_goal(tmp_path, title="Build a six-month emergency fund",
                           body="Grow liquid + property to the target.",
                           status="On track", target="2026-12-31")
    gs = goals.list_goals(tmp_path)
    assert len(gs) == 1
    g = gs[0]
    assert g["stem"] == stem
    assert g["title"] == "Build a six-month emergency fund"
    assert g["status"] == "On track"
    assert g["target"] == "2026-12-31"
    assert "Dec 2026" in g["target_label"]
    assert g["agents"] == []          # no members mapped yet


def test_agent_mapping_toggle_and_coordinator(tmp_path):
    _mk_realm(tmp_path)
    stem = goals.save_goal(tmp_path, title="Ship V1", body="", status="On track")
    goals.set_agents(tmp_path, stem, ["warren"])
    assert goals.list_goals(tmp_path)[0]["agents"] == ["warren"]

    # mapped member sees it; unmapped member does not
    assert len(goals.goals_for_agent(tmp_path, "warren", is_coord=False)) == 1
    assert goals.goals_for_agent(tmp_path, "steve", is_coord=False) == []
    # coordinator sees every goal regardless of the stored mapping
    assert len(goals.goals_for_agent(tmp_path, "marcus", is_coord=True)) == 1


def test_edit_preserves_agents(tmp_path):
    _mk_realm(tmp_path)
    stem = goals.save_goal(tmp_path, title="Land", body="buy", status="On track")
    goals.set_agents(tmp_path, stem, ["warren"])
    # editing title/status/body without passing agents must keep the mapping
    goals.save_goal(tmp_path, title="Land + home", body="buy then build",
                    status="At risk", stem=stem)
    g = goals.list_goals(tmp_path)[0]
    assert g["title"] == "Land + home" and g["status"] == "At risk"
    assert g["agents"] == ["warren"]


def test_overdue_forces_at_risk(tmp_path):
    _mk_realm(tmp_path)
    goals.save_goal(tmp_path, title="Past due", body="x", status="On track", target="2000-01-01")
    g = goals.list_goals(tmp_path)[0]
    assert g["overdue"] is True
    assert g["effective_status"] == "At risk"     # past ETA overrides the stored status
    assert g["status"] == "On track"              # stored status is untouched
    # a Done goal is never forced to At risk, even if its ETA is in the past
    goals.save_goal(tmp_path, title="Past due", body="x", status="Done", target="2000-01-01", stem=g["stem"])
    g2 = goals.list_goals(tmp_path)[0]
    assert g2["overdue"] is True and g2["effective_status"] == "Done"


def test_save_goal_with_agents_auto_owner(tmp_path):
    # goals added from an agent's Goals page pass agents=[that agent] so it's auto-mapped
    _mk_realm(tmp_path)
    stem = goals.save_goal(tmp_path, title="Learn Spanish", body="", agents=["warren"])
    assert goals.list_goals(tmp_path)[0]["agents"] == ["warren"]
    assert len(goals.goals_for_agent(tmp_path, "warren")) == 1


def test_delete(tmp_path):
    _mk_realm(tmp_path)
    stem = goals.save_goal(tmp_path, title="Temp", body="x")
    assert goals.delete_goal(tmp_path, stem) is True
    assert goals.list_goals(tmp_path) == []
    assert goals.delete_goal(tmp_path, stem) is False


def test_assemble_core_injects_mapped_goals(tmp_path):
    _mk_realm(tmp_path)
    stem = goals.save_goal(tmp_path, title="Emergency fund", body="detail",
                           status="On track", target="2026-12-31")
    goals.set_agents(tmp_path, stem, ["warren"])

    warren_core = memory.assemble_core(tmp_path, tmp_path / "agents" / "warren", {})
    assert "Goals you advance" in warren_core and "Emergency fund" in warren_core
    assert "On track" in warren_core

    # unmapped, non-coordinator agent: no detailed goals section (the all-goals overview lives in the
    # shared System memory, which a bare test realm doesn't have)
    steve_core = memory.assemble_core(tmp_path, tmp_path / "agents" / "steve", {})
    assert "Goals you advance" not in steve_core
    assert "Emergency fund" not in steve_core

    # coordinator gets all goals even without being in the mapping
    marcus_core = memory.assemble_core(tmp_path, tmp_path / "agents" / "marcus",
                                       {"coordinator": True})
    assert "Emergency fund" in marcus_core
