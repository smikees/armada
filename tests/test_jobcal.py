"""Job-calendar event projection: scheduled/missed/success resolution from schedule + runs."""
import json, datetime
from pathlib import Path
from armada import webui
from armada.model import Realm, Agent, Job


def _mk_realm(tmp_path, runs):
    """One coordinator agent 'hand' with a daily 09:00 job; write given run records."""
    a = Agent(id="hand", display="Marcus", is_coordinator=True,
              jobs=[Job(id="brief", name="Daily Brief", cadence="daily 09:00", report_task="hand-brief")])
    realm = Realm(name="Test", root=str(tmp_path), agents=[a])
    rdir = tmp_path / "agents" / "hand" / "runs"
    rdir.mkdir(parents=True)
    (rdir / "hand.jsonl").write_text(
        "\n".join(json.dumps(r) for r in runs), encoding="utf-8")
    return realm


# anchor to real "now" (the code uses datetime.now() for the past/future cutoff)
TODAY = datetime.date.today()
PAST = TODAY - datetime.timedelta(days=3)
FUTURE = TODAY + datetime.timedelta(days=10)


def test_future_is_scheduled(tmp_path):
    realm = _mk_realm(tmp_path, [])
    evs = webui._jobcal_events(realm, tmp_path, FUTURE, FUTURE + datetime.timedelta(days=1))
    assert evs and all(e["status"] == "scheduled" for e in evs)
    assert all(e["job"] == "brief" and e["agent"] == "hand" for e in evs)


def test_past_success_from_run(tmp_path):
    realm = _mk_realm(tmp_path, [
        {"ts": PAST.isoformat() + "T09:00:00", "task": "hand-brief", "status": "ok"}])
    evs = webui._jobcal_events(realm, tmp_path, PAST, PAST)
    slot = [e for e in evs if e["ts"].startswith(PAST.isoformat())]
    assert slot and slot[0]["status"] == "success"


def test_past_missing_run_is_missed(tmp_path):
    realm = _mk_realm(tmp_path, [])
    evs = webui._jobcal_events(realm, tmp_path, PAST, PAST)
    assert evs and evs[0]["status"] == "missed"


def test_failed_run_maps_to_failed(tmp_path):
    realm = _mk_realm(tmp_path, [
        {"ts": PAST.isoformat() + "T09:00:00", "task": "hand-brief", "status": "error"}])
    evs = webui._jobcal_events(realm, tmp_path, PAST, PAST)
    assert any(e["status"] == "failed" for e in evs)


def test_norm_status():
    assert webui._jc_norm("ok") == "success"
    assert webui._jc_norm("error") == "failed"
    assert webui._jc_norm("warning") == "warn"
