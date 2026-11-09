"""Steering remains inside one admitted owner turn, with durable delivery receipts."""
import json
from pathlib import Path
import subprocess
import shutil
import sys
import threading
import time

import pytest

from armada import steering, thread_windows, util
from armada.engine.codex import CodexEngine
from armada.engine.codex_steering import SteeringControl
from armada.execution import RunSession
from armada.request_context import RunContext
from armada.threads import Thread
from golden_support import build_fixture, ServedRealm


@pytest.fixture
def live(tmp_path):
    root = build_fixture(tmp_path / 'realm')
    th = Thread(Path(root) / 'agents/captain', 'main')
    context = RunContext.capture(root, 'captain', 'main', 'steering-run')
    control = SteeringControl()
    control.activate('provider-thread', 'provider-turn')
    class Process:
        can_steer = True
        def steer(self, identity, text, callback):
            control.submit(identity, text, callback)
    with RunSession(context) as session:
        session.active.process = Process()
        session.active.steering_enabled = True
        session.active.steering_turn = th.begin_turn('Original task')
        yield root, th, session, control
        control.close()


def submit(live, identity='request-0001', text='Focus on the second option', **kwargs):
    return steering.submit(live[0], 'captain', 'main', kwargs.get('run_id', 'steering-run'), identity, text)


def ack(control, identity='request-0001'):
    sent = []
    control.drain(sent.append)
    assert len(sent) == 1
    control.accept({'id': 'armada-steer-' + identity, 'result': {'turnId': 'provider-turn'}})
    return sent[0]


def test_accepted_steering_is_exact_idempotent_and_persisted(live):
    root, th, session, control = live
    assert thread_windows.state(root, 'captain', 'main')['steerable']
    first = submit(live)
    assert first['status'] == 'pending'
    assert submit(live) == first
    message = ack(control)
    assert message['params'] == {'threadId': 'provider-thread', 'expectedTurnId': 'provider-turn',
                                 'input': [{'type': 'text', 'text': first['text']}]}
    assert submit(live)['status'] == 'accepted'
    assert len(control.requests) == 1
    state = thread_windows.state(root, 'captain', 'main')
    assert state['steering'][0]['status'] == 'accepted'
    assert 'Steering sent to the active run' in state['html']
    th.complete_turn(session.active.steering_turn, 'Revised answer')
    reloaded = Thread(Path(root) / 'agents/captain', 'main')
    assert 'Owner (steering during this turn): Focus on the second option' in reloaded.render()
    assert len(reloaded._messages()) == 4  # original fixture pair and one real turn
    with pytest.raises(ValueError, match='already used'):
        submit(live, text='Different message')


@pytest.mark.parametrize('change', ['stale', 'unsupported', 'cancelled', 'other-thread', 'completed'])
def test_no_delivery_to_wrong_or_closed_run(live, change):
    _, th, session, control = live
    if change == 'unsupported': session.active.steering_enabled = False
    if change == 'cancelled': session.active.cancelled = True
    if change == 'other-thread':
        # A second existing thread must not borrow the first thread's handle.
        Thread(th.dir.parent.parent, 'other').append('Other', 'Answer')
        with pytest.raises(ValueError, match='no longer accepting'):
            steering.submit(live[0], 'captain', 'other', 'steering-run', 'request-0001', 'Hello')
        return
    if change == 'completed': th.complete_turn(session.active.steering_turn, 'Done')
    with pytest.raises((ValueError, util.StateError)):
        submit(live, run_id='stale-run' if change == 'stale' else 'steering-run')
    assert not control.requests and not steering.receipts(th._messages())


@pytest.mark.parametrize('text', ['', ' ', 'a\0b', 'a' * 32001, None])
def test_invalid_text_never_dispatches(live, text):
    with pytest.raises(ValueError, match='characters'):
        submit(live, text=text)
    assert not live[3].requests


@pytest.mark.parametrize('result,expected', [({'turnId': 'provider-turn'}, 'accepted'),
                                          ({'turnId': 'different'}, 'uncertain'), (None, 'uncertain')])
