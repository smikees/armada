"""The dispatch loop: cheap when idle, exactly-once when busy, reported either way."""
import json

import pytest

from armada import inbox, runner


@pytest.fixture
def realm(tmp_path):
    (tmp_path / "realm.json").write_text(json.dumps({"name": "t", "inbox": {"cadence": "minute"}}),
                                         encoding="utf-8")
    for a in ("galen", "steve"):
        d = tmp_path / "agents" / a
        d.mkdir(parents=True)
        (d / "agent.json").write_text(json.dumps({"display": a.title()}), encoding="utf-8")
    return tmp_path


def test_an_empty_pass_never_touches_the_engine(realm, monkeypatch):
    """The whole cost argument rests on this: no mail, no agent run, no tokens."""
    calls = []
    monkeypatch.setattr(runner, "run_job_prompt", lambda *a, **k: calls.append(a))
    r = runner.dispatch_inboxes(realm)
    assert r["checked"] == 2 and r["handled"] == 0
    assert calls == [], "an empty inbox must not cost anything"


def test_a_waiting_task_is_delivered_and_run(realm, monkeypatch):
    seen = {}

    def fake(realm_root, agent_id, prompt, **kw):
        seen["agent"], seen["prompt"], seen["thread"] = agent_id, prompt, kw.get("thread")
        return {"status": "ok", "summary": "added to the price watch"}
    monkeypatch.setattr(runner, "run_job_prompt", fake)
    inbox.send(realm, "galen", "steve", "add the Fitbit Air to the daily price check")
    r = runner.dispatch_inboxes(realm)
    assert r["handled"] == 1
    assert seen["agent"] == "steve"
    assert "Fitbit Air" in seen["prompt"] and "galen" in seen["prompt"]
    assert seen["thread"] == inbox.INBOX_THREAD, "delegated work belongs in its own thread"


def test_the_task_is_filed_and_the_sender_told(realm, monkeypatch):
    monkeypatch.setattr(runner, "run_job_prompt",
                        lambda *a, **k: {"status": "ok", "summary": "done"})
    inbox.send(realm, "galen", "steve", "add the Fitbit Air")
    runner.dispatch_inboxes(realm)
    assert not inbox.has_mail(realm, "steve")
    assert inbox._list(realm, "steve", inbox.DONE)[0]["ok"] is True
    assert inbox._list(realm, "galen", inbox.DONE)[0]["reply"] is True


def test_a_failing_task_is_reported_not_retried_forever(realm, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("engine exploded")
    monkeypatch.setattr(runner, "run_job_prompt", boom)
    inbox.send(realm, "galen", "steve", "impossible")
    r = runner.dispatch_inboxes(realm)
    # delivery succeeded even though the task didn't — the failure is counted, and reported to the
    # sender and the bell, rather than making inbox delivery itself look broken
    assert r["handled"] == 1 and r["failed"] == 1 and r["ok"] is True
    assert not inbox.has_mail(realm, "steve"), "a failure must not leave the task to run again"
    assert inbox._list(realm, "galen", inbox.DONE)[0]["ok"] is False


def test_a_rejected_message_never_reaches_the_engine(realm, monkeypatch):
    """Screening happens before the run, so a loop or a refusal costs nothing."""
    calls = []
    monkeypatch.setattr(runner, "run_job_prompt", lambda *a, **k: calls.append(a))
    box = realm / "agents" / "steve" / "inbox" / "pending"
    box.mkdir(parents=True)
    (box / "x.json").write_text(json.dumps({
        "id": "x", "from": "galen", "to": "steve", "ask": "loop", "hops": 99,
        "created": "2026-09-14T10:00:00+02:00", "state": "pending"}), encoding="utf-8")
    runner.dispatch_inboxes(realm)
    assert calls == []
    done = inbox._list(realm, "steve", inbox.DONE)
    assert done and done[0]["ok"] is False and "chain" in done[0]["detail"]


def test_the_realm_switch_stops_dispatch_entirely(realm, monkeypatch):
    (realm / "realm.json").write_text(json.dumps({"inbox": {"enabled": False}}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(runner, "run_job_prompt", lambda *a, **k: calls.append(a))
    box = realm / "agents" / "steve" / "inbox" / "pending"
    box.mkdir(parents=True)
    (box / "x.json").write_text(json.dumps({"id": "x", "from": "galen", "ask": "x", "hops": 1,
                                            "created": "2026-09-14T10:00:00+02:00"}), encoding="utf-8")
    r = runner.dispatch_inboxes(realm)
    assert r["skipped"] == "disabled" and calls == []


def test_an_agent_whose_cadence_has_not_elapsed_waits(realm, monkeypatch):
    (realm / "realm.json").write_text(json.dumps({"inbox": {"cadence": "day"}}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(runner, "run_job_prompt", lambda *a, **k: calls.append(a))
    inbox.send(realm, "galen", "steve", "later please")
    inbox.mark_checked(realm, "steve")
    assert runner.dispatch_inboxes(realm)["handled"] == 0 and calls == []


def test_process_now_skips_the_cadence_but_not_the_rules(realm, monkeypatch):
    """'Process now' is the owner overriding the wait, not overriding the safeguards."""
    import time as _t
    ran = []
    monkeypatch.setattr(runner, "run_job_prompt",
                        lambda *a, **k: ran.append(a) or {"status": "ok", "summary": "done"})
    (realm / "realm.json").write_text(json.dumps({"inbox": {"cadence": "day"}}), encoding="utf-8")
    inbox.send(realm, "galen", "steve", "urgent thing")
    inbox.mark_checked(realm, "steve")                    # not due for a day
    assert runner.dispatch_inboxes(realm)["handled"] == 0  # confirms the wait is real
    mid = inbox._list(realm, "steve", inbox.PENDING)[0]["id"]
    assert runner.process_message_now(realm, "steve", mid)["ok"] is True
    for _ in range(50):                                   # it runs on a background thread
        if ran:
            break
        _t.sleep(0.05)
    assert ran, "process now should have run the task despite the cadence"


def test_process_now_still_screens_the_message(realm, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "run_job_prompt", lambda *a, **k: calls.append(a))
    box = realm / "agents" / "steve" / "inbox" / "pending"
    box.mkdir(parents=True)
    (box / "x.json").write_text(json.dumps({
        "id": "x", "from": "galen", "to": "steve", "ask": "loop", "hops": 99,
        "created": "2026-09-14T10:00:00+02:00", "state": "pending"}), encoding="utf-8")
    r = runner.process_message_now(realm, "steve", "x")
    assert r["ok"] is False and calls == []


def test_process_now_on_a_vanished_message_fails_cleanly(realm):
    assert runner.process_message_now(realm, "steve", "nope")["ok"] is False


def test_delegated_runs_use_the_normal_job_path():
    """Delegated work must not be more privileged than work an agent does for its owner — same
    context assembly, same capability gating, same approval gate."""
    import inspect
    src = inspect.getsource(runner.run_job_prompt)
    assert "_run_job_inner" in src
