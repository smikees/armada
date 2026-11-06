"""Synthetic account/realm admission: capacity, fairness, cancellation and crash recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

import pytest

from armada import execution_admission as admission, util
from armada.request_context import RunContext


def context(tmp_path, realm='one', thread='main'):
    root = tmp_path / realm
    root.mkdir(exist_ok=True)
    (root / 'realm.json').write_text('{}', encoding='utf-8')
    return RunContext.capture(root, 'agent', thread)


@pytest.fixture
def tickets():
    created = []
    def new(ctx, provider='claude'):
        ticket = admission.Ticket(ctx, provider)
        created.append(ticket)
        return ticket
    yield new
    for ticket in reversed(created):
        ticket.close()


def test_total_provider_realm_and_conversation_bounds(tmp_path, tickets):
    a = tickets(context(tmp_path, 'a', '1'))
    a2 = tickets(context(tmp_path, 'a', '2'))
    b = tickets(context(tmp_path, 'b'), 'codex')
    c = tickets(context(tmp_path, 'c'), 'gemini')
    blocked_provider = tickets(context(tmp_path, 'd'))
    blocked_thread = tickets(context(tmp_path, 'b'), 'gemini')
    assert all(t.ready() for t in (a, a2, b, c))
    assert not blocked_provider.ready() and not blocked_thread.ready()
    assert len([r for r in admission.snapshot() if r['state'] == 'running']) == 4
    a.close()
    assert blocked_provider.ready()
    assert not blocked_thread.ready()
    b.close()
    assert blocked_thread.ready()


def test_round_robin_realms_and_fifo_threads(tmp_path, tickets, monkeypatch):
    monkeypatch.setattr(admission, 'TOTAL', 1)
    first = tickets(context(tmp_path, 'a', 'first'))
    assert first.ready()
    a1 = tickets(context(tmp_path, 'a', 'x'))
    a2 = tickets(context(tmp_path, 'a', 'x'), 'codex')
    b1 = tickets(context(tmp_path, 'b'))
    first.close()
    assert not a1.ready()  # Poll order cannot steal the next realm's turn.
    assert b1.ready()
    b1.close()
    assert a1.ready() and not a2.ready()
    a1.close()
    assert a2.ready()


def test_saturated_provider_does_not_block_other_provider(tmp_path, tickets):
    a = tickets(context(tmp_path, 'a', '1'))
    b = tickets(context(tmp_path, 'b', '1'))
    blocked = tickets(context(tmp_path, 'c', '1'))
    other = tickets(context(tmp_path, 'd', '1'), 'gemini')
    assert a.ready() and b.ready()
    assert not blocked.ready() and other.ready()


def test_queue_bound_and_cancel_before_execution(tmp_path, tickets, monkeypatch):
    monkeypatch.setattr(admission, 'PER_REALM_QUEUE', 2)
    ctx = context(tmp_path)
    one, two = tickets(ctx), tickets(context(tmp_path))
    assert one.ready() and not two.ready()
    with pytest.raises(admission.QueueFull, match='queue is full'):
        tickets(context(tmp_path, thread='third'))
    assert admission.cancel(ctx.realm.realm_id, run_id=two.context.run_id) == 1
    with pytest.raises(admission.Cancelled):
        two.wait()
    assert not one.cancelled


def test_running_cancellation_and_nested_scope_share_one_slot(tmp_path):
    ctx = context(tmp_path)
    stopped = threading.Event()
    with admission.scope(ctx, 'claude', on_cancel=stopped.set) as ticket:
        with admission.scope(ctx, 'claude') as nested:
            assert ticket is nested and len(admission.snapshot()) == 1
            admission.cancel(ctx.realm.realm_id, run_id=ctx.run_id)
            assert stopped.wait(3)
    assert admission.snapshot() == []


def test_cancellation_snapshot_waits_for_ledger_replacement(tmp_path, monkeypatch, tickets):
    ticket = tickets(context(tmp_path))
    assert ticket.ready()
    replacing, publish, observed, stopped = (threading.Event() for _ in range(4))
    original_read, original_write = admission._read, util.write_json_atomic
    errors = []

    def read():
        if threading.current_thread().name == 'execution-cancellation':
            if replacing.is_set():
                raise PermissionError('Windows replacement temporarily denies this read')
            observed.set()
        return original_read()

    def write(path, data, **kwargs):
        if threading.current_thread().name == 'ledger-writer':
            replacing.set()
            assert publish.wait(10)
            try:
                return original_write(path, data, **kwargs)
            finally:
                replacing.clear()
        return original_write(path, data, **kwargs)

    def mutate():
        try:
            with admission._transaction() as state:
                state['last_realm'] = 'another-realm'
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(admission, '_read', read)
    monkeypatch.setattr(util, 'write_json_atomic', write)
    writer = threading.Thread(target=mutate, name='ledger-writer')
    writer.start()
    try:
        assert replacing.wait(5)
        with ticket.activate(stopped.set):
            # The watcher must wait for the writer, not misdiagnose its replacement
            # as lost ownership and cancel an otherwise healthy process.
            assert not stopped.wait(.3)
            publish.set()
            writer.join(5)
            assert not writer.is_alive() and not errors
            assert observed.wait(5) and not ticket.cancelled and not stopped.is_set()
            admission.cancel(ticket.context.realm.realm_id, run_id=ticket.context.run_id)
            assert stopped.wait(5)  # A real Stop is still delivered after the writer.
    finally:
        publish.set()
        writer.join(5)


def test_maintenance_wrapper_cancellation_reaches_model_child(tmp_path):
    parent = context(tmp_path, thread='system')
    child = context(tmp_path, thread='model')
    stopped = threading.Event()
    with admission.scope(parent, 'maintenance'):
        with admission.scope(child, 'claude', on_cancel=stopped.set):
            admission.cancel(parent.realm.realm_id, run_id=parent.run_id)
            assert stopped.wait(3)


def test_bad_state_is_preserved_and_refused(tmp_path):
    path = admission._state_path()
    path.parent.mkdir(parents=True)
    path.write_text('{"tickets":[]}', encoding='utf-8')
    before = path.read_bytes()
    with pytest.raises(util.StateError, match='Invalid execution admission'):
        admission.Ticket(context(tmp_path), 'codex')
    assert path.read_bytes() == before


def test_failed_publication_releases_kernel_ownership(tmp_path, monkeypatch):
    write = util.write_json_atomic
    def fail(path, data):
        if Path(path) == admission._state_path():
            raise OSError('injected disk failure')
        return write(path, data)
    with monkeypatch.context() as m:
        m.setattr(util, 'write_json_atomic', fail)
        with pytest.raises(OSError, match='disk failure'):
            admission.Ticket(context(tmp_path), 'claude')
    with util.file_lock(admission._slot_path('0'), timeout=0, validate_state=False):
        pass
    ticket = admission.Ticket(context(tmp_path), 'claude')
    ticket.close()


def test_duplicate_run_id_cannot_acquire_second_owner(tmp_path, tickets):
    ctx = context(tmp_path)
    tickets(ctx)
    with pytest.raises(util.StateError, match='already has an execution owner'):
        tickets(ctx)


def test_remote_cancel_is_delivered_to_the_owning_process(tmp_path, monkeypatch):
    shared = tmp_path / 'account'
    monkeypatch.setattr(admission, '_directory', lambda: shared)
    ctx = context(tmp_path)
    code = '''
import sys, threading
from pathlib import Path
from armada import execution_admission as a
from armada.request_context import RunContext
a._directory = lambda: Path(sys.argv[1])
done = threading.Event()
with a.scope(RunContext.capture(sys.argv[2], 'agent', 'main'), 'codex', on_cancel=done.set):
    print('owned', flush=True)
    if not done.wait(10): raise RuntimeError('Stop was not delivered')
print('stopped', flush=True)
'''
    proc = subprocess.Popen([sys.executable, '-c', code, str(shared), ctx.realm.root],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=0x08000000 if os.name == 'nt' else 0)
    try:
        assert proc.stdout.readline().strip() == 'owned'
        assert admission.cancel(ctx.realm.realm_id, agent='agent', thread='main') == 1
        out, err = proc.communicate(timeout=5)
        assert proc.returncode == 0 and 'stopped' in out, err
        assert admission.snapshot() == []
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=10)


def test_waiting_turn_rechecks_policy_before_any_engine_call(tmp_path, tickets):
    from armada import runner
    from armada.engine import MockEngine
    ctx = context(tmp_path)
    root = Path(ctx.realm.root)
    agent_path = root / 'agents/agent/agent.json'
    util.write_json_atomic(agent_path, {'id': 'agent'})
    holder = tickets(ctx, 'mock')
    assert holder.ready()
    queued = threading.Event()
    called = []
    result = []
    class Engine(MockEngine):
        def execute(self, request, **kw):
            called.append(request)
            return super().execute(request, **kw)
    worker = threading.Thread(target=lambda: result.append(runner.chat_stream(root, 'agent', 'main', 'work',
        lambda event: queued.set() if event.get('kind') == 'status' else None, engine=Engine())))
    worker.start()
    try:
        assert queued.wait(4)
        # Raw owner edit after initial validation: admission must reject damaged policy.
        agent_path.write_text('{"id":"agent","tool_policy":[]}', encoding='utf-8')
        holder.close()
        worker.join(timeout=5)
        assert not worker.is_alive() and not called
        assert result and not result[0]['ok'] and 'tool_policy' in result[0]['error']
    finally:
        holder.close()
        worker.join(timeout=5)


def test_queued_chat_survives_reload_and_later_messages_do_not_leak_into_context(tmp_path, tickets):
    from armada import runner
    from armada.engine import MockEngine, RunResult
    from armada.threads import Thread
    ctx = context(tmp_path)
    root = Path(ctx.realm.root)
    util.write_json_atomic(root / 'agents/agent/agent.json', {'id': 'agent'})
    holder = tickets(ctx, 'mock')
    assert holder.ready()
    requests, results = [], []
    class Engine(MockEngine):
        def execute(self, request, **kw):
            requests.append(request)
            return RunResult(ok=True, output='FIRST ANSWER' if len(requests) == 1 else 'SECOND ANSWER')
    def run(message, queued):
        results.append(runner.chat_stream(root, 'agent', 'main', message,
            lambda ev: queued.set() if ev.get('kind') == 'status' else None, engine=Engine()))
    one, two = threading.Event(), threading.Event()
    workers = [threading.Thread(target=run, args=('FIRST UNIQUE REQUEST', one)),
               threading.Thread(target=run, args=('SECOND UNIQUE REQUEST', two))]
    workers[0].start()
    try:
        assert one.wait(4)
        workers[1].start()
        assert two.wait(4)
        th = Thread(root / 'agents/agent', 'main')
        assert [m['content'] for m in th._messages()] == ['FIRST UNIQUE REQUEST', 'SECOND UNIQUE REQUEST']
        assert all(th.progress(m['turn'])['activity'].startswith('Queued') for m in th._messages())
        holder.close()
        for worker in workers:
            worker.join(6)
            assert not worker.is_alive()
        assert all(r['ok'] for r in results) and len(requests) == 2
        assert 'SECOND UNIQUE REQUEST' not in requests[0].prompt
        assert 'FIRST ANSWER' in requests[1].prompt
        assert len(th._messages()) == 4
    finally:
        holder.close()
        for worker in workers:
            if worker.ident:
                worker.join(6)


def test_kernel_ownership_across_processes_and_crash_releases_capacity(tmp_path, monkeypatch):
    shared = tmp_path / 'account'
    monkeypatch.setattr(admission, '_directory', lambda: shared)
    ctx = context(tmp_path)
    code = '''
import sys, time
from pathlib import Path
from armada import execution_admission as a
from armada.request_context import RunContext
a._directory = lambda: Path(sys.argv[1])
t = a.Ticket(RunContext.capture(sys.argv[2], 'agent', 'main'), 'claude')
t.wait()
print('owned', flush=True)
time.sleep(30)
'''
    proc = subprocess.Popen([sys.executable, '-c', code, str(shared), ctx.realm.root],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=0x08000000 if os.name == 'nt' else 0)
    ticket = None
    try:
        assert proc.stdout.readline().strip() == 'owned'
        ticket = admission.Ticket(ctx, 'claude')
        assert not ticket.ready()
        proc.kill()
        proc.communicate(timeout=10)
        until = time.monotonic() + 3
        while not ticket.ready() and time.monotonic() < until:
            time.sleep(.05)
        assert ticket.ready()
        assert [r['run_id'] for r in admission.snapshot()] == [ctx.run_id]
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=10)
        if ticket:
            ticket.close()


def test_concurrent_large_reports_cannot_interleave_json_records(tmp_path, monkeypatch):
    from armada import runner
    agent = tmp_path / 'agents/a'
    agent.mkdir(parents=True)
    target = agent / 'runs/a.jsonl'
    original_open = Path.open
    @contextmanager
    def split_append(path, *args, **kw):
        with original_open(path, *args, **kw) as handle:
            class Writer:
                def write(self, value):
                    mid = len(value) // 2
                    handle.write(value[:mid])
                    handle.flush()
                    time.sleep(.02)
                    handle.write(value[mid:])
                def flush(self):
                    handle.flush()
                def fileno(self):
                    return handle.fileno()
            yield Writer()
    def open_file(path, *args, **kw):
        if path == target and args and args[0] == 'a':
            return split_append(path, *args, **kw)
        return original_open(path, *args, **kw)
    monkeypatch.setattr(Path, 'open', open_file)
    start = threading.Barrier(2)
    def append(n):
        start.wait()
        runner._write_report(agent, 'a', {'id': n, 'text': 'résumé 測試 ' * 10000})
    workers = [threading.Thread(target=append, args=(n,)) for n in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(5)
        assert not worker.is_alive()
    records = [json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
    assert {r['id'] for r in records} == {0, 1}
    assert all(r['text'] == 'résumé 測試 ' * 10000 for r in records)