def test_provider_acknowledgement_required(result, expected):
    control = SteeringControl(); control.activate('thread', 'provider-turn')
    receipts = []
    control.submit('one', 'hello', lambda status, error: receipts.append((status, error)))
    control.drain(lambda message: None)
    assert control.accept({'id': 'armada-steer-one', 'result': result})
    control.close()
    assert len(receipts) == 1 and receipts[0][0] == expected


def test_rejection_and_disappearance_are_not_success(live):
    _, th, _, control = live
    submit(live)
    control.drain(lambda message: None)
    control.accept({'id': 'armada-steer-request-0001', 'error': {'code': -32601, 'message': 'Unsupported'}})
    assert not control.ready
    assert submit(live)['status'] == 'rejected'
    assert 'Focus on the second option' not in th.render()


@pytest.mark.parametrize('sent,status', [(False, 'rejected'), (True, 'uncertain')])
def test_end_or_stop_settles_pending_receipts(live, sent, status):
    _, th, session, control = live
    submit(live)
    if sent: control.drain(lambda message: None)
    control.close()
    steering.finish(th, session.active.steering_turn)
    assert submit(live)['status'] == status
    assert ('delivery unconfirmed' in th.render()) == sent


def test_only_one_message_pending_and_completed_receipts_survive_compaction(live):
    from test_thread_compaction import SummaryEngine
    _, th, session, control = live
    submit(live)
    assert submit(live, 'request-0002', 'Another')['status'] == 'rejected'
    ack(control)
    th.complete_turn(session.active.steering_turn, 'Answer')
    for i in range(3): th.append(f'Later {i}', 'Reply')
    engine = SummaryEngine()
    th.compact_if_needed(engine, threshold_chars=1, keep_recent_pairs=2)
    assert 'Focus on the second option' in engine.prompts[0]


def test_authenticated_bound_route_and_detached_state(live):
    root, th, session, control = live
    with ServedRealm(root) as server:
        body = {'agent': 'captain', 'thread': 'main', 'tid': 'steering-run',
                'request_id': 'request-0001', 'message': 'Keep it concise'}
        result = server.post('/api/chat-steer', body)
        assert result['ok'] and result['receipt']['status'] == 'pending'
        ack(control)
        assert server.post('/api/chat-steer', body)['receipt']['status'] == 'accepted'
        body['tid'] = 'wrong-run'; body['request_id'] = 'request-0002'
        result = server.post('/api/chat-steer', body)
        assert not result['ok'] and result['not_sent']
        assert len(control.requests) == 1


def test_interrupted_receipt_commit_recovers_without_sending(live, monkeypatch):
    _, th, session, control = live
    original = util.write_text_atomic
    def fail(path, *args, **kwargs):
        if path == th.msgs: raise OSError('Synthetic disk interruption')
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(util, 'write_text_atomic', fail)
        with pytest.raises(OSError, match='disk interruption'):
            submit(live)
    assert not control.requests
    assert th._store.journal.exists()
    recovered = steering.receipts(th._messages())
    assert recovered[0]['status'] == 'pending'
    assert not th._store.journal.exists()
    # A retry reads the original receipt and cannot duplicate uncertain work.
    assert submit(live)['status'] == 'pending' and not control.requests
    steering.finish(th, session.active.steering_turn)
    assert submit(live)['status'] == 'uncertain'


def test_steering_route_preserves_detached_realm_boundary(live, tmp_path):
    from test_thread_windows import request
    from armada.request_context import RealmContext
    from urllib.parse import urlencode
    root, _, session, control = live
    other = RealmContext.capture(build_fixture(tmp_path / 'other-realm'))
    context = session.context.realm
    body = {'agent': 'captain', 'thread': 'main', 'tid': 'steering-run',
            'request_id': 'request-0001', 'message': 'Original realm only'}
    with ServedRealm(root) as server:
        assert request(server, '/switch?' + urlencode({'path': other.root}), context)[0] == 302
        assert request(server, '/api/chat-steer', context, body)[0] == 409
        status, raw = request(server, '/api/chat-steer', other, body)
        assert status == 200 and not json.loads(raw)['ok']
        status, raw = request(server, '/api/chat-steer', context, body, companion=True)
        assert status == 200 and json.loads(raw)['ok']
        assert len(control.requests) == 1


