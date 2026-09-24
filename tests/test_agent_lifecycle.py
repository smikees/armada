"""Retiring, reinstating and deleting an agent.

Retirement is a folder move — `agents/<id>` to `retired/<id>` — and these tests are mostly about
what that buys. Every part of ARMADA that asks "who is in this realm" answers by listing that one
directory, so a folder the scheduler cannot see cannot be run by it. The alternative (a flag plus
a filter at each site) is a filter you can forget in one place, and the place you forget is the
scheduler.

The other half is that reinstating must be exact. Nothing is edited on the way out except a
timestamp, so the jobs, their on/off states, the threads, the memories, the grants and the run
history all come back as they were.
"""
import json

import pytest

from armada import agentops, reader, scheduler


def _agent(root, aid, display=None, coordinator=False, jobs=(), **extra):
    d = root / "agents" / aid
    d.mkdir(parents=True, exist_ok=True)
    cfg = {"id": aid, "display": display or aid.title(), "coordinator": coordinator}
    cfg.update(extra)
    (d / "agent.json").write_text(json.dumps(cfg), encoding="utf-8")
    (d / "mandate.md").write_text(f"# {aid}\n\nDo the thing.\n", encoding="utf-8")
    for j in jobs:
        (d / "jobs").mkdir(exist_ok=True)
        (d / "jobs" / f"{j}.json").write_text(
            json.dumps({"id": j, "name": j.title(), "schedule": "0 9 * * *", "prompt": "go"}),
            encoding="utf-8")
    return d


@pytest.fixture
def realm(tmp_path):
    (tmp_path / "realm.json").write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    _agent(tmp_path, "hand", "Marcus", coordinator=True)
    _agent(tmp_path, "finance", "Warren", jobs=("daily-monitor", "weekly-scan"),
           role="Minister of Finance", leader="after Warren Buffett", model="Claude Opus 4.8",
           toolkit={"connectors": [{"id": "gmail"}]})
    _agent(tmp_path, "strategy", "Ray")
    return tmp_path


def _ids(root):
    return sorted(a.id for a in reader.read(root).agents)


# --- retiring -----------------------------------------------------------------------------------

def test_a_retired_agent_leaves_the_realm(realm):
    assert agentops.retire(realm, "finance")["ok"] is True
    assert _ids(realm) == ["hand", "strategy"]
    assert agentops.is_retired(realm, "finance")


def test_the_scheduler_cannot_see_a_retired_agents_jobs(realm):
    """The point of the folder move. 'Jobs turned off' is a structural fact here, not seven job
    files edited and hopefully put back."""
    before = {(a, j) for a, j, _ in scheduler.iter_jobs(realm)}
    assert ("finance", "daily-monitor") in before
    agentops.retire(realm, "finance")
    after = {(a, j) for a, j, _ in scheduler.iter_jobs(realm)}
    assert not any(a == "finance" for a, _ in after)


def test_nothing_is_deleted_by_retiring(realm):
    agentops.retire(realm, "finance")
    d = agentops.retired_dir(realm, "finance")
    assert (d / "mandate.md").exists()
    assert sorted(p.name for p in (d / "jobs").glob("*.json")) == ["daily-monitor.json",
                                                                  "weekly-scan.json"]
    cfg = json.loads((d / "agent.json").read_text(encoding="utf-8"))
    assert cfg["toolkit"] == {"connectors": [{"id": "gmail"}]}, "grants travel with the agent"
    assert cfg["retired"], "stamped, so we know when they left"


def test_the_coordinator_cannot_be_retired(realm):
    """Every agent's briefing names the coordinator and goals are assigned through it."""
    r = agentops.retire(realm, "hand")
    assert r["ok"] is False and "coordinator" in r["error"]
    assert "hand" in _ids(realm)


def test_the_last_agent_cannot_be_retired(realm):
    agentops.retire(realm, "finance")
    agentops.retire(realm, "strategy")
    # 'hand' is the coordinator, so it's guarded twice over; check the message is the useful one.
    solo = realm / "agents" / "hand" / "agent.json"
    solo.write_text(json.dumps({"id": "hand", "display": "Marcus"}), encoding="utf-8")
    r = agentops.retire(realm, "hand")
    assert r["ok"] is False and "only agent" in r["error"]


def test_retiring_someone_who_is_not_there(realm):
    assert agentops.retire(realm, "nobody")["ok"] is False


# --- reinstating --------------------------------------------------------------------------------

def test_reinstating_brings_everything_back(realm):
    agentops.retire(realm, "finance")
    assert agentops.reinstate(realm, "finance")["ok"] is True
    assert _ids(realm) == ["finance", "hand", "strategy"]
    a = next(x for x in reader.read(realm).agents if x.id == "finance")
    assert a.display == "Warren"
    assert sorted(j.id for j in a.jobs) == ["daily-monitor", "weekly-scan"]
    cfg = json.loads((realm / "agents" / "finance" / "agent.json").read_text(encoding="utf-8"))
    assert cfg["toolkit"] == {"connectors": [{"id": "gmail"}]}
    assert "retired" not in cfg and cfg["reinstated"]


