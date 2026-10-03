"""Concurrent writers and interrupted history commits must never silently lose conversation."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from armada import util
from armada.thread_store import CompactionConflict
from armada.threads import Thread


@pytest.fixture
def th(tmp_path):
    thread = Thread(tmp_path, "main")
    for i in range(8):
        thread.append(f"Question {i}", f"Answer {i}")
    return thread


class SummaryEngine:
    def __init__(self, during=None, text="- Earlier decisions"):
        self.during = during
        self.text = text
        self.prompts = []

    def run(self, **kwargs):
        assert kwargs["allow_tools"] is False
        self.prompts.append(kwargs["prompt"])
        if self.during:
            self.during()
        return SimpleNamespace(ok=True, output=self.text)


def compact(th, engine=None, keep=2):
    return th.compact_if_needed(engine or SummaryEngine(), threshold_chars=1, keep_recent_pairs=keep)


def test_appends_and_events_during_model_call_survive(th):
    before = th._messages()
    event = th.append_event("note", title="Before summary")
    late = []

    def append():
        other = Thread(th.dir.parent.parent, "main")
        other.append("New question", "New answer", attachments=[{"name": "input"}], outputs=[{"name": "output"}])
        other.append_event("memory_boundary", title="Concurrent observation")
        late.extend(other._messages()[-3:])

    assert compact(th, SummaryEngine(append))
    assert th._messages() == before[-4:] + [event] + late
    assert th._messages()[4]["title"] == "Before summary"
    assert th.summary() == "- Earlier decisions"


def test_pending_turn_stays_live_when_another_turn_finishes(th):
    pending = th.begin_turn("Waiting question")
    th.save_progress(pending, "Partial answer", "Thinking")
    for i in range(4):
        th.append(f"Concurrent {i}", "Done")
    th.append_event("note", title="Keep this event")
    tail = th._messages()[-10:]
    engine = SummaryEngine()
    assert compact(th, engine)
    assert th._messages() == tail
    assert "Waiting question" not in engine.prompts[0] and "Concurrent 0" not in engine.prompts[0]
    assert th.open_turn()["turn"] == pending
    assert th.progress(pending)["content"] == "Partial answer"
    th.complete_turn(pending, "Finished")
    assert th.open_turn() is None


def test_compaction_never_splits_interleaved_turns(th):
    a, b = th.begin_turn("A"), th.begin_turn("B")
    th.complete_turn(a, "Answer A")
    th.complete_turn(b, "Answer B")
    live = th._messages()[-4:]
    assert compact(th, keep=1)
    assert th._messages() == live


def test_open_turn_before_all_completed_history_defers_compaction(tmp_path):
    th = Thread(tmp_path)
    th.begin_turn("Still open")
    for _ in range(6):
        th.append("Background job", "Complete")
    engine = SummaryEngine()
    before = th.msgs.read_bytes()
    assert not compact(th, engine)
    assert not engine.prompts and th.msgs.read_bytes() == before


def test_zero_keep_compacts_complete_exchanges_but_keeps_events(th):
    event = th.append_event("note", title="Do not summarize this")
    assert compact(th, keep=0)
    assert th._messages() == [event]


def test_existing_summary_is_folded_in_once(th):
    with util.file_lock(th.msgs):
        util.write_text_atomic(th.summary_f, "- Old summary")
    engine = SummaryEngine(text="- Updated summary\r\n- Further decisions")
    assert compact(th, engine)
    assert engine.prompts[0].count("- Old summary") == 1
    assert th.summary() == "- Updated summary\n- Further decisions"


def test_unicode_line_separators_inside_messages_remain_valid_jsonl(th):
    value = "First\u2028second\u2029third"
    th.append(value, "Answer")
    event = th.append_event("note", title=value)
    for i in range(3):
        th.append(f"More {i}", "Done")
    before = th._messages()
    engine = SummaryEngine()
    assert compact(th, engine)
    assert value in engine.prompts[0]
    assert th._messages() == [event] + before[-4:]


@pytest.mark.parametrize("action", ["truncate", "truncate-and-restore", "summary-edit", "prefix-edit", "other-compaction"])
def test_concurrent_rewrite_rejects_stale_summary(th, action):
    before = th._store.read()
    original = th._messages()
    changed = []

    def rewrite():
        if action.startswith("truncate"):
            th.truncate(2)
            if action == "truncate-and-restore":
                th._write(*original[2:])
                assert th._store.read().messages == before.messages  # ABA: only the revision differs.
        elif action == "other-compaction":
            assert compact(th, SummaryEngine(text="- Winning summary"))
        else:
            with util.file_lock(th.msgs):
                if action == "summary-edit":
                    util.write_text_atomic(th.summary_f, "Owner changed summary")
                else:
                    util.write_text_atomic(th.msgs, before.messages.replace("Question 0", "Changed question", 1))
        changed.append(th._store.read())

    with pytest.raises(CompactionConflict, match="retry"):
        compact(th, SummaryEngine(rewrite, text="Must not commit"))
    assert th._store.read() == changed[0]
    assert not th._store.journal.exists()


@pytest.mark.parametrize("bad", ['{"role":"user"', '[]\n', '{"role":"user","role":"assistant"}\n'])
def test_malformed_history_is_not_silently_dropped(th, bad):
    with th.msgs.open("a", encoding="utf-8") as stream:
        stream.write(bad)
    before = th.msgs.read_bytes()
    with pytest.raises(util.StateError, match="Invalid messages"):
        compact(th)
    with pytest.raises(util.StateError):
        th.truncate(0)
    with pytest.raises(util.StateError):
        th.append("Next", "Reply")
    assert th.msgs.read_bytes() == before
    assert not th._store.journal.exists()
    assert len(th._messages()) == 16  # Inspection remains tolerant.


def test_prepare_write_failure_leaves_history_unchanged(th, monkeypatch):
    before = th._store.read()
    original = util.write_json_atomic

    def fail(path, *args, **kwargs):
        if path == th._store.journal:
            raise OSError("journal unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(util, "write_json_atomic", fail)
    with pytest.raises(OSError, match="journal unavailable"):
        compact(th)
    assert th._store.read() == before
    assert not th._store.journal.exists()


def interrupted_commit(th, monkeypatch):
    original = util.write_text_atomic

    def fail(path, *args, **kwargs):
        if path == th.msgs:
            raise OSError("interrupted after summary")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(util, "write_text_atomic", fail)
        with pytest.raises(OSError, match="interrupted after summary"):
            compact(th)
    assert th._store.journal.exists()


@pytest.mark.parametrize("next_operation", ["read", "append", "event", "truncate"])
def test_every_history_operation_recovers_before_using_partial_commit(th, monkeypatch, next_operation):
    expected = th._messages()[-4:]
    interrupted_commit(th, monkeypatch)
    # New object: recovery cannot depend on in-memory state in the crashed process.
    fresh = Thread(th.dir.parent.parent)
    if next_operation == "append":
        fresh.append("After recovery", "Kept")
    elif next_operation == "event":
        fresh.append_event("note", title="After recovery")
    elif next_operation == "truncate":
        assert fresh.truncate(2) == 2
    summary, messages = fresh.snapshot()
    assert summary == "- Earlier decisions"
    assert messages[:2 if next_operation == "truncate" else 4] == expected[:2 if next_operation == "truncate" else 4]
    assert len(messages) == {"read": 4, "append": 6, "event": 5, "truncate": 2}[next_operation]
    assert not fresh._store.journal.exists()


def test_recovery_refuses_unknown_external_changes_before_writing_any_file(th, monkeypatch):
    interrupted_commit(th, monkeypatch)
    # Simulate a non-participating editor after a crash. Never overwrite it to finish the journal.
    util.write_text_atomic(th.msgs, '{"role":"user","content":"External edit"}\n')
    before = {p: p.read_bytes() for p in (th.msgs, th.summary_f, th._store.journal)}
    with pytest.raises(util.StateError, match="outside the transaction"):
        th.snapshot()
    assert {p: p.read_bytes() for p in before} == before
    assert not th._store.revision.exists()


@pytest.mark.parametrize("damage", ["syntax", "checksum", "future"])
def test_invalid_journal_is_preserved_for_explicit_recovery(th, monkeypatch, damage):
    interrupted_commit(th, monkeypatch)
    path = th._store.journal
    state = json.loads(path.read_text(encoding="utf-8"))
    if damage == "syntax":
        path.write_text("{", encoding="utf-8")
    else:
        state["checksum" if damage == "checksum" else "schema_version"] = "bad" if damage == "checksum" else 100
        util.write_json_atomic(path, state)
    before = {p: p.read_bytes() for p in (th.msgs, th.summary_f, path)}
    with pytest.raises(util.StateError):
        th.snapshot()
    assert {p: p.read_bytes() for p in before} == before


def test_cleanup_failure_is_idempotently_recovered(th, monkeypatch):
    expected = th._messages()[-4:]
    original = Path.unlink

    def fail(path, *args, **kwargs):
        if path == th._store.journal:
            raise PermissionError("journal cleanup failed")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail)
        with pytest.raises(PermissionError, match="cleanup failed"):
            compact(th)
    assert th._store.journal.exists()
    assert th.snapshot() == ("- Earlier decisions", expected)
    assert th.snapshot() == ("- Earlier decisions", expected)
    assert not th._store.journal.exists()


@pytest.mark.parametrize("pending", [False, True])
def test_newer_realm_remains_read_only_even_during_recovery(th, monkeypatch, pending):
    if pending:
        interrupted_commit(th, monkeypatch)
    root = th.dir.parent.parent
    (root / "realm.json").write_text('{"schema_version":100}', encoding="utf-8")
    before = {p: p.read_bytes() for p in th.dir.iterdir() if p.is_file()}
    if pending:
        with pytest.raises(util.UnsupportedSchemaError):
            th.snapshot()
    else:
        assert len(th.snapshot()[1]) == 16
    with pytest.raises(util.UnsupportedSchemaError):
        th.append("Blocked", "Blocked")
    assert {p: p.read_bytes() for p in before} == before


def test_truncate_route_uses_the_recoverable_history_service(th, monkeypatch):
    from armada.routes.agents import AgentRoutes
    # The fixture's agent directory is the temporary root; use the real realm/agent layout here.
    realm = th.dir.parent.parent / "realm"
    target = Thread(realm / "agents" / "a")
    for i in range(4):
        target.append(str(i), "Reply")
    interrupted_commit(target, monkeypatch)
    result = AgentRoutes._thread_truncate(SimpleNamespace(realm=realm), {"agent": "a", "keep": 2})
    assert result == {"ok": True, "kept": 2}
    assert len(target._messages()) == 2 and target.summary() == "- Earlier decisions"
    assert not target._store.journal.exists()


def _spawn(code, *args):
    return subprocess.Popen([sys.executable, "-c", code, *map(str, args)],
        cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=0x08000000 if os.name == "nt" else 0)


def _line(proc):
    result = queue.Queue()
    threading.Thread(target=lambda: result.put(proc.stdout.readline().strip()), daemon=True).start()
    return result.get(timeout=10)


def _stop(processes):
    for proc in processes:
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=10)


_CHILD = """
import os, sys, time
from pathlib import Path
from types import SimpleNamespace
from armada import util
from armada.threads import Thread
from armada.thread_store import CompactionConflict
th = Thread(Path(sys.argv[1]))
class Engine:
    def run(self, **kwargs):
        return SimpleNamespace(ok=True, output='- Recovered summary')
