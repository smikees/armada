"""2.19: exercise real dispatch with offline provider/transport boundaries."""
import json
import threading

import pytest

from armada import auth, inbox, notify, runner, sysjobs, telegram as tg
from armada.engine.authentication import provider_access, recipient_access
from armada.engine.codex import CodexEngine


@pytest.fixture
def realm(tmp_path):
    (tmp_path / "realm.json").write_text(json.dumps({"default_model": "gpt-5",
        "inbox": {"cadence": "minute"}}), encoding="utf-8")
    for aid, model in (("c", "claude-sonnet-4"), ("o", "gpt-5"), ("sender", "gpt-5")):
        d = tmp_path / "agents" / aid
        d.mkdir(parents=True)
        (d / "agent.json").write_text(json.dumps({"display": aid, "model": model}), encoding="utf-8")
    return tmp_path


def connections(monkeypatch, claude, codex):
    probes = []
    def check(provider, signed_in):
        probes.append(provider)
        return {"ok": True, "logged_in": signed_in}
    monkeypatch.setattr(auth, "status", lambda: check("claude", claude))
    monkeypatch.setattr(CodexEngine, "auth_status", lambda self: check("codex", codex))
    return probes


@pytest.mark.parametrize("claude,codex", [(False, True), (True, False), (True, True), (False, False)])
def test_mixed_inboxes_run_only_the_selected_connected_provider(realm, monkeypatch, claude, codex):
    probes = connections(monkeypatch, claude, codex)
    calls = []
    monkeypatch.setattr(runner, "run_job_prompt", lambda rr, aid, prompt, **kw:
                        calls.append((aid, kw["engine"])) or {"status": "ok", "summary": "done"})
    for aid in ("c", "o"):
        inbox.send(realm, "sender", aid, "test task")
    result = sysjobs.run_one(realm, "inbox-dispatch")
    assert calls == ([('c', 'claude')] if claude else []) + ([('o', 'codex')] if codex else [])
    assert probes == ["claude", "codex"]
    assert result["status"] == ("ok" if claude and codex else "skipped")
    for aid, connected in (("c", claude), ("o", codex)):
        assert inbox.has_mail(realm, aid) is not connected
        if not connected:
            assert inbox.due(realm, aid), "sign-in recovery must not wait for recipient cadence"
            assert not inbox._list(realm, aid, inbox.DONE)
    connections(monkeypatch, True, True)
    assert sysjobs.run_one(realm, "inbox-dispatch", manual=True)["ok"]
    assert sorted(calls) == [('c', 'claude'), ('o', 'codex')], "never replay completed work"


def test_no_pending_work_never_probes_auth(realm, monkeypatch):
    probes = connections(monkeypatch, False, False)
    assert sysjobs.run_one(realm, "inbox-dispatch")["ok"]
    assert not probes


@pytest.mark.parametrize("state", [None, {}, {"ok": False}, {"ok": False, "logged_in": True},
                                  {"ok": True}, {"ok": True, "logged_in": "yes"}])
def test_unavailable_auth_fails_closed_but_other_provider_continues(realm, monkeypatch, state):
    connections(monkeypatch, True, True)
    monkeypatch.setattr(auth, "status", lambda: state)
    calls = []
    monkeypatch.setattr(runner, "run_job_prompt", lambda rr, aid, *a, **kw:
                        calls.append(aid) or {"status": "ok"})
    for aid in ("c", "o"):
        inbox.send(realm, "sender", aid, "task")
    r = sysjobs.run_one(realm, "inbox-dispatch")
    assert r["status"] == "error" and r["reason"] == "auth-unavailable"
    assert calls == ["o"] and inbox.has_mail(realm, "c")


def test_probe_exception_never_leaks_cli_output_or_launches(realm, monkeypatch):
    monkeypatch.setattr(auth, "status", lambda: (_ for _ in ()).throw(RuntimeError("secret")))
    r = provider_access("claude")
    assert r["status"] == "error" and "secret" not in str(r)


def test_realm_default_and_explicit_override_select_auth(realm, monkeypatch):
    probes = connections(monkeypatch, False, True)
    assert recipient_access(realm, {})["provider"] == "codex"
    assert recipient_access(realm, "c", "codex")["ok"]
    assert not recipient_access(realm, "o", "claude")["ok"]
    assert provider_access("mock")["ok"]
    assert provider_access("unknown")["status"] == "error"
    assert probes == ["codex", "codex", "claude"]


