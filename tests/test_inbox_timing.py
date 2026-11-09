import datetime as dt
import json
import threading
from contextlib import contextmanager

import pytest

from armada import clock, inbox, inbox_timing as timing, runner, util


@pytest.fixture
def realm(tmp_path, monkeypatch):
    util.write_json_atomic(tmp_path / 'realm.json', {'name': 'Synthetic', 'timezone': 'Europe/Madrid'})
    for aid in ('sender', 'recipient'):
        ad = tmp_path / 'agents' / aid
        ad.mkdir(parents=True)
        util.write_json_atomic(ad / 'agent.json', {'id': aid})
    monkeypatch.setattr(runner, 'recipient_access', lambda *a: {'ok': True, 'provider': 'mock'})
    return tmp_path


def put(root, **fields):
    path = root / 'agents/recipient/inbox/pending/task.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {'id': 'task', 'from': 'sender', 'to': 'recipient', 'ask': 'Synthetic work', **fields}
    util.write_json_atomic(path, record)
    return {**record, '_file': str(path)}


@pytest.mark.parametrize('now,expected', [
    ('2026-11-09T09:59:59+00:00', 'deferred'), ('2026-11-09T10:00:00+00:00', 'deferred'),
    ('2026-11-09T10:00:00.000001+00:00', 'eligible'), ('2026-11-09T12:00:00+00:00', 'expired')])
def test_strict_processing_window(realm, now, expected):
    msg = {'process_after': '2026-11-09T10:00:00Z', 'process_before': '2026-11-09T12:00:00Z'}
    assert timing.status(realm, msg, dt.datetime.fromisoformat(now))[0] == expected


@pytest.mark.parametrize('fields', [
    {'process_after': 'bad'}, {'process_after': None}, {'process_before': 42},
    {'process_after': '9999-12-31T23:59:59-01:00'}, {'process_after': '0001-01-01T00:00:00+01:00'},
    {'ask': 'process after'}, {'ask': 'process before tomorrow'},
    {'process_after': '11/09/2026 11:00:00', 'process_before': '11/09/2026 10:00:00'},
    {'process_after': '2026-11-09T10:00:00Z', 'ask': 'process after 11/09/2026 14:00:00'},
    {'process_after': '10/25/2026 02:30:00'}, {'process_after': '03/29/2026 02:30:00'}])
def test_bad_or_ambiguous_timing_fails_closed(realm, fields):
    assert timing.status(realm, fields)[0] == 'invalid'


def test_instruction_lines_and_realm_timezone(realm):
    assert timing.normalized(realm, {'ask': 'Do work\nprocess after 11/09/2026 11:00:00'}) == {
        'process_after': '2026-11-09T10:00:00.000000+00:00'}
    assert timing.status(realm, {'ask': 'Please explain process after timestamps'})[0] == 'eligible'


def test_future_mail_does_not_spend_capacity_or_starve_ready_mail(realm, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, 'run_job_prompt', lambda *a, **kw: calls.append(a[2]) or {'status': 'ok'})
    with clock.frozen('2026-11-09T10:00:00Z'):
        for n in range(5):
            inbox.send(realm, 'sender', 'recipient', 'later ' + str(n), process_after='2026-11-10T10:00:00Z')
        assert runner.run_inbox(realm, 'recipient')['handled'] == 0
        assert not calls and len(inbox._list(realm, 'recipient', inbox.PENDING)) == 5
        inbox.send(realm, 'sender', 'recipient', 'ready')
        assert runner.run_inbox(realm, 'recipient')['handled'] == 1
        assert len(calls) == 1 and 'ready' in calls[0]
        assert len(inbox._list(realm, 'recipient', inbox.PENDING)) == 5


@pytest.mark.parametrize('fields,state', [({'process_before': '2020-01-01T00:00:00Z'}, 'expired'),
                                         ({'process_after': 'wrong'}, 'invalid')])
def test_hand_placed_expired_or_invalid_mail_never_calls_engine(realm, monkeypatch, fields, state):
    put(realm, **fields)
    monkeypatch.setattr(runner, 'recipient_access', lambda *a: pytest.fail('Provider inspected'))
    monkeypatch.setattr(runner, 'run_job_prompt', lambda *a, **kw: pytest.fail('Engine called'))
    assert runner.run_inbox(realm, 'recipient')['handled'] == 0
    done = inbox._list(realm, 'recipient', inbox.DONE)
    assert done[0]['timing_state'] == state and not done[0]['ok']


