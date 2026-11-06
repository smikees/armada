"""Deadlines include UI queueing; stale native completions cannot deliver results."""
import json
import threading
import time
from types import SimpleNamespace

import pytest

from armada.desktop_operations import ScriptCalls
from armada.desktop_recovery import Presentation, RecoveryBudget, bound_route, initial_route, recovery_route


def test_native_start_cannot_hold_caller_past_deadline():
    entered, release = threading.Event(), threading.Event()
    workers = []
    def post(fn):
        worker = threading.Thread(target=fn)
        workers.append(worker)
        worker.start()
    def start(_):
        entered.set()
        assert release.wait(2)
        return SimpleNamespace(IsCompleted=False)
    calls = ScriptCalls(post, start, capacity=1)
    try:
        before = time.monotonic()
        with pytest.raises(OSError, match='deadline'):
            calls.evaluate('blocked native start', timeout=.05)
        assert entered.is_set() and time.monotonic() - before < 1
        with pytest.raises(OSError, match='busy'):
            calls.evaluate('capacity retained')
        calls.reset()
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
    assert not calls.calls


def test_bootstrap_destination_survives_failure_before_first_heartbeat():
    base = 'http://127.0.0.1:8756'
    assert initial_route(base + '/auth#synthetic-token&next=%2Falexander', base) == '/alexander'
    assert initial_route(base + '/auth#synthetic-token&next=%2Fthread-window%3F_realm%3Dsynthetic', base) == '/thread-window?_realm=synthetic'
    assert initial_route(base + '/auth#synthetic-token&next=%2Fapi%2Fjob-run', base) == '/'
    assert initial_route('https://other.test/auth#token&next=%2Falexander', base) == '/'


def test_failed_state_ignores_duplicate_browser_exit_events():
    guard = object.__new__(Presentation)
    guard.state, guard.generation, guard.quitting = 'failed', 3, lambda: False
    guard.recover('BrowserProcessExited')
    assert guard.state == 'failed' and guard.generation == 3


def test_native_drafts_are_bounded_and_clear_submitted_text():
    guard = object.__new__(Presentation)
    guard.drafts = {}
    for kind, prefix, limit in [('chat', 'armada-draft:', 65536), ('alexander', 'armada-alex-draft:', 6000)]:
        message = {'type': 'armada-unsent-draft', 'kind': kind, 'key': prefix + 'synthetic', 'value': 'x' * 70000}
        guard.remember_draft(message)
        assert len(guard.drafts[kind]['value']) == limit
        guard.remember_draft({**message, 'value': ''})
        assert guard.drafts[kind]['value'] == ''
    for invalid in [None, {}, {'type': 'armada-unsent-draft', 'kind': []},
                    {'type': 'armada-unsent-draft', 'kind': 'password', 'key': 'secret', 'value': 'secret'}]:
        guard.remember_draft(invalid)
    assert len(guard.drafts) == 2


def test_quit_cancels_queued_recovery_without_replacing_browser():
    queued = []
    guard = object.__new__(Presentation)
    guard.state, guard.generation = 'healthy', 0
    guard.window = SimpleNamespace()
    guard.quitting = lambda: False
    guard.show_panel = lambda *args, **kwargs: None
    guard.budget = RecoveryBudget()
    guard.post = queued.append
    guard.recover('RenderProcessExited')
    assert len(queued) == 1
    guard.quitting = lambda: True
    queued.pop()()  # No backend exists: a replacement attempt would fail this test.
    guard.recover('BrowserProcessExited')
    assert not queued and guard.generation == 1


def test_withdrawn_backend_events_are_detached_and_stale_callbacks_ignored():
    class Event:
        def __init__(self): self.callbacks = []
        def __iadd__(self, fn):
            self.callbacks.append(fn)
            return self
        def __isub__(self, fn):
            self.callbacks.remove(fn)
            return self
    core = SimpleNamespace(ProcessFailed=Event(), WebMessageReceived=Event(), NavigationStarting=Event(),
                           BrowserProcessId=123, Environment=SimpleNamespace(BrowserProcessExited=Event()))
    backend = SimpleNamespace(webview=SimpleNamespace(CoreWebView2=core))
    guard = object.__new__(Presentation)
    guard.state, guard.quitting, guard.bindings, guard.panel = 'healthy', lambda: False, None, None
    failures = []
    guard.process_failed = failures.append
    guard.bind(backend, SimpleNamespace(IsSuccess=True))
    callback = core.ProcessFailed.callbacks[0]
    callback(None, SimpleNamespace(ProcessFailedKind='RenderProcessExited'))
    assert failures == ['RenderProcessExited']
    guard.unbind()
    guard.backend = object()
    callback(None, SimpleNamespace(ProcessFailedKind='BrowserProcessExited'))
    assert failures == ['RenderProcessExited']
    assert not any(event.callbacks for event in (core.ProcessFailed, core.WebMessageReceived,
                                                  core.NavigationStarting, core.Environment.BrowserProcessExited))


