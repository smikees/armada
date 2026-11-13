import datetime as dt
import pytest
from armada import capabilities, connector_health, dispatch, job_waits, run_policy, runner, scheduler, scheduler_state, util

AT=dt.datetime(2026,11,13,16,0,tzinfo=dt.timezone.utc)


@pytest.fixture
def realm(tmp_path,monkeypatch):
    util.write_json_atomic(tmp_path/'realm.json',{'schema_version':2,'name':'Synthetic','timezone':'UTC',
        'toolkit':{'connectors':[{'id':'broker','name':'Broker','mcp_url':'https://broker.example/mcp','enabled':True}]}})
    util.write_json_atomic(tmp_path/'agents/a/agent.json',{'id':'a','name':'A'})
    capabilities.grant(tmp_path,'a','broker')
    monkeypatch.setattr('armada.preflight.hold_reason',lambda *a:'')
    monkeypatch.setattr('armada.sysjobs.run_due',lambda *a:[])
    monkeypatch.setattr('armada.sysjobs.JOBS',[])
    monkeypatch.setattr('armada.notify.emit',lambda *a,**kw:None)
    job={'id':'read','kind':'agent','prompt':'Read only','allow_tools':True,'schedule':'daily 16:00',
         'requires_connectors':['broker'],'start_deadline_minutes':90}
    util.write_json_atomic(tmp_path/'agents/a/jobs/read.json',job)
    run_policy.seal_job(tmp_path,'a',job)
    return tmp_path


def test_outage_wait_survives_restart_without_claim_or_provider_slot(realm,monkeypatch):
    calls=[]
    states=iter(['down','down','up'])
    monkeypatch.setattr(connector_health,'request',lambda *a,**kw:{'broker':{'state':next(states),'checked_at':AT.timestamp()+100,'reason':'HTTP 503'}})
    monkeypatch.setattr(runner,'run_job',lambda *a,**kw:calls.append(a) or {'status':'ok'})
    for minutes in (0,5):
        result=scheduler.tick(realm,engine='claude',at=AT+dt.timedelta(minutes=minutes))
        assert result[0]['status']=='waiting' and not calls
        assert scheduler_state.inspect_attempt(realm,'a','read',AT.date().isoformat()) is None
    # A new tick acquires a new scheduler lease, as after restart, using the old deadline.
    result=scheduler.tick(realm,engine='claude',at=AT+dt.timedelta(minutes=6))
    assert result[0]['status']=='ok' and len(calls)==1
    assert job_waits.state(realm)['a/read']['since']==AT.timestamp()


def test_deadline_records_failure_without_engine_call(realm,monkeypatch):
    monkeypatch.setattr(connector_health,'request',lambda *a,**kw:{'broker':{'state':'down','checked_at':AT.timestamp(),'reason':'HTTP 503'}})
    monkeypatch.setattr(runner,'run_job',lambda *a,**kw:pytest.fail('Engine started before connector recovered'))
    scheduler.tick(realm,engine='claude',at=AT)
    result=scheduler.tick(realm,engine='claude',at=AT+dt.timedelta(minutes=90))
    assert result[0]['status']=='failed' and 'HTTP 503' in result[0]['detail']
    from armada.job_history import reports
    assert reports(realm/'agents/a','read')[0]['start_failure'] is True


def test_queued_job_releases_ticket_if_prerequisite_fails_again(realm,monkeypatch):
    state=['up']
    monkeypatch.setattr(connector_health,'request',lambda *a,**kw:{'broker':{'state':state[0],'checked_at':AT.timestamp()+30,'reason':'HTTP 503'}})
    pool=dispatch.Dispatcher();lease=scheduler_state.acquire(realm)
    try:
        result=scheduler.tick(realm,engine='claude',at=AT,_lease=lease,_dispatch=pool)
        assert result[0]['status']=='queued' and len(pool.pending)==1
        state[0]='down'
        result=scheduler.tick(realm,engine='claude',at=AT+dt.timedelta(minutes=1),_lease=lease,_dispatch=pool)
        assert result[0]['status']=='waiting' and not pool.pending
        assert scheduler_state.inspect_attempt(realm,'a','read',AT.date().isoformat())['status']=='waiting_prerequisites'
    finally:
        pool.close();lease.close()


@pytest.mark.parametrize('schedule',['mon-fri 16:00','0 16 * * 1-5'])
def test_window_overrides_hour_but_preserves_weekdays_and_overnight(schedule):
    job={'schedule':schedule,'start_window':{'from':'23:30','until':'01:30'}}
    friday=AT.replace(hour=23,minute=30)
    assert scheduler._due_time(job,friday,0)==friday
    assert scheduler._due_time(job,friday+dt.timedelta(hours=1),0)==friday
    assert scheduler._due_time(job,friday+dt.timedelta(days=1),0) is None