def test_claim_rereads_timing(realm):
    stale = put(realm)
    put(realm, process_after='2099-01-01T00:00:00Z')
    assert inbox.claim(realm, 'recipient', stale) is None
    assert inbox.has_mail(realm, 'recipient')


def test_message_cannot_grant_itself_a_timing_override(realm):
    msg = put(realm, process_after='2099-01-01T00:00:00Z', timing_override={'by': 'owner'},
              inbox_timing_override=True)
    assert inbox.next_batch(realm, 'recipient') == []
    assert inbox.claim(realm, 'recipient', msg) is None


def test_saved_original_timing_is_display_only(realm):
    inbox.send(realm, 'sender', 'recipient', 'timed', process_after='2099-11-09T09:00:00+01:00')
    msg = inbox._list(realm, 'recipient', inbox.PENDING)[0]
    assert '2099-11-09T09:00:00+01:00' in timing.description(realm, msg)
    msg['timing_original']['process_after'] = '2020-01-01T00:00:00Z'
    assert '2020' not in timing.description(realm, msg)
    assert timing.status(realm, msg)[0] == 'deferred'
    msg['timing_original']['process_after'] = '9999-12-31T23:59:59-01:00'
    assert '9999' not in timing.description(realm, msg)


@pytest.mark.parametrize('field,value', [('process_after', '2099-01-01T00:00:00Z'),
                                        ('process_before', '2020-01-01T00:00:00Z')])
def test_owner_must_acknowledge_warning_then_can_override(realm, monkeypatch, field, value):
    msg = put(realm, **{field: value})
    finished = threading.Event()
    seen = []
    def run(*a, **kw):
        seen.append(kw); return {'status': 'ok', 'summary': 'done'}
    original_complete = inbox.complete
    def complete(*a, **kw):
        original_complete(*a, **kw); finished.set()
    monkeypatch.setattr(runner, 'run_job_prompt', run)
    monkeypatch.setattr(inbox, 'complete', complete)
    response = runner.process_message_now(realm, 'recipient', 'task')
    assert response['requires_timing_confirmation'] and value[:10] in response['warning']
    assert not seen and inbox.has_mail(realm, 'recipient')
    result = runner.process_message_now(realm, 'recipient', 'task', timing_confirmation=response['timing_confirmation'])
    assert result['ok'] and finished.wait(3)
    assert seen[0]['inbox_timing_override'] is True
    assert inbox._list(realm, 'recipient', inbox.DONE)[0]['timing_override']['by'] == 'owner'
    assert 'for this run only' in inbox.prompt_for(seen[0]['inbox_message'])
    assert inbox.requeue(realm, 'recipient', 'task')['ok']
    waiting = inbox._list(realm, 'recipient', inbox.PENDING)[0]
    assert 'timing_override' not in waiting
    assert runner.process_message_now(realm, 'recipient', 'task')['requires_timing_confirmation']


def test_changed_message_requires_new_confirmation(realm):
    put(realm, process_after='2099-01-01T00:00:00Z')
    token = runner.process_message_now(realm, 'recipient', 'task')['timing_confirmation']
    changed = put(realm, process_after='2098-01-01T00:00:00Z')
    result = runner.process_message_now(realm, 'recipient', 'task', timing_confirmation=token)
    assert result['requires_timing_confirmation'] and result['timing_confirmation'] != token
    assert inbox.claim(realm, 'recipient', changed, timing_confirmation=token) is None


def test_expiration_during_capacity_wait_never_reaches_model(realm, monkeypatch):
    from armada import execution_admission
    from armada.engine import MockEngine
    eng = MockEngine()
    monkeypatch.setattr(eng, 'run_stream', lambda **kw: pytest.fail('Expired task reached model'))
    @contextmanager
    def queued(*args, **kw):
        with clock.frozen('2026-11-09T12:00:00Z'):
            yield
    monkeypatch.setattr(execution_admission, 'scope', queued)
    with clock.frozen('2026-11-09T10:00:00Z'):
        result = runner.run_job_prompt(realm, 'recipient', 'Synthetic work', engine=eng,
            inbox_message={'process_before': '2026-11-09T11:00:00Z'}, allow_tools=False)
    assert result['status'] == 'error' and 'expired' in result['summary'].lower()


def test_deduplication_includes_window(realm):
    assert inbox.send(realm, 'sender', 'recipient', 'same', process_after='2099-01-01T00:00:00Z')['ok']
    assert inbox.send(realm, 'sender', 'recipient', 'same', process_after='2099-01-02T00:00:00Z')['ok']
    assert not inbox.send(realm, 'sender', 'recipient', 'same', process_after='2099-01-02T00:00:00Z')['ok']