def test_process_now_keeps_signed_out_message_pending(realm, monkeypatch):
    connections(monkeypatch, False, False)
    inbox.send(realm, "sender", "o", "task")
    mid = inbox._list(realm, "o", inbox.PENDING)[0]["id"]
    monkeypatch.setattr(runner, "run_job_prompt", lambda *a, **kw: pytest.fail("ran signed out"))
    assert runner.process_message_now(realm, "o", mid)["reason"] == "signed-out"
    assert inbox.has_mail(realm, "o")


@pytest.mark.parametrize("claude,codex", [(False, True), (True, False), (True, True), (False, False)])
def test_keepalive_is_explicitly_claude_only(realm, monkeypatch, claude, codex):
    probes = connections(monkeypatch, claude, codex)
    calls = []
    monkeypatch.setitem(sysjobs._BY_ID["usage-keepalive"], "run",
                        lambda rr: calls.append(1) or {"ok": True})
    r = sysjobs.run_one(realm, "usage-keepalive")
    assert r["ok"] is claude and bool(calls) is claude
    assert probes == ["claude"]


@pytest.fixture
def telegram(monkeypatch):
    sent, ran = [], []
    monkeypatch.setattr(tg, "ready", lambda: True)
    monkeypatch.setattr(tg, "send", lambda text: sent.append(text))
    monkeypatch.setattr(tg, "typing", lambda: None)
    monkeypatch.setattr(tg, "register_commands", lambda rr: None)
    monkeypatch.setattr(runner, "chat", lambda rr, aid, thread, prompt, **kw:
                        ran.append((aid, kw["engine"])) or {"ok": True, "output": "reply"})
    return sent, ran


@pytest.mark.parametrize("claude,codex", [(False, True), (True, False), (True, True), (False, False)])
@pytest.mark.parametrize("listener", [False, True])
def test_telegram_routes_per_recipient_in_fallback_and_listener(realm, monkeypatch, telegram,
                                                              claude, codex, listener):
    sent, ran = telegram
    probes = connections(monkeypatch, claude, codex)
    stop = threading.Event()
    def poll(rr, **kw):
        return [{"text": "/c hello"}, {"text": "/o hello"}]
    monkeypatch.setattr(tg, "poll", poll)
    if listener:
        original = tg.handle
        def handle(*args):
            result = original(*args)
            if args[1]["text"].startswith("/o"):
                stop.set()
            return result
        monkeypatch.setattr(tg, "handle", handle)
        tg.listen(realm, stop=stop)
    else:
        r = sysjobs.run_one(realm, "telegram-inbox")
        assert r["status"] == ("ok" if claude and codex else "skipped")
    assert ran == ([('c', 'claude')] if claude else []) + ([('o', 'codex')] if codex else [])
    assert probes == ["claude", "codex"]
    assert sum("Sign in and retry" in s for s in sent) == 2 - int(claude) - int(codex)
    assert len(tg.state(realm).get("runs", [])) == int(claude) + int(codex)


def test_fallback_defers_to_listener_without_polling_or_probing(realm, monkeypatch, telegram):
    probes = connections(monkeypatch, False, False)
    monkeypatch.setattr(tg, "listener_alive", lambda rr: True)
    monkeypatch.setattr(tg, "poll", lambda *a: pytest.fail("second poller"))
    r = sysjobs.run_one(realm, "telegram-inbox")
    assert r["reason"] == "listener-active" and r["skipped"] and not r["error"]
    assert not probes


def test_telegram_commands_need_no_provider(realm, monkeypatch, telegram):
    probes = connections(monkeypatch, False, False)
    monkeypatch.setattr(tg, "poll", lambda rr: [{"text": "/help"}])
    assert sysjobs.run_one(realm, "telegram-inbox")["ok"]
    assert not probes and not telegram[1] and telegram[0]


@pytest.mark.parametrize("result", [None, [], {}, {"ok": "yes"},
                                    {"ok": True, "status": "skipped"}])
def test_invalid_job_outcome_is_never_success(realm, monkeypatch, result):
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", lambda rr: result)
    r = sysjobs.run_one(realm, "prune-history")
    assert r["reason"] == "invalid-result" and r["status"] == "error"
    assert sysjobs.state(realm)["prune-history"]["attempt"]["status"] == "error"


def test_skips_are_recorded_without_failure_notification_or_false_success(realm, monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "emit", lambda *a: calls.append(a))
    job = sysjobs._BY_ID["prune-history"]
    monkeypatch.setitem(job, "run", lambda rr: {"ok": False, "detail": "failed"})
    for _ in range(3):
        sysjobs.run_one(realm, job["id"], manual=True)
    calls.clear()
    monkeypatch.setitem(job, "run", lambda rr: {"ok": False, "status": "skipped", "reason": "disabled"})
    r = sysjobs.run_one(realm, job["id"], manual=True)
    assert not r["ok"] and r["skipped"] and not r["error"] and r["fails"] == 3
    assert not calls
    entry = sysjobs.state(realm)[job["id"]]
    assert entry["runs"][-1]["status"] == "skipped" and entry["attempt"]["state"] == "finished"


