import pytest
from armada import job_triggers as triggers, run_policy, util, job_waits


@pytest.fixture
def realm(tmp_path, monkeypatch):
    util.write_json_atomic(tmp_path/'realm.json', {'name':'Synthetic', 'timezone':'UTC'})
    util.write_json_atomic(tmp_path/'agents/a/agent.json', {'id':'a','name':'A','coordinator':True})
    monkeypatch.setattr('armada.notify.emit', lambda *a, **kw: None)
    monkeypatch.setattr('armada.records.admit_agent', lambda *a: {})
    monkeypatch.setattr('armada.execution_admission.view', lambda *a: [])
    monkeypatch.setattr(triggers.threading, 'Thread', lambda **kw: type('Deferred', (), {'start':lambda self:None})())
    # Stub workers never run, so isolate their reservations per test.
    import threading
    monkeypatch.setattr(triggers, '_workers', threading.BoundedSemaphore(16))
    return tmp_path


def save(root, jid, **fields):
    job={'id':jid,'kind':'agent','prompt':'Read only','allow_tools':False,'coordinator_may_start':True,**fields}
    util.write_json_atomic(root/f'agents/a/jobs/{jid}.json',job)
    run_policy.seal_job(root,'a',job)
    return job


def start(root,jid='read'):
    return triggers.enqueue(root,'a',jid,'Rerun after repair',coordinator='a')


def finish(root,request):
    triggers._update(root,request['request_id'],state='finished')


def test_opt_in_approval_and_role_are_all_required(realm):
    save(realm,'read',coordinator_may_start=False)
    with pytest.raises(ValueError,match='not allowed'): start(realm)
    job=save(realm,'read')
    util.write_json_atomic(realm/'agents/a/jobs/read.json',{**job,'prompt':'Changed'})
    with pytest.raises(ValueError,match='changed'): start(realm)
    save(realm,'read')
    util.write_json_atomic(realm/'agents/a/agent.json',{'id':'a','name':'A','coordinator':False})
    with pytest.raises(ValueError,match='Only the realm coordinator'): start(realm)


def test_overlap_and_per_job_cap_reserved_before_queueing(realm):
    save(realm,'read')
    first=start(realm)
    with pytest.raises(ValueError,match='already running or queued'): start(realm)
    finish(realm,first)
    finish(realm,start(realm))
    with pytest.raises(ValueError,match='daily start allowance'): start(realm)
    assert len(triggers.history(realm))==2


def test_realm_cap_covers_different_jobs(realm):
    run_policy.save(realm,{'coordinator_daily_cap':1})
    save(realm,'first');save(realm,'second')
    finish(realm,start(realm,'first'))
    with pytest.raises(ValueError,match='daily start allowance'): start(realm,'second')


def test_fallback_deduplicates_and_preserves_replay_guard(realm):
    save(realm,'backup',coordinator_may_start=False)
    job=save(realm,'read',fallback_job={'agent':'a','job':'backup'})
    report={'run_id':'failure-1','result':{'execution':'failed','delivery':[]}}
    result=triggers.fallback(realm,'a',job,report)
    finish(realm,result)
    with pytest.raises(ValueError,match='already requested'): triggers.fallback(realm,'a',job,report)
    report['result']['delivery']=[{'status':'sent'}]
    assert triggers.fallback(realm,'a',job,report) is None


def test_fallback_success_satisfies_dependency(realm):
    import datetime as dt
    from armada.runner import _write_report
    save(realm,'read');save(realm,'backup')
    job=save(realm,'desk',after=[{'agent':'a','job':'read'}])
    util.write_json_atomic(triggers._path(realm),{'requests':[{'agent':'a','fallback_for':{'agent':'a','job':'read'}}]})
    now=dt.datetime.now(dt.timezone.utc)
    _write_report(realm/'agents/a','a',{'task':'backup','status':'ok','ts':now.isoformat(),
        'fallback_for':{'agent':'a','job':'read','run_id':'failed-read'}})
    assert job_waits.dependency_errors(realm,job,now.timestamp()+1)==[]


