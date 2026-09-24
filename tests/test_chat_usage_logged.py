"""Every turn that spends tokens writes a run-report.

The streaming chat path logged one; the non-streaming path did not. That path serves Telegram and
the plain /api/chat endpoint, so a turn could run, cost real quota, and leave the Usage widget
showing nothing for the day — the tokens came back to the caller in the response and were dropped
on the floor.
"""
import inspect
import json
from pathlib import Path

import pytest

from armada import runner
from armada.engine.base import RunResult, Usage


def _realm(tmp_path):
    realm = tmp_path / "realm"
    ad = realm / "agents" / "scribe"
    (ad / "jobs").mkdir(parents=True)
    (ad / "memory").mkdir()
    (realm / "realm.json").write_text(json.dumps({"name": "R"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({"id": "scribe", "name": "Scribe"}), encoding="utf-8")
    return realm, ad


class _Eng:
    """No run_stream, so chat() takes the plain run() branch."""
    name = "claude"

    def __init__(self, ok=True):
        self.ok = ok

    def run(self, **kw):
        return RunResult(ok=self.ok, output="pong" if self.ok else "",
                         error="" if self.ok else "boom", model="claude-haiku-4-5",
                         usage=Usage(input=10, output=5, cache_write=1219))   # total = 1234


def _reports(ad, agent_id="scribe"):
    f = ad / "runs" / f"{agent_id}.jsonl"
    if not f.exists():
        return []
    return [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_a_plain_chat_turn_is_recorded(tmp_path):
    realm, ad = _realm(tmp_path)
    runner.chat(realm, "scribe", "main", "ping", engine=_Eng())
    recs = _reports(ad)
    assert len(recs) == 1, "the turn spent tokens and logged nothing"
    assert recs[0]["tokens"]["total"] == 1234
    assert recs[0]["task"] == "chat:main" and recs[0]["kind"] == "chat"
    assert recs[0]["status"] == "ok"


def test_a_failed_turn_is_recorded_too(tmp_path):
    """A failure that cost nothing still belongs in the log — it is how you find out a turn died."""
    realm, ad = _realm(tmp_path)
    runner.chat(realm, "scribe", "main", "ping", engine=_Eng(ok=False))
    recs = _reports(ad)
    assert len(recs) == 1 and recs[0]["status"] == "error"
    assert "boom" in recs[0]["summary"]


def test_the_thread_is_carried_into_the_task(tmp_path):
    realm, ad = _realm(tmp_path)
    runner.chat(realm, "scribe", "side", "ping", engine=_Eng())
    assert _reports(ad)[0]["task"] == "chat:side"


def test_the_two_chat_paths_log_the_same_shape():
    """They drifted once; the fields the Usage widget reads must match on both."""
    a = inspect.getsource(runner.chat)
    b = inspect.getsource(runner.chat_stream)
    for key in ('"task": f"chat:{thread}"', '"kind": "chat"', '"tokens": res.usage.as_dict()'):
        assert key in a, f"chat() lost {key}"
        assert key in b, f"chat_stream() lost {key}"


def test_logging_never_breaks_the_turn(tmp_path, monkeypatch):
    realm, ad = _realm(tmp_path)
    monkeypatch.setattr(runner, "_write_report",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    out = runner.chat(realm, "scribe", "main", "ping", engine=_Eng())
    assert out["ok"] is True and out["output"] == "pong"
