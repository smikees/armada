import datetime as dt
import json
from pathlib import Path
import pytest

from armada import connector_health as health, job_waits as waits, job_rules, run_policy, util


@pytest.fixture
def realm(tmp_path, monkeypatch):
    util.write_json_atomic(tmp_path/'realm.json', {'name': 'Synthetic', 'timezone': 'UTC'})
    util.write_json_atomic(tmp_path/'agents/a/agent.json', {'id': 'a', 'name': 'A'})
    monkeypatch.setattr('armada.notify.emit', lambda *a, **kw: None)
    return tmp_path


def save(root, jid, **fields):
    job = {'id': jid, 'kind': 'agent', 'prompt': 'Synthetic read', 'allow_tools': False, 'schedule': 'daily 16:00', **fields}
    util.write_json_atomic(root/f'agents/a/jobs/{jid}.json', job)
    run_policy.seal_job(root, 'a', job)
    return job


def clock(hour=16, minute=0):
    return dt.datetime(2026, 11, 13, hour, minute, tzinfo=dt.timezone.utc)


def finish(root, jid, when, status='ok'):
    from armada.runner import _write_report
    _write_report(root/'agents/a', 'a', {'ts': when.isoformat(), 'task': jid, 'status': status,
                                       'run_id': jid+str(when.minute), 'summary': 'Synthetic outcome'})


def evaluate(root, job, when):
    return waits.evaluate(root, 'a', job, clock(), when, provider='claude')


def test_dependency_wait_survives_reload_and_counts_manual_results(realm):
    save(realm, 'read')
    job = save(realm, 'desk', after=[{'agent': 'a', 'job': 'read'}], start_window={'from': '16:00', 'until': '18:00'})
    first = evaluate(realm, job, clock())
    assert first['state'] == 'waiting'
    assert waits.pending(realm, 'a', 'desk')['deadline'] == clock(18).timestamp()
    finish(realm, 'read', clock(16, 22))
    assert evaluate(realm, job, clock(16, 22))['state'] == 'ready'


def test_running_dependency_overrides_older_success(realm, monkeypatch):
    save(realm, 'read')
    finish(realm, 'read', clock())
    job = save(realm, 'desk', after=[{'agent': 'a', 'job': 'read'}])
    monkeypatch.setattr('armada.execution_admission.view', lambda *a: [{'state': 'running'}])
    assert evaluate(realm, job, clock(16, 1))['state'] == 'waiting'


@pytest.mark.parametrize('action,expected', [('fail', 'failed'), ('run_anyway', 'ready')])
def test_window_end_has_explicit_outcome_and_reason(realm, action, expected):
    save(realm, 'read')
    job = save(realm, 'desk', after=[{'agent': 'a', 'job': 'read'}], on_window_end=action,
               start_window={'from': '16:00', 'until': '17:00'})
    evaluate(realm, job, clock())
    outcome = evaluate(realm, job, clock(17))
    assert outcome['state'] == expected and 'a/read' in outcome['reason']
    if action == 'run_anyway':
        assert 'a/read' in waits.context(realm, 'a', 'desk')
    else:
        finish(realm, 'read', clock(17, 1))
        assert evaluate(realm, job, clock(17, 2))['state'] == 'failed'


def test_stale_success_or_newer_failure_does_not_satisfy_dependency(realm):
    save(realm, 'read')
    finish(realm, 'read', clock(15))
    job = save(realm, 'desk', after=[{'agent': 'a', 'job': 'read', 'max_age_minutes': 30}])
    assert 'too old' in evaluate(realm, job, clock())['reason']
    finish(realm, 'read', clock(16, 1), 'error')
    assert evaluate(realm, job, clock(16, 2))['state'] == 'waiting'


def test_three_job_chain_moves_after_success(realm):
    read = save(realm, 'read')
    desk = save(realm, 'desk', after=[{'agent': 'a', 'job': 'read'}])
    brief = save(realm, 'brief', after=[{'agent': 'a', 'job': 'desk'}])
    assert evaluate(realm, desk, clock())['state'] == evaluate(realm, brief, clock())['state'] == 'waiting'
    finish(realm, read['id'], clock(16, 40))
    assert evaluate(realm, desk, clock(16, 40))['state'] == 'ready'
    assert evaluate(realm, brief, clock(16, 40))['state'] == 'waiting'
    finish(realm, desk['id'], clock(16, 50))
    assert evaluate(realm, brief, clock(16, 50))['state'] == 'ready'


def test_graph_rejects_dependency_and_fallback_cycles(realm):
    first = save(realm, 'first')
    save(realm, 'second', after=[{'agent': 'a', 'job': 'first'}])
    with pytest.raises(ValueError, match='cycle'):
        job_rules.validate_graph(realm, 'a', {**first, 'fallback_job': {'agent': 'a', 'job': 'second'}})


@pytest.mark.parametrize('field,value', [('schedule', 'daily 17:00'), ('cron', '0 17 * * *'),
    ('retry_backoff_seconds', [300]), ('coordinator_may_start', True), ('requires_connectors', ['broker']),
    ('start_deadline_minutes', 120), ('after', [{'agent': 'a', 'job': 'j'}]), ('secrets', ['broker'])])
def test_agent_edit_invalidates_owner_seal(realm, field, value):
    job = save(realm, 'j', kind='command', run='echo synthetic')
    with pytest.raises(ValueError):
        run_policy.verify_job(realm, 'a', {**job, field: value})


def test_connector_recovery_and_deadline_do_not_launch_engine(realm, monkeypatch):
    monkeypatch.setattr('armada.capabilities.execution_policy', lambda *a: type('Policy', (), {'allowed_mcp_ids': {'broker'}})())
    job = save(realm, 'read', requires_connectors=['broker'], start_deadline_minutes=90)
    checked = [None]
    calls = []
    def request(root, provider, ids, **kw):
        calls.append(kw)
        return {'broker': checked[0] or {'checked_at': clock().timestamp(), 'state': 'down', 'reason': 'provider server: HTTP 503'}}
    monkeypatch.setattr(health, 'request', request)
    assert evaluate(realm, job, clock())['state'] == 'waiting'
    checked[0] = {'checked_at': clock(16, 22).timestamp(), 'state': 'up'}
    assert evaluate(realm, job, clock(16, 22))['state'] == 'ready'
    assert calls[0]['not_before'] == clock().timestamp()
    checked[0] = None
    result = evaluate(realm, job, clock(17, 30))
    assert result['state'] == 'failed' and 'broker' in result['reason']


def test_heartbeat_records_transition_once_and_mirrors_without_credentials(realm, monkeypatch):
    sent = []
    monkeypatch.setattr('armada.notify.emit', lambda *args: sent.append(args))
    row = {'id': 'broker', 'name': 'Broker', 'provider': 'claude', 'state': 'down', 'reason': 'HTTP 503', 'links': {}}
    health.record(realm, 'claude', {'broker': row}, now=1000)
    health.record(realm, 'claude', {'broker': row}, now=1100)
    health.record(realm, 'claude', {'broker': {**row, 'state': 'up', 'reason': ''}}, now=1200)
    assert len(sent) == 2
    latest = json.loads((realm/'connector-health.json').read_text())['connectors']['claude:broker']
    assert latest['last_up_at'] == 1200 and latest['uptime_percent'] == 33.3
    assert 'checks' not in latest
