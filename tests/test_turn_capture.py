"""A turn records what it produced — the files it wrote and the capabilities it used.

This was true of chat turns only. Jobs, which are exactly the runs nobody watches, appended their
output to the thread and nothing else: 52 job runs in the live realm, zero artefacts recorded. The
capture is now shared, so the two paths cannot drift apart again.
"""
import inspect
import json

from armada import runner
from armada.engine import ClaudeEngine


def _agent(tmp_path, allow_tools=True):
    realm = tmp_path / "realm"
    ad = realm / "agents" / "scribe"
    (ad / "jobs").mkdir(parents=True)
    (ad / "memory").mkdir()
    (realm / "realm.json").write_text(json.dumps({"name": "R"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps(
        {"id": "scribe", "name": "Scribe", "allow_tools": allow_tools}), encoding="utf-8")
    return realm, ad


# --------------------------------------------------------------------------- the timeout coupling

def test_default_timeout_matches_the_engines_own():
    """The job path passes _DEFAULT_RUN_TIMEOUT to run_stream because run_stream's default is NOT
    run's. If run()'s default ever changes, this constant has to follow or jobs silently get a
    different time limit than they did before."""
    got = inspect.signature(ClaudeEngine.run).parameters["timeout"].default
    assert runner._DEFAULT_RUN_TIMEOUT == got, (
        f"run() defaults to {got}s but the streaming paths would pass {runner._DEFAULT_RUN_TIMEOUT}s")


def test_run_stream_default_really_does_differ():
    """Guard the reason the constant exists: if the two defaults ever converge, the explicit pass
    is harmless, but this test documents why it was needed."""
    r = inspect.signature(ClaudeEngine.run).parameters["timeout"].default
    s = inspect.signature(ClaudeEngine.run_stream).parameters["timeout"].default
    assert r != s, "run/run_stream timeouts converged — the explicit pass is now belt-and-braces"
    assert (r, s) == (1200, 600), f"engine defaults moved: run={r} run_stream={s}"


# --------------------------------------------------------------------------- artefact capture

def test_captures_files_written_by_the_write_tool(tmp_path):
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    target = ad / "report.md"
    cap.on_event({"kind": "tool", "name": "Write", "input": {"file_path": str(target)}})
    assert [o["name"] for o in cap.outputs] == ["report.md"]
    assert cap.outputs[0]["kind"] == "output"


def test_captures_files_written_without_a_write_tool(tmp_path):
    """A file created by Bash or by a script never appears in the event stream."""
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    (ad / "from-bash.csv").write_text("a,b\n", encoding="utf-8")
    cap.finish()
    assert "from-bash.csv" in [o["name"] for o in cap.outputs]


def test_does_not_list_files_that_were_already_there(tmp_path):
    realm, ad = _agent(tmp_path)
    (ad / "pre-existing.txt").write_text("old", encoding="utf-8")
    cap = runner._TurnCapture(realm, ad, True)
    cap.finish()
    assert "pre-existing.txt" not in [o["name"] for o in cap.outputs]


def test_does_not_list_plumbing_as_an_artefact(tmp_path):
    """Thread logs, job files and memory are the app's own records, not the agent's work."""
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    for p in [ad / "threads" / "main" / "messages.jsonl", ad / "jobs" / "x.json",
              ad / "memory" / "note.md"]:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    cap.finish()
    assert cap.outputs == [], cap.outputs


def test_no_duplicate_when_both_sources_see_the_same_file(tmp_path):
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    target = ad / "once.md"
    target.write_text("hi", encoding="utf-8")
    cap.on_event({"kind": "tool", "name": "Write", "input": {"file_path": str(target)}})
    cap.finish()
    assert [o["name"] for o in cap.outputs].count("once.md") == 1


def test_captures_nothing_when_tools_are_off(tmp_path):
    realm, ad = _agent(tmp_path, allow_tools=False)
    cap = runner._TurnCapture(realm, ad, False)
    (ad / "should-be-ignored.md").write_text("x", encoding="utf-8")
    cap.finish()
    assert cap.outputs == []


# --------------------------------------------------------------------------- capability capture

def test_records_a_capability_the_turn_exercised(tmp_path):
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    cap.on_event({"kind": "tool", "name": "WebSearch", "input": {"query": "x"}})
    assert [c["id"] for c in cap.caps] == ["web-research"]


def test_a_capability_is_recorded_once_however_often_it_is_used(tmp_path):
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    for _ in range(4):
        cap.on_event({"kind": "tool", "name": "WebFetch", "input": {"url": "u"}})
    assert len(cap.caps) == 1


def test_plumbing_tools_are_not_capabilities(tmp_path):
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    for t in ["Bash", "Read", "Write", "Glob"]:
        cap.on_event({"kind": "tool", "name": t, "input": {}})
    assert cap.caps == []


def test_tool_names_are_collected_for_auto_discovery(tmp_path):
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    cap.on_event({"kind": "tool", "name": "mcp__acme__do_thing", "input": {}})
    assert "mcp__acme__do_thing" in cap.tools


# --------------------------------------------------------------------------- robustness

def test_capture_never_raises_on_malformed_events(tmp_path):
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    for ev in [None, {}, {"kind": "tool"}, {"kind": "tool", "name": None},
               {"kind": "tool", "name": "Write", "input": None},
               {"kind": "tool", "name": "Write", "input": {"file_path": None}},
               {"kind": "text", "text": "hello"}, "not a dict"]:
        cap.on_event(ev)          # must not raise — it sits in the engine's event path


def test_finish_is_safe_when_the_agent_dir_vanishes(tmp_path):
    import shutil
    realm, ad = _agent(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    shutil.rmtree(ad)
    cap.finish()                  # must not raise


# --------------------------------------------------------------------------- wiring

# All three ways a turn can run. chat() is the Telegram path, chat_stream() the browser path,
# _run_job_inner() the scheduler path. Only chat_stream ever recorded anything.
_TURN_PATHS = (runner.chat, runner.chat_stream, runner._run_job_inner)


def test_every_turn_path_persists_what_it_captured():
    """The bug was structural: two of the three paths called th.append with no outputs= or caps=.
    A unit test of _TurnCapture alone would have passed throughout, so assert the wiring."""
    for fn in _TURN_PATHS:
        src = inspect.getsource(fn)
        assert "_TurnCapture" in src, f"{fn.__name__} does not capture at all"
        assert "outputs=cap.outputs" in src and "caps=cap.caps" in src, \
            f"{fn.__name__} captures but does not persist"


def test_every_turn_path_applies_the_memory_guardrail():
    """chat() - the Telegram entry point - was the one path where a write into another agent's
    memory folder would not be reverted."""
    for fn in _TURN_PATHS:
        src = inspect.getsource(fn)
        assert "_guard_snapshot" in src and "_guard_restore" in src, fn.__name__


def test_streaming_paths_pin_the_timeout():
    for fn in (runner.chat, runner._run_job_inner):
        src = inspect.getsource(fn)
        assert "_DEFAULT_RUN_TIMEOUT" in src, \
            f"{fn.__name__} streams without pinning the timeout — run_stream defaults to half of run"


def test_finish_runs_after_the_memory_guardrail():
    """Order matters: a file the guardrail reverted must not be reported as this turn's output."""
    for fn in _TURN_PATHS:
        src = inspect.getsource(fn)
        assert src.index("_guard_restore") < src.index("cap.finish()"), fn.__name__


def test_no_path_falls_back_to_a_bare_append():
    """Regression guard for the exact shape of the bug: th.append(x, y) with nothing else."""
    import re
    for fn in _TURN_PATHS:
        src = inspect.getsource(fn)
        for call in re.findall(r"th\.append\([^)]*\)", src, re.S):
            assert "outputs=" in call, f"{fn.__name__}: bare append -> {call.strip()[:80]}"
