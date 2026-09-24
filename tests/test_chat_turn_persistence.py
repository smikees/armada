"""A chat message must survive the owner walking away.

The turn used to be written in one piece when the reply landed, so the owner's own message existed
nowhere but the open browser tab until then. Navigate away during a long turn and the thread you
came back to had no record of what you'd asked — the agent was still working, the status dot still
pulsed, and the transcript looked untouched. A run that failed lost the message permanently.
"""
import json

import pytest

from armada import runner
from armada.threads import Thread


@pytest.fixture
def agent_dir(tmp_path):
    d = tmp_path / "agents" / "hand"
    (d / "threads").mkdir(parents=True)
    (d / "agent.json").write_text(json.dumps({"id": "hand", "display": "Marcus"}), encoding="utf-8")
    (tmp_path / "realm.json").write_text(json.dumps({"name": "T"}), encoding="utf-8")
    return d


def _roles(th):
    return [(m.get("role"), m.get("content")) for m in th._messages()]


# --- the store ----------------------------------------------------------------------------------

def test_begin_turn_records_the_message_on_its_own(agent_dir):
    th = Thread(agent_dir, "main")
    th.begin_turn("what is the plan?")
    assert _roles(th) == [("user", "what is the plan?")]
    assert th.open_turn()["content"] == "what is the plan?"


def test_complete_turn_closes_it(agent_dir):
    th = Thread(agent_dir, "main")
    t = th.begin_turn("hello")
    th.complete_turn(t, "hello back")
    assert _roles(th) == [("user", "hello"), ("assistant", "hello back")]
    assert th.open_turn() is None


def test_the_two_halves_carry_the_same_turn_id(agent_dir):
    """Matched by an id rather than by 'the last user line', which stops being true the moment a
    scheduled job writes into the same thread."""
    th = Thread(agent_dir, "main")
    t = th.begin_turn("hello")
    th.complete_turn(t, "hi")
    ids = {m["turn"] for m in th._messages()}
    assert ids == {t}


def test_a_failed_turn_is_still_closed(agent_dir):
    th = Thread(agent_dir, "main")
    t = th.begin_turn("do the thing")
    th.complete_turn(t, "the engine fell over", status="error")
    msgs = th._messages()
    assert msgs[-1]["status"] == "error"
    assert th.open_turn() is None, "a closed turn is closed even when it went wrong"


def test_an_event_entry_does_not_close_a_turn(agent_dir):
    """Events are UI chrome — a compaction bar between the question and the answer must not make
    the question look answered."""
    th = Thread(agent_dir, "main")
    th.begin_turn("hello")
    th.append_event("compaction", "Compacted earlier turns")
    assert th.open_turn() is not None


def test_append_still_writes_both_halves(agent_dir):
    """Jobs and the non-streaming path use it, so it keeps working unchanged."""
    th = Thread(agent_dir, "main")
    th.append("q", "a")
    assert _roles(th) == [("user", "q"), ("assistant", "a")]
    assert th.open_turn() is None


# --- the streaming chat turn ---------------------------------------------------------------------

class _Res:
    def __init__(self, ok, output="", error=""):
        self.ok, self.output, self.error = ok, output, error
        self.model = "test"
        self.usage = type("U", (), {"as_dict": lambda self: {}})()


def _run_chat(agent_dir, monkeypatch, res, capture=None):
    """Drive chat_stream with a stub engine, capturing the thread state mid-run."""
    realm_root = agent_dir.parent.parent

    class _Eng:
        name = "test"

        def run(self, **kw):
            if capture is not None:
                capture.append(_roles(Thread(agent_dir, "main")))
            return res

    monkeypatch.setattr(runner, "get_engine", lambda *_a, **_k: _Eng())
    return runner.chat_stream(realm_root, "hand", "main", "make me a flower", on_event=lambda e: None)


def test_the_message_is_on_disk_while_the_agent_is_still_working(agent_dir, monkeypatch):
    """The bug, pinned. Mid-run the transcript already has the question in it, so a page loaded at
    that moment shows it."""
    seen = []
    _run_chat(agent_dir, monkeypatch, _Res(True, "here you go"), capture=seen)
    assert seen and seen[0] == [("user", "make me a flower")]