"""


@pytest.mark.parametrize("stage", ["prepared", "summary.md", "messages.jsonl", ".history-revision", "cleaned"])
def test_real_process_exit_at_each_commit_boundary_recovers(th, stage):
    before = th._messages()
    code = _CHILD + """
stage = sys.argv[2]
write = util.write_text_atomic
def checkpoint(path, *args, **kwargs):
    write(path, *args, **kwargs)
    if Path(path).name == stage or (stage == 'prepared' and Path(path).name == '.history-transaction.json'):
        os._exit(17)
util.write_text_atomic = checkpoint
th.compact_if_needed(Engine(), threshold_chars=1, keep_recent_pairs=2)
os._exit(17)
"""
    proc = _spawn(code, th.dir.parent.parent, stage)
    try:
        out, err = proc.communicate(timeout=15)
        assert proc.returncode == 17, (out, err)
        if stage == "prepared":
            txn = json.loads(th._store.journal.read_text(encoding="utf-8"))
            assert "Question 0" in txn["before"]["messages"]  # Raw prefix is still recoverable.
        fresh = Thread(th.dir.parent.parent)
        assert fresh.snapshot() == ("- Recovered summary", before[-4:])
        assert not fresh._store.journal.exists()
        fresh.append("After restart", "Still here")
        assert len(fresh._messages()) == 6
    finally:
        _stop([proc])


def test_independent_writer_is_not_locked_out_during_model_call(th):
    original = th._messages()
    code = _CHILD + """