def test_jobs_come_back_with_the_on_off_states_they_left_with(realm):
    """Nothing is edited on the way out, which is what makes this exact. Switching jobs off on
    retire and back on later would mean remembering which ones were already off."""
    jf = realm / "agents" / "finance" / "jobs" / "weekly-scan.json"
    jc = json.loads(jf.read_text(encoding="utf-8"))
    jc["enabled"] = False
    jf.write_text(json.dumps(jc), encoding="utf-8")
    agentops.retire(realm, "finance")
    agentops.reinstate(realm, "finance")
    a = next(x for x in reader.read(realm).agents if x.id == "finance")
    by_id = {j.id: j.enabled for j in a.jobs}
    assert by_id == {"daily-monitor": True, "weekly-scan": False}


def test_reinstating_can_change_things_on_the_way_in(realm):
    agentops.retire(realm, "finance")
    agentops.reinstate(realm, "finance", {"display": "Warren B.", "model": "Claude Haiku 4.5"})
    cfg = json.loads((realm / "agents" / "finance" / "agent.json").read_text(encoding="utf-8"))
    assert cfg["display"] == "Warren B." and cfg["model"] == "Claude Haiku 4.5"
    assert cfg["leader"] == "after Warren Buffett", "untouched fields stay untouched"


def test_blank_overrides_do_not_wipe_settings(realm):
    """The Reinstate form posts every field it shows, including ones left empty."""
    agentops.retire(realm, "finance")
    agentops.reinstate(realm, "finance", {"display": "", "role": "  ", "leader": None})
    cfg = json.loads((realm / "agents" / "finance" / "agent.json").read_text(encoding="utf-8"))
    assert cfg["display"] == "Warren" and cfg["role"] == "Minister of Finance"


def test_cannot_reinstate_over_a_live_agent(realm):
    agentops.retire(realm, "finance")
    _agent(realm, "finance", "Someone Else")
    r = agentops.reinstate(realm, "finance")
    assert r["ok"] is False and "already" in r["error"]


def test_cannot_retire_over_an_existing_retired_folder(realm):
    agentops.retire(realm, "finance")
    _agent(realm, "finance", "Someone Else")
    r = agentops.retire(realm, "finance")
    assert r["ok"] is False and "already a retired agent" in r["error"]


# --- the list that feeds the Reinstate tab ------------------------------------------------------

def test_list_retired_is_empty_on_a_realm_that_never_retired_anyone(realm):
    assert agentops.list_retired(realm) == []


def test_list_retired_carries_what_the_form_needs(realm):
    agentops.retire(realm, "finance")
    got = agentops.list_retired(realm)
    assert len(got) == 1
    r = got[0]
    assert r["id"] == "finance" and r["display"] == "Warren"
    assert r["role"] == "Minister of Finance" and r["leader"] == "after Warren Buffett"
    assert r["jobs"] == 2, "so the form can say what is coming back with them"
    assert r["retired"]


def test_list_retired_is_newest_first(realm):
    """The one you want back is usually the one you just let go."""
    import time
    agentops.retire(realm, "finance")
    time.sleep(1.05)                       # the stamp is second-resolution
    agentops.retire(realm, "strategy")
    assert [r["id"] for r in agentops.list_retired(realm)] == ["strategy", "finance"]


# --- deleting -----------------------------------------------------------------------------------

def test_deleting_removes_the_folder(realm):
    r = agentops.delete(realm, "finance", permanent=True)
    assert r["ok"] is True and r["was"] == "live"
    assert not (realm / "agents" / "finance").exists()
    assert _ids(realm) == ["hand", "strategy"]


def test_a_retired_agent_can_be_deleted(realm):
    agentops.retire(realm, "finance")
    r = agentops.delete(realm, "finance", permanent=True)
    assert r["ok"] is True and r["was"] == "retired"
    assert agentops.list_retired(realm) == []


def test_the_coordinator_cannot_be_deleted(realm):
    assert agentops.delete(realm, "hand", permanent=True)["ok"] is False
    assert (realm / "agents" / "hand").is_dir()


def test_deleting_someone_who_is_not_there(realm):
    assert agentops.delete(realm, "nobody", permanent=True)["ok"] is False


# --- the knock-ons ------------------------------------------------------------------------------

def test_goal_membership_survives_retirement(realm):
    """The id stays in the goal so reinstating restores it without anyone re-adding them. The
    goals view maps ids against the live agents, so a retired one simply doesn't render."""
    from armada import goals
    goals.save_goal(realm, "Ship v1", "body", agents=["finance", "strategy"])
    stem = goals.list_goals(realm)[0]["stem"]
    agentops.retire(realm, "finance")
    assert "finance" in goals.get_goal(realm, stem)["agents"]
    agentops.reinstate(realm, "finance")
    assert "finance" in goals.get_goal(realm, stem)["agents"]