def test_all_public_run_branches_have_identity_reason_and_truthful_flags(realm, monkeypatch):
    jid = "prune-history"
    monkeypatch.setitem(sysjobs._BY_ID[jid], "run", lambda rr: {"ok": True})
    results = [sysjobs.run_one(realm, "unknown"), sysjobs.run_one(realm, jid),
               sysjobs.run_one(realm, jid)]
    sysjobs.set_enabled(realm, jid, False)
    results.append(sysjobs.run_one(realm, jid, manual=True))
    (realm / sysjobs._STATE).write_text("{broken", encoding="utf-8")
    results.append(sysjobs.run_one(realm, jid))
    monkeypatch.setattr(sysjobs, "due", lambda *a: (_ for _ in ()).throw(RuntimeError("bad cadence")))
    results.extend(sysjobs.run_due(realm))
    for r in results:
        assert r["id"] and r["reason"] and r["detail"]
        assert r["ok"] == (r["status"] == "ok")
        assert r["skipped"] == (r["status"] in ("skipped", "held"))
        assert bool(r["error"]) == (r["status"] == "error")


def test_skipped_history_is_not_a_success():
    import datetime as dt
    from armada.webui.agentbits import _sysjob_health7
    now = dt.datetime.now().astimezone()
    runs = [{"ts": now.isoformat(), "status": "skipped"}]
    assert _sysjob_health7(runs, now)[3][2] == "Not scheduled"
    runs.append({"ts": now.isoformat(), "status": "ok"})
    assert _sysjob_health7(runs, now)[3][2] == "Success"


def test_failed_inbox_task_is_an_error_even_with_other_recipients_signed_out(realm, monkeypatch):
    connections(monkeypatch, False, True)
    monkeypatch.setattr(runner, "run_job_prompt", lambda *a, **kw: {"status": "error", "summary": "failed"})
    for aid in ("c", "o"):
        inbox.send(realm, "sender", aid, "task")
    r = sysjobs.run_one(realm, "inbox-dispatch")
    assert r["status"] == "error" and r["reason"] == "task-failed" and not r["skipped"]
    assert "1 failed" in r["detail"] and "signed out" in r["detail"]
    assert inbox.has_mail(realm, "c") and not inbox.has_mail(realm, "o")


def test_telegram_probe_failure_is_an_error_without_run_allowance(realm, monkeypatch, telegram):
    connections(monkeypatch, False, False)
    monkeypatch.setattr(CodexEngine, "auth_status", lambda self: {"ok": False})
    monkeypatch.setattr(tg, "poll", lambda rr: [{"text": "/o hello"}])
    r = sysjobs.run_one(realm, "telegram-inbox")
    assert r["status"] == "error" and not r["skipped"]
    assert not telegram[1] and "Could not check Codex" in telegram[0][0]
    assert not tg.state(realm).get("runs")


@pytest.mark.parametrize("job,reason", [("inbox-dispatch", "disabled"), ("telegram-inbox", "not-connected")])
def test_unavailable_dispatch_does_not_probe(realm, monkeypatch, job, reason):
    probes = connections(monkeypatch, False, False)
    monkeypatch.setattr(inbox, "enabled", lambda rr: False)
    monkeypatch.setattr(tg, "ready", lambda: False)
    r = sysjobs.run_one(realm, job)
    assert r["reason"] == reason and r["skipped"] and not r["error"]
    assert not probes


def test_held_and_locked_results_are_not_execution_errors(realm, monkeypatch):
    from armada import util
    jid = "prune-history"
    sysjobs._save(realm, {jid: {"attempt": {"attempt_id": "old", "started": "yesterday", "state": "claimed"}}})
    r = sysjobs.run_one(realm, jid)
    assert r["id"] == jid and r["status"] == "held" and r["reason"] == "uncertain-attempt"
    assert r["skipped"] and not r["error"]
    acquired, release = threading.Event(), threading.Event()
    def holder():
        with util.file_lock(realm / ".scheduler" / "system" / f"{jid}.json"):
            acquired.set()
            assert release.wait(5)
    worker = threading.Thread(target=holder)
    worker.start()
    try:
        assert acquired.wait(5)
        r = sysjobs.run_one(realm, jid, manual=True)
        assert r["id"] == jid and r["reason"] == "already-running"
        assert r["skipped"] and not r["error"]
    finally:
        release.set()
        worker.join(5)