class Slow:
    def run(self, **kwargs):
        print('summarizing', flush=True)
        while not (th.dir / 'finish').exists(): time.sleep(.005)
        return SimpleNamespace(ok=True, output='- Summary')
th.compact_if_needed(Slow(), threshold_chars=1, keep_recent_pairs=2)
"""
    proc = _spawn(code, th.dir.parent.parent)
    try:
        assert _line(proc) == "summarizing"
        th.append("Independent writer", "Survives")
        th.append_event("note", title="Independent event")
        tail = th._messages()[-3:]
        (th.dir / "finish").touch()
        out, err = proc.communicate(timeout=15)
        assert proc.returncode == 0, (out, err)
        assert th._messages() == original[-4:] + tail
    finally:
        _stop([proc])


def test_two_synchronized_compactors_commit_only_one_summary(th):
    code = _CHILD + """
class Slow:
    def run(self, **kwargs):
        print('ready', flush=True)
        while not (th.dir / 'finish').exists(): time.sleep(.005)
        return SimpleNamespace(ok=True, output='- Summary ' + sys.argv[2])
try:
    th.compact_if_needed(Slow(), threshold_chars=1, keep_recent_pairs=2)
    print('committed', flush=True)
except CompactionConflict:
    print('conflict', flush=True)
"""
    procs = [_spawn(code, th.dir.parent.parent, str(i)) for i in range(2)]
    try:
        assert [_line(p) for p in procs] == ["ready", "ready"]
        (th.dir / "finish").touch()
        results = []
        for proc in procs:
            out, err = proc.communicate(timeout=15)
            assert proc.returncode == 0, err
            results.append(out.strip())
        assert sorted(results) == ["committed", "conflict"]
        assert len(th._messages()) == 4
        assert th.summary() in ("- Summary 0", "- Summary 1")
    finally:
        _stop(procs)


def test_reader_waits_for_a_coherent_generation_during_commit(th):
    before = th._messages()
    code = _CHILD + """
write = util.write_text_atomic
def pause(path, *args, **kwargs):
    write(path, *args, **kwargs)
    if Path(path).name == 'summary.md':
        print('summary-written', flush=True)
        while not (th.dir / 'finish').exists(): time.sleep(.005)
util.write_text_atomic = pause
th.compact_if_needed(Engine(), threshold_chars=1, keep_recent_pairs=2)
"""
    proc = _spawn(code, th.dir.parent.parent)
    result, errors = [], []
    entered, finished = threading.Event(), threading.Event()

    def read():
        entered.set()
        try:
            result.append(Thread(th.dir.parent.parent).snapshot())
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    reader = threading.Thread(target=read)
    try:
        assert _line(proc) == "summary-written"
        reader.start()
        assert entered.wait(1)
        assert not finished.wait(.15), "reader observed a partially applied transaction"
        (th.dir / "finish").touch()
        out, err = proc.communicate(timeout=15)
        assert proc.returncode == 0, (out, err)
        reader.join(10)
        assert not reader.is_alive() and not errors
        assert result == [("- Recovered summary", before[-4:])]
    finally:
        _stop([proc])
        if reader.ident:
            reader.join(10)