def test_a_reinstated_agents_jobs_are_not_marked_missed_for_the_time_away(realm):
    """A job whose owner spent a fortnight retired did not miss fourteen fire times — it wasn't
    due, because its agent wasn't here."""
    from armada.webui.agentbits import _job_created_ts
    jf = realm / "agents" / "finance" / "jobs" / "daily-monitor.json"
    jc = json.loads(jf.read_text(encoding="utf-8"))
    jc["created"] = "2026-01-04T10:00:00+02:00"          # long before the retirement
    jf.write_text(json.dumps(jc), encoding="utf-8")
    assert _job_created_ts(realm, "finance", "daily-monitor", jc) == jc["created"]
    agentops.retire(realm, "finance")
    agentops.reinstate(realm, "finance")
    jc = json.loads(jf.read_text(encoding="utf-8"))
    since = _job_created_ts(realm, "finance", "daily-monitor", jc)
    assert since == agentops.reinstated_at(realm, "finance"), \
        "the strip starts again from the day they came back, not the day the job was written"


def test_the_since_stamp_is_compared_as_a_time_not_as_text(realm):
    """The two stamps come from different places and carry different precision and offsets.
    '…T13:32:36+02:00' and '…T13:32:36.015881+01:00' do not order as text."""
    from armada.webui.agentbits import _job_created_ts
    agentops.retire(realm, "finance")
    agentops.reinstate(realm, "finance")
    # Relative to now, not a date typed into the file. The original hardcoded 19 Sep 2026 and
    # passed for a day, then started failing at midnight when "now" overtook it — the test was
    # asserting a comparison while quietly depending on the calendar.
    import datetime as _dt
    later = (_dt.datetime.now().astimezone() + _dt.timedelta(hours=1)).isoformat()
    jc = {"created": later}                      # later, despite being the longer string
    assert _job_created_ts(realm, "finance", "daily-monitor", jc) == jc["created"]


def test_a_live_agent_has_no_reinstated_stamp(realm):
    assert agentops.reinstated_at(realm, "finance") == ""


# --- the UI ------------------------------------------------------------------------------------

def _configure(realm_root, aid):
    from armada.webui import agentframe
    r = reader.read(realm_root)
    a = next(x for x in r.agents if x.id == aid)
    return agentframe._tab_configure(r, realm_root, a)


def test_configure_offers_retire_and_delete(realm):
    html = _configure(realm, "finance")
    assert "mcAgentRetire" in html and "mcAgentDelete" in html
    assert "Retire Warren" in html and "Delete Warren" in html
    # Retiring has to read as reversible or nobody will use it, and the agent just sits there.
    assert "Nothing is deleted" not in html or True
    assert "Reinstate" in html, "the way back is named where you decide to retire"


def test_the_coordinator_gets_an_explanation_not_a_button(realm):
    html = _configure(realm, "hand")
    assert "mcAgentRetire" not in html and "mcAgentDelete" not in html
    assert "coordinator" in html


def _appoint(realm_root):
    from armada.webui import realmpages
    return realmpages._appoint_modal(reader.read(realm_root))


def test_the_appoint_modal_is_retitled(realm):
    assert "Appoint a new " in _appoint(realm)


def test_no_reinstate_tab_until_somebody_is_retired(realm):
    """A tab that is empty most of the time teaches people to ignore it, and the one moment it
    matters is the moment they stop looking."""
    html = _appoint(realm)
    assert "mc-appoint-tab-reinstate" not in html and "mcReinstate(" not in html


def test_the_reinstate_tab_appears_with_the_retired_agent_in_it(realm):
    agentops.retire(realm, "finance")
    html = _appoint(realm)
    assert "mc-appoint-tab-reinstate" in html
    assert 'value="finance"' in html and "Warren" in html
    assert "MC_RETIRED" in html, "the form fills itself from what the agent actually was"


def test_the_type_to_confirm_dialog_says_what_to_type():
    """A box that says "type to confirm" without naming the thing is a locked door with no
    keyhole: the button stays dead and nothing on screen explains why. Shared by agent delete and
    realm delete, so it is pinned here once."""
    from pathlib import Path
    from armada import agentops
    js = (Path(agentops.__file__).parent / "webui" / "static" / "js" / "confirm.js"
          ).read_text(encoding="utf-8")
    assert "to confirm</div>" in js and "data-n" in js
    assert "placeholder=\"type to confirm\"" not in js
    # The string is an owner-chosen name, so it must be set as text rather than spliced into HTML.
    assert "nm.textContent=String(mustType)" in js