def test_delayed_native_queue_does_not_execute_expired_call():
    queue, started = [], []
    calls = ScriptCalls(queue.append, started.append)
    with pytest.raises(OSError, match='deadline'):
        calls.evaluate('never execute', timeout=.01)
    queue.pop()()
    assert started == [] and not calls.calls


def test_pending_tasks_hold_finite_capacity_until_disposal():
    calls = ScriptCalls(lambda fn: fn(), lambda _: SimpleNamespace(IsCompleted=False), capacity=2)
    for _ in range(2):
        with pytest.raises(OSError, match='deadline'):
            calls.evaluate('pending promise', timeout=.01)
    with pytest.raises(OSError, match='busy'):
        calls.evaluate('must not start', timeout=1)
    assert len(calls.calls) == 2
    calls.reset()
    assert not calls.calls


def test_result_polling_and_stale_generation():
    task = SimpleNamespace(IsCompleted=False, Result=json.dumps({'result': {'value': {'ok': True}}}))
    calls = ScriptCalls(lambda fn: fn(), lambda _: task)
    result = []
    started = threading.Event()
    def run():
        started.set()
        result.append(calls.evaluate('synthetic', timeout=1))
    worker = threading.Thread(target=run)
    worker.start()
    started.wait(1)
    deadline = time.monotonic() + 1
    while not calls.calls and time.monotonic() < deadline:
        time.sleep(.001)
    task.IsCompleted = True
    # The caller may have registered its slot before the native start assigned
    # its task. Poll to completion, as the actual UI timer does.
    while worker.is_alive() and time.monotonic() < deadline:
        calls.poll()
        time.sleep(.001)
    worker.join(1)
    assert result == [{'ok': True}]
    calls.reset(close=True)
    with pytest.raises(OSError, match='unavailable'):
        calls.evaluate('closed')


def test_reset_releases_waiter_and_ignores_late_completion():
    queued, errors = [], []
    calls = ScriptCalls(queued.append, lambda _: pytest.fail('stale request executed'))
    def run():
        try:
            calls.evaluate('old generation', timeout=2)
        except OSError as e:
            errors.append(str(e))
    worker = threading.Thread(target=run)
    worker.start()
    deadline = time.monotonic() + 1
    while not queued and time.monotonic() < deadline:
        time.sleep(.001)
    calls.reset()
    queued.pop()()
    calls.poll()
    worker.join(1)
    assert errors and 'view changed' in errors[0]
    assert not calls.calls


@pytest.mark.parametrize('route', ['/api/chat-stop', '/api/job-run', '/switch?path=x', '/restart', '/update',
                                  '/r/private', '/section-raw/x', '/auth#secret', '//evil/', '/%61pi/chat-stop'])
def test_recovery_never_replays_action_or_untrusted_document(route):
    assert recovery_route('http://127.0.0.1:8756' + route, 'http://127.0.0.1:8756/') is None


def test_exact_origin_and_bound_realm_are_preserved():
    base = 'http://127.0.0.1:8756/'
    assert recovery_route('http://127.0.0.1:8757/agent/a', base) is None
    assert recovery_route('http://user@127.0.0.1:8756/', base) is None
    route = recovery_route(base + 'agent/scribe?thread=main#not-retained', base)
    assert bound_route(route, 'synthetic-realm') == '/agent/scribe?thread=main&_realm=synthetic-realm'
    assert bound_route('/?_realm=old', 'new') == '/?_realm=new'


def test_recovery_budget_stops_storms_and_allows_later_recovery():
    budget = RecoveryBudget()
    assert budget.allow(0) and budget.allow(1)
    assert not budget.allow(2) and not budget.allow(119)
    assert budget.allow(120)


def test_recovery_draft_keys_and_legacy_migration():
    from pathlib import Path
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for the production draft controller test')
    subprocess.run([node, str(Path(__file__).with_name('draft_recovery_harness.js'))], check=True, timeout=15)
