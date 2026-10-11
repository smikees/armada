"""Agents are told what kind of turn they are in, so job-only endings stay in jobs.

Feynman ended a test message in his thread with "ARMADA_JOB_RESULT: FAILED" because his mandate
says how every run ends (11 October 2026). Conversations and one-off requests now say plainly that
job endings don't apply; scheduled runs are unchanged.
"""
import json

from armada import runner
from armada.engine.base import RunResult, Usage
from armada.execution import turn_kind_note


def test_the_note_names_the_kind_of_turn():
    chat = turn_kind_note(False, None, "main")
    assert "conversation with the owner" in chat and '"main"' in chat
    assert "ARMADA_JOB_RESULT" in chat and "do not apply" in chat
    request = turn_kind_note(False, "adhoc", "main")
    assert "one-off request" in request and "do not apply" in request
    job = turn_kind_note(True, "pacioli-book", "job-run--pacioli-book")
    assert "scheduled job run (job pacioli-book)" in job and "do not apply" not in job


class _Eng:
    name = "claude"

    def __init__(self):
        self.systems = []

    def run(self, **kw):
        self.systems.append(kw.get("system") or "")
        return RunResult(ok=True, output="Pong.", model="claude-haiku-5-5", usage=Usage(input=1, output=1))


def test_a_chat_turn_carries_the_conversation_note(tmp_path):
    realm = tmp_path / "realm"
    ad = realm / "agents" / "scribe"
    (ad / "jobs").mkdir(parents=True)
    (ad / "memory").mkdir()
    (realm / "realm.json").write_text(json.dumps({"name": "R"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({"id": "scribe", "name": "Scribe"}), encoding="utf-8")
    eng = _Eng()
    runner.chat(realm, "scribe", "main", "Test ping", engine=eng)
    assert eng.systems and "This turn is a conversation with the owner" in eng.systems[-1]