def test_unapproved_disabled_fallback_is_rejected(realm):
    save(realm,'backup',enabled=False)
    job=save(realm,'read',fallback_job={'agent':'a','job':'backup'})
    with pytest.raises(ValueError,match='enabled and approved'):
        triggers.fallback(realm,'a',job,{'run_id':'r','result':{'execution':'failed'}})


def test_agent_cannot_self_promote_to_an_approved_coordinator(realm):
    save(realm,'read')
    util.write_json_atomic(realm/'agents/imposter/agent.json',{'id':'imposter','coordinator':True})
    with pytest.raises(ValueError,match='approve this coordinator'):
        triggers.enqueue(realm,'a','read','Try a run',coordinator='imposter')


def test_queued_request_rechecks_revoked_coordinator_role(realm):
    from armada import runner
    save(realm, 'read')
    start(realm)
    request = triggers.history(realm)[0]
    util.write_json_atomic(realm/'agents/a/agent.json', {'id':'a', 'name':'A', 'coordinator':False})
    with pytest.raises(ValueError, match='Only the realm coordinator'):
        runner._run_job_series(realm, 'a', 'read', None, 'main', False, trigger=request)
    assert not (realm/'agents/a/runs/.running/read.json').exists()


def test_abandoned_request_is_visible_as_interrupted(realm, monkeypatch):
    save(realm, 'read')
    start(realm)
    monkeypatch.setattr(util, 'pid_alive', lambda pid: False)
    assert triggers.history(realm)[0]['state'] == 'interrupted'
    assert not triggers.active(realm, 'a', 'read')


def test_fallback_waits_for_own_connector_without_execution_capacity(realm, monkeypatch):
    import datetime as dt
    from armada import connector_health, scheduler
    now = dt.datetime.now(dt.timezone.utc)
    monkeypatch.setattr(scheduler, 'now_in', lambda *a: now)
    monkeypatch.setattr('armada.capabilities.execution_policy', lambda *a: type('Policy', (), {'allowed_mcp_ids': {'broker'}})())
    save(realm, 'backup', requires_connectors=['broker'])
    triggers.enqueue(realm, 'a', 'backup', 'Primary failed', fallback_for={'agent':'a','job':'read','run_id':'failed-1'})
    request = triggers.history(realm)[0]
    states = iter(['down', 'up'])
    monkeypatch.setattr(connector_health, 'request', lambda *a, **kw: {'broker': {
        'state': next(states), 'checked_at': now.timestamp(), 'reason': 'HTTP 503'}})
    waits = []
    monkeypatch.setattr(triggers, '_wait_for_health', lambda seconds: waits.append(seconds))
    monkeypatch.setattr('armada.execution_admission.scope', lambda *a, **kw: pytest.fail('Waiting acquired execution capacity'))
    assert triggers.wait_for_prerequisites(realm, request) == ''
    assert waits == [5]
    row = job_waits.state(realm)['a/backup/'+request['id']]
    assert row['state'] == 'ready'


def test_fallback_rechecks_prerequisites_after_admission_queue(realm, monkeypatch):
    from armada import runner
    save(realm, 'backup')
    triggers.enqueue(realm, 'a', 'backup', 'Primary failed', fallback_for={'agent':'a','job':'read','run_id':'failed-1'})
    request = triggers.history(realm)[0]
    monkeypatch.setattr(triggers, 'prerequisites', lambda *a: {'state':'waiting','reason':'Broker HTTP 503'})
    with pytest.raises(ValueError, match='prerequisites changed.*503'):
        runner._run_job_series(realm, 'a', 'backup', None, 'main', False, trigger=request)
    assert not (realm/'agents/a/runs/.running/backup.json').exists()
