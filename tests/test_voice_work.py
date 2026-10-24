"""Speech uses the real coordinator, with independent audio and work lifetimes."""
import threading
import time

import pytest

from armada import runner, util, voice_turns, thread_windows
from armada.engine import MockEngine
from armada.engine.base import RunResult
from armada.execution import ACTIVE_RUNS, RUNS_LOCK, RunSession, TurnCoordinator, TurnRequest
from armada.request_context import RunContext
from armada.threads import Thread


def wait_idle():
    deadline = time.monotonic() + 5
    while voice_turns._queues and time.monotonic() < deadline:
        time.sleep(.01)
    assert not voice_turns._queues


@pytest.fixture
def work(tmp_path, monkeypatch):
    root = tmp_path
    agent = {'id': 'a', 'model': 'codex:default', 'effort': 'high'}
    util.write_json_atomic(root/'realm.json', {'name': 'Speech fixture'})
    util.write_json_atomic(root/'agents/a/agent.json', agent)
    util.write_text_atomic(root/'agents/a/mandate.md', 'Remember cobalt.')
    th = Thread(root/'agents/a')
    th.append('Earlier question', 'Earlier answer')
    started, release = threading.Event(), threading.Event()
    requests = []

    class Engine(MockEngine):
        def execute(self, request, *, on_event=None, on_proc=None):
            requests.append(request)
            if on_event:
                on_event({'kind': 'tool', 'name': 'Write', 'id': 'test',
                          'input': {'file_path': str(root/'agents/a/proof.txt')}})
            started.set()
            assert release.wait(5)
            util.write_text_atomic(root/'agents/a/proof.txt', 'cobalt completed')
            return RunResult(ok=True, output='Actual tool work finished.')

    monkeypatch.setattr(runner, '_prepare_agent_run', lambda *args: (Engine(), agent))
    yield root, th, started, release, requests
    release.set()
    wait_idle()


def submit(root, text, **kw):
    return voice_turns.submit(root, 'a', 'main', text, voice_session='call', voice_item=text, **kw)


def test_audio_end_does_not_cancel_normal_work_and_views_share_progress(work):
    root, th, started, release, requests = work
    audio = RunSession(RunContext.capture(root, 'a', 'main'))
    audio.active.kind = 'voice_audio'
    audio.__enter__()
    try:
        tid = submit(root, 'Create proof')
        assert started.wait(2)
        assert th.open_turn()['turn'] == tid
        assert th.progress(tid)['events'][0]['name'] == 'Write'
        state = thread_windows.state(root, 'a', 'main')
        assert state['run_id'] != audio.context.run_id and state['run_id']
        assert 'Using a tool' in state['html'] or 'Updating' in state['html']
        RunSession.cancel(audio.context.key)
        audio.close()
        with RUNS_LOCK:
            assert any(not r.cancelled and r.context.run_id == tid for r in ACTIVE_RUNS.values())
        release.set()
        wait_idle()
        assert (root/'agents/a/proof.txt').read_text() == 'cobalt completed'
        assert th.open_turn() is None
        assert th._messages()[-1]['content'] == 'Actual tool work finished.'
        assert requests[0].allow_tools and requests[0].effort == 'high'
        assert 'Earlier answer' in requests[0].prompt and 'cobalt' in requests[0].system
        assert requests[0].prompt.count('Create proof') == 1
        assert not thread_windows.state(root, 'a', 'main')['run_id']
    finally:
        audio.close()


def test_queue_is_fifo_and_context_excludes_future_requests(work):
    root, th, started, release, requests = work
    first = submit(root, 'First unique request')
    assert started.wait(2)
    second = submit(root, 'Second unique request')
    assert len(requests) == 1 and first != second
    assert 'Second unique request' not in requests[0].prompt
    release.set()
    wait_idle()
    assert len(requests) == 2
    assert 'Actual tool work finished.' in requests[1].prompt
    assert requests[1].prompt.count('Second unique request') == 1
    for tid in (first, second):
        assert [m['role'] for m in th._messages() if m.get('turn') == tid] == ['user', 'assistant']