@pytest.mark.parametrize('cancel', [False, True])
def test_blocked_rpc_stdin_cannot_prevent_timeout_or_stop(tmp_path, cancel):
    from armada.engine.process import supervise_rpc
    script = tmp_path / 'stalled.py'
    script.write_text('import time\ntime.sleep(60)\n', encoding='utf-8')
    timers = []
    def bind(process):
        if cancel:
            timer = threading.Timer(.25, process.kill)
            timers.append(timer); timer.start()
    began = time.monotonic()
    result = supervise_rpc([sys.executable, '-u', str(script)],
        start=lambda send: send({'data': 'x' * 100000}), on_message=lambda *_: False,
        on_proc=bind, timeout=2 if cancel else .3)
    for timer in timers: timer.join(1)
    assert result.cancelled if cancel else result.timed_out
    assert time.monotonic() - began < 8


def test_blocked_send_does_not_lock_steering_admission():
    control = SteeringControl(); control.activate('thread', 'turn')
    control.submit('first', 'Message', lambda *_: None)
    blocked, release = threading.Event(), threading.Event()
    def send(_):
        blocked.set(); release.wait(3)
    worker = threading.Thread(target=control.drain, args=(send,))
    worker.start()
    try:
        assert blocked.wait(2)
        assert control.ready
        with pytest.raises(ValueError, match='awaiting confirmation'):
            control.submit('second', 'No duplicate pending', lambda *_: None)
        control.close()
    finally:
        release.set(); worker.join(3)


def test_real_rpc_transport_steers_one_turn_without_changing_permissions(tmp_path, monkeypatch):
    from test_codex_app_stream import _fake_server
    script = _fake_server(tmp_path, '''
def reply(value): print(json.dumps(value),flush=True)
starts=0
for line in sys.stdin:
    msg=json.loads(line)
    if msg.get('method')=='initialize': reply({'id':1,'result':{}})
    elif msg.get('method')=='thread/start':
        assert msg['params']['ephemeral'] is True
        reply({'id':2,'result':{'thread':{'id':'thread'}}})
    elif msg.get('method')=='turn/start':
        starts+=1
        assert starts==1 and msg['params']['approvalPolicy']=='never'
        assert msg['params']['sandboxPolicy']['type']=='workspaceWrite'
        reply({'id':3,'result':{'turn':{'id':'active'}}})
        reply({'method':'item/agentMessage/delta','params':{'itemId':'first','delta':'Working'}})
    elif msg.get('method')=='turn/steer':
        assert msg['params']=={'threadId':'thread','expectedTurnId':'active','input':[{'type':'text','text':'Focus'}]}
        reply({'id':msg['id'],'result':{'turnId':'active'}})
        reply({'method':'item/agentMessage/delta','params':{'itemId':'first','delta':' with revised focus'}})
        reply({'method':'turn/completed','params':{'threadId':'thread','turn':{'id':'active','status':'completed'}}})
''')
    engine = CodexEngine()
    monkeypatch.setattr(engine, '_launcher', lambda: [sys.executable, '-u', str(script)])
    monkeypatch.setattr(engine, '_mcp_args', lambda *a, **kw: [])
    handles, receipts = [], []
    def event(item):
        if item.get('text') == 'Working':
            assert handles[0].can_steer
            handles[0].steer('request-0001', 'Focus', lambda status, error: receipts.append(status))
    result = engine.run_stream('System', 'Task', cwd=str(tmp_path), allow_tools=True,
                               on_event=event, on_proc=handles.append, timeout=10)
    assert result.ok, result.error
    assert receipts == ['accepted'] and not handles[0].can_steer
    assert 'revised focus' in result.output


def test_browser_composer_steering():
    node = shutil.which('node')
    if not node: pytest.skip('Node is not installed')
    result = subprocess.run([node, str(Path(__file__).with_name('steering_harness.js'))], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