def test_the_question_is_not_sent_to_the_model_twice(agent_dir, monkeypatch):
    """It is written after the history is rendered, or it would appear in the prompt both as
    history and as the new message."""
    prompts = []
    realm_root = agent_dir.parent.parent

    class _Eng:
        name = "test"

        def run(self, **kw):
            prompts.append(kw.get("prompt", ""))
            return _Res(True, "ok")

    monkeypatch.setattr(runner, "get_engine", lambda *_a, **_k: _Eng())
    runner.chat_stream(realm_root, "hand", "main", "first", on_event=lambda e: None)
    runner.chat_stream(realm_root, "hand", "main", "second", on_event=lambda e: None)
    assert prompts[0].count("first") == 1
    assert prompts[1].count("second") == 1, "the new message appears once, not as history too"
    assert "first" in prompts[1], "but the earlier turn is still history"


def test_a_completed_turn_reads_back_as_one_exchange(agent_dir, monkeypatch):
    _run_chat(agent_dir, monkeypatch, _Res(True, "here you go"))
    assert _roles(Thread(agent_dir, "main")) == [("user", "make me a flower"),
                                                 ("assistant", "here you go")]


def test_a_failed_run_keeps_the_owners_message(agent_dir, monkeypatch):
    """It used to vanish: nothing was written unless the reply came back."""
    _run_chat(agent_dir, monkeypatch, _Res(False, "", "engine exploded"))
    th = Thread(agent_dir, "main")
    got = _roles(th)
    assert got[0] == ("user", "make me a flower")
    assert "engine exploded" in got[1][1]
    assert th._messages()[-1]["status"] == "error"


def test_a_run_that_returns_nothing_still_says_so(agent_dir, monkeypatch):
    _run_chat(agent_dir, monkeypatch, _Res(True, ""))
    th = Thread(agent_dir, "main")
    assert th.open_turn() is None
    assert "without producing a reply" in _roles(th)[1][1]


# --- what the transcript shows while a turn is open ----------------------------------------------

def _turns(realm_root, thread="main"):
    from armada import reader
    from armada.webui.pages import render_thread_turns
    return render_thread_turns(reader.read(realm_root), realm_root, "hand", thread)


def _mark(agent_dir, thread="main", kind="chat"):
    d = agent_dir / "runs" / ".running"
    d.mkdir(parents=True, exist_ok=True)
    (d / "_chat.json").write_text(json.dumps({"kind": kind, "thread": thread}), encoding="utf-8")


def test_an_open_turn_with_a_live_run_says_working(agent_dir):
    """The reply streams over an event stream belonging to the tab that sent it. A page loaded
    afterwards knows nothing about that connection, so the server has to say so itself."""
    Thread(agent_dir, "main").begin_turn("make me a flower")
    _mark(agent_dir)
    html = _turns(agent_dir.parent.parent)
    assert "make me a flower" in html, "the question is on the page at all, which was the bug"
    assert "working on it" in html and "mc-pending" in html


def test_an_open_turn_with_nothing_running_says_it_got_no_reply(agent_dir):
    """Reachable when the app was closed mid-turn: the run can't write its own failure if it
    isn't there any more."""
    Thread(agent_dir, "main").begin_turn("make me a flower")
    html = _turns(agent_dir.parent.parent)
    assert "make me a flower" in html
    assert "No reply" in html and "working on it" not in html


def test_a_run_in_another_thread_does_not_spin_this_one(agent_dir):
    """One marker file per agent, so without the thread name every thread would show a spinner
    whenever the agent was busy anywhere."""
    (agent_dir / "threads" / "taxes").mkdir(parents=True, exist_ok=True)
    Thread(agent_dir, "taxes").begin_turn("older question")
    _mark(agent_dir, thread="main")
    assert "working on it" not in _turns(agent_dir.parent.parent, "taxes")


def test_a_stale_marker_does_not_spin_forever(agent_dir):
    """Same cut-off the activity dot uses: a crashed run stops claiming to be running."""
    import os, time
    Thread(agent_dir, "main").begin_turn("make me a flower")
    _mark(agent_dir)
    p = agent_dir / "runs" / ".running" / "_chat.json"
    old = time.time() - 60 * 60
    os.utime(p, (old, old))
    assert "working on it" not in _turns(agent_dir.parent.parent)


def test_a_closed_turn_shows_no_placeholder(agent_dir):
    th = Thread(agent_dir, "main")
    th.complete_turn(th.begin_turn("hello"), "hi")
    html = _turns(agent_dir.parent.parent)
    assert "mc-pending" not in html and "No reply" not in html