def test_voice_waits_for_existing_typed_work(work):
    root, th, started, release, requests = work
    with RunSession(RunContext.capture(root, 'a', 'main')):
        submit(root, 'Follow up on typed work')
        assert not started.wait(.15)
        th.append('Typed work', 'Typed work is complete')
    assert started.wait(2)
    release.set()
    wait_idle()
    assert 'Typed work is complete' in requests[0].prompt


def test_cancelled_queued_turn_never_launches_engine(work):
    root, th, started, release, requests = work
    submit(root, 'First')
    assert started.wait(2)
    second = submit(root, 'Must not execute')
    with RUNS_LOCK:
        key = next(k for k, r in ACTIVE_RUNS.items() if r.context.run_id == second)
    assert RunSession.cancel(key)['ok']
    release.set()
    wait_idle()
    assert len(requests) == 1
    assert th._messages()[-1]['status'] == 'stopped'


def test_removed_queued_request_does_not_reappear(work):
    root, th, started, release, requests = work
    submit(root, 'First')
    assert started.wait(2)
    second = submit(root, 'Removed request')
    # Simulate an owner history rewrite while the request is queued.
    import json
    util.write_text_atomic(th.msgs, ''.join(json.dumps(m)+'\n' for m in th._messages()
                                          if m.get('turn') != second))
    release.set()
    wait_idle()
    assert len(requests) == 1
    assert not any(m.get('turn') == second for m in th._messages())


def test_invalid_admitted_turn_never_appends_a_reply(work):
    root, th, started, release, requests = work
    before = th._messages()
    context = RunContext.capture(root, 'a', 'main')
    with pytest.raises(ValueError, match='no longer pending'):
        TurnCoordinator(TurnRequest(context, 'missing', admitted_turn='missing')).run()
    assert th._messages() == before and not requests


def test_speech_playback_failure_does_not_erase_successful_work(work):
    root, th, started, release, requests = work
    def failed_audio(result):
        raise OSError('Audio closed')
    release.set()
    submit(root, 'Create proof', reply=failed_audio)
    wait_idle()
    assert th._messages()[-1]['content'] == 'Actual tool work finished.'
    assert th._messages()[-1].get('status', 'ok') == 'ok'


def test_failed_normal_runner_is_saved_as_failure(work, monkeypatch):
    root, th, started, release, requests = work
    def failed(*args):
        raise ValueError('Provider unavailable')
    monkeypatch.setattr(runner, '_prepare_agent_run', failed)
    submit(root, 'Create proof')
    wait_idle()
    assert th._messages()[-1]['status'] == 'error'
    assert 'Provider unavailable' in th._messages()[-1]['content']
    assert not (root/'agents/a/proof.txt').exists()


def test_archived_queued_request_is_not_executed(work):
    root, th, started, release, requests = work
    submit(root, 'First')
    assert started.wait(2)
    second = submit(root, 'Queued')
    util.write_json_atomic(root/'agents/a/threads/meta.json', {'archived': {'main': True}})
    release.set()
    wait_idle()
    assert len(requests) == 1
    assert len([m for m in th._messages() if m.get('turn') == second]) == 1


def test_stop_work_cancels_active_and_queued_work_without_ending_audio(work):
    root, th, started, release, requests = work
    from armada.routes.agents import AgentRoutes
    class Routes(AgentRoutes):
        _streams, _streams_lock = ACTIVE_RUNS, RUNS_LOCK
    routes = Routes()
    routes.realm = root
    audio = RunSession(RunContext.capture(root, 'a', 'main'))
    audio.active.kind = 'voice_audio'
    audio.__enter__()
    try:
        first = submit(root, 'First')
        assert started.wait(2)
        second = submit(root, 'Second')
        assert routes._chat_stop({'agent': 'a', 'thread': 'main'})['stopped']
        assert not audio.active.cancelled
        with RUNS_LOCK:
            assert all(r.cancelled for r in ACTIVE_RUNS.values() if r.context.run_id in (first, second))
    finally:
        audio.close()
