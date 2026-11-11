"""Owner-approved deadlines, stalls, API accounting and provider usage contracts."""
import datetime as dt
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import time

import pytest
from armada import billing, run_policy, provider_keys, usage_snapshot, util, runner
from armada.engine.base import RunResult
from armada.engine.contracts import RunRequest
from armada.run_watchdog import Watchdog


@pytest.fixture(autouse=True)
def synthetic_worker_boundary(monkeypatch):
    # These accounting/protocol tests use fake engines. Real separate-SID access
    # and process ownership are exercised by tools/worker_boundary_probe.py.
    monkeypatch.setattr('armada.worker.require', lambda: {'ready':True})
    monkeypatch.setattr('armada.worker.enabled',lambda:False)


@pytest.fixture
def realm(tmp_path):
    root = tmp_path/'realm'
    util.write_json_atomic(root/'realm.json', {'name':'Synthetic'})
    util.write_json_atomic(root/'agents/a/agent.json', {'id':'a'})
    return root


def test_thread_bullets_have_the_same_shared_behavior():
    process = subprocess.run(['node','tests/bullet_input_harness.js'], capture_output=True,text=True,timeout=15)
    assert process.returncode == 0, process.stderr
    from armada.webui.thread_window import render
    assert 'js("form")' in __import__('inspect').getsource(render)
    from armada.webui._base import _md
    rendered=_md('• Parent\n  • Nested\n    • Deeper\n• Sibling')
    assert rendered=='<ul><li>Parent<ul><li>Nested<ul><li>Deeper</li></ul></li></ul></li><li>Sibling</li></ul>'


def test_45_minutes_of_healthy_work_has_no_deadline(realm):
    # Virtual time avoids consuming provider quota or waiting 45 real minutes.
    clock = [0.0]
    killed = []
    watchdog = Watchdog(realm,'a','main',{},lambda:killed.append(True),clock=lambda:clock[0])
    for minute in range(46):
        clock[0] = minute*60
        watchdog.event({'kind':'tool_result'})
        watchdog.check()
    assert not killed
    assert RunRequest('', '').timeout is None
    assert runner._resolve_timeout(realm, {}) is None
    assert runner._resolve_timeout(realm, {'timeout':600}) == 600
    assert runner._resolve_timeout(realm, {'timeout':.5}) == .5
    util.write_json_atomic(realm/'realm.json', {'default_job_timeout':900})
    assert runner._resolve_timeout(realm,{}) == 900


def test_watchdog_only_counts_engine_events_and_soft_notice_is_once(realm,monkeypatch):
    clock=[0.0]; killed=[]; notices=[]
    monkeypatch.setattr('armada.notify.emit',lambda *args:notices.append(args))
    monitor=Watchdog(realm,'a','job',{'agent_inactivity_minutes':30,'agent_soft_mark_minutes':60},lambda:killed.append(True),scheduled=True,clock=lambda:clock[0])
    for minute in (20,40,60,80):
        clock[0]=minute*60
        monitor.event({'kind':'tool'})
        monitor.check()
    assert len(notices)==1 and not killed
    clock[0]=111*60
    monitor.event({'kind':'status'})
    monitor.check()
    assert monitor.stalled and killed and monitor.last_at


def test_watchdog_resumes_after_waiting_for_subscription(realm):
    clock=[0.0];killed=[]
    monitor=Watchdog(realm,'a','job',{},lambda:killed.append(True),clock=lambda:clock[0])
    monitor.event({'kind':'status','waiting_for_plan':True})
    clock[0]=7200;monitor.check()
    assert not killed
    monitor.event({'kind':'engine_event'})
    clock[0]+=1801;monitor.check()
    assert monitor.stalled and killed


@pytest.mark.parametrize('field,value',[('timeout',600),('critical',True),('plan_limit_action','api'),('connector_limit_action','wait'),('api_run_ceiling_usd',3),('api_model','claude-sonnet-5')])
def test_file_edits_revoke_every_approved_run_control(realm,field,value):
    job={'id':'job','kind':'agent','prompt':'work','allow_tools':False}
    run_policy.seal_job(realm,'a',job)
    assert run_policy.verify_job(realm,'a',job)
    with pytest.raises(ValueError,match='after approval'):
        run_policy.verify_job(realm,'a',{**job,field:value})


def test_api_reservations_fail_closed_and_preserve_critical_reserve(realm):
    provider_keys.save('claude','sk-ant-synthetic-test')
    run_policy.save(None,{'monthly_cap_usd':10,'api_run_ceiling_usd':5,'reserve_percent':30},global_provider=True)
    config=run_policy.settings()
    config.update(monthly_cap_usd=10,api_run_ceiling_usd=5,reserve_percent=30)
    assert run_policy.reserve('claude','one',config)==5
    assert run_policy.reserve('claude','two',config)==2
    with pytest.raises(ValueError,match='reserve'):
        run_policy.reserve('claude','three',config)
    run_policy.settle('claude','one',None)
    assert run_policy.credit(config=config)['spent_usd']==5
    assert run_policy.reserve('claude','critical',{**config,'critical':True})==3
    assert not run_policy.credit(config=config)['open']
    with pytest.raises(ValueError):
        run_policy.reserve('claude','after-cap',{**config,'critical':True})
    assert provider_keys.key('claude')=='sk-ant-synthetic-test'
    assert not any('sk-ant-synthetic-test' in p.read_text(encoding='utf-8',errors='replace') for p in realm.rglob('*') if p.is_file())


def execute_fixture(root,invoke):
    return billing.execute(SimpleNamespace(name='claude'),RunRequest('system','work'),root=root,agent='a',job=None,
        run_id='test-invocation',on_event=lambda e:None,on_proc=lambda p:None,invoke=invoke)


def test_plan_limit_fallback_is_one_invocation_and_uses_real_terminal_cost(realm,monkeypatch):
    provider_keys.save('claude','sk-ant-synthetic-test')
    monkeypatch.setattr('armada.engine.claude.credential_scrub_supported',lambda engine:True)
    calls=[]
    def invoke(engine,request,**callbacks):
        calls.append(request)
        if len(calls)==1:
            return RunResult(ok=False,error="You've hit your session limit · resets 11:59pm (Europe/Madrid)",raw={'api_error_status':429})
        assert request.env['CLAUDE_CODE_SUBPROCESS_ENV_SCRUB']=='1'
        assert request.env['ANTHROPIC_API_KEY']!='sk-ant-synthetic-test'
        assert request.env['ANTHROPIC_BASE_URL'].startswith('http://127.0.0.1:')
        assert request.max_budget_usd==5
        return RunResult(ok=True,output='Finished',raw={'total_cost_usd':0.64})
    result=execute_fixture(realm,invoke)
    assert result.ok and len(calls)==2
    assert result.raw['billing']['lane']=='api'
    assert result.raw['billing']['refused_attempt']['attempt_id']=='test-invocation-plan'
    assert run_policy.credit()['spent_usd']==.64


def test_generic_429_never_spends_api_credit(realm):
    result=execute_fixture(realm,lambda *a,**k:RunResult(ok=False,error='Rate limited',raw={'api_error_status':429}))
    assert result.raw['billing']['lane']=='plan'
    assert not billing.refusal(result)


def test_side_effects_without_replay_evidence_never_fall_back(realm):
    provider_keys.save('claude','sk-ant-synthetic-test')
    calls=[]
    def invoke(*args,**kw):
        calls.append(True)
        kw['on_event']({'kind':'tool','name':'Bash','input':{'command':'send_message'}})
        return RunResult(ok=False,error="You've hit your weekly limit",raw={'api_error_status':429})
    result=execute_fixture(realm,invoke)
    assert not result.ok and len(calls)==1 and 'replay evidence' in result.error


def test_connector_guard_checks_effective_grants(realm):
    connector={'id':'claude_ai_Interactive_Brokers','name':'Interactive Brokers','enabled':True}
    util.write_json_atomic(realm/'realm.json',{'toolkit':{'connectors':[connector]}})
    util.write_json_atomic(realm/'agents/a/agent.json',{'id':'a','toolkit':{'connectors':[connector]}})
    assert billing.connector_guard(realm,'a',RunRequest('','',allow_tools=True))==['Interactive Brokers']
    assert not billing.connector_guard(realm,'a',RunRequest('','',allow_tools=False))


def test_usage_is_shared_for_claude_codex_and_realm_objects(realm):
    root=SimpleNamespace(root=realm)
    usage_snapshot.remember(root,'claude',{'available':True,'plan':'max','session':{'pct':43,'resets_at':'2026-11-12T19:00:00+01:00'},'weekly':{'pct':61},'account':'must not persist'})
    usage_snapshot.remember(root,'codex',{'available':True,'plan':'pro','groups':[{'id':'codex','windows':[{'window_minutes':300,'pct':12},{'window_minutes':10080,'pct':20}]}]})
    reading=usage_snapshot.read(realm)
    assert reading['claude']['session']['pct']==43
    assert reading['codex']['weekly']['pct']==20
    assert 'account' not in (realm/'usage-last.json').read_text()
    text=usage_snapshot.preamble(realm)
    assert '43% used' in text and '61% used' in text and 'API credit' in text


def test_gateway_never_admits_an_unbounded_cost():
    from armada.api_gateway import Budget
    body={'model':'claude-sonnet-5','max_tokens':1000,'messages':[]}
    budget=Budget(.1)
    assert budget.authorise(body,1000)>0
    with pytest.raises(ValueError,match='remaining'):
        budget.authorise({**body,'max_tokens':100000},1000)
    with pytest.raises(ValueError,match='verified price'):
        budget.authorise({**body,'model':'claude-sonnet-50'},1000)
    with pytest.raises(ValueError,match='tool fees'):
        budget.authorise({**body,'tools':[{'type':'web_search_20250305'}]},1000)
    with pytest.raises(ValueError,match='premium'):
        budget.authorise({**body,'service_tier':'auto'},1000)


def test_expired_limit_returns_to_the_plan_without_api(realm):
    util.write_json_atomic(billing._refusal_path('claude'),{'at':time.time()-3600,'reset_at':time.time()-1,'reason':'Old limit'})
    result=execute_fixture(realm,lambda *a,**k:RunResult(ok=True,output='Plan reply'))
    assert result.ok and result.raw['billing']['lane']=='plan'


def test_known_exhaustion_skips_the_refused_attempt(realm,monkeypatch):
    provider_keys.save('claude','sk-ant-synthetic-test')
    monkeypatch.setattr('armada.engine.claude.credential_scrub_supported',lambda engine:True)
    reset=dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)
    usage_snapshot.remember(realm,'claude',{'available':True,'session':{'pct':100,'resets_at':reset.isoformat()}})
    calls=[]
    def invoke(engine,request,**kw):
        calls.append(request)
        assert 'ANTHROPIC_BASE_URL' in request.env
        return RunResult(ok=True,output='API reply',raw={'total_cost_usd':.1})
    result=execute_fixture(realm,invoke)
    assert result.ok and len(calls)==1


def test_unreadable_accounting_closes_the_lane():
    run_policy._ledger_path('claude').parent.mkdir(parents=True,exist_ok=True)
    run_policy._ledger_path('claude').write_text('{broken',encoding='utf-8')
    with pytest.raises(OSError):
        run_policy.credit()


def test_critical_queue_keeps_a_slot_free():
    from armada import execution_admission as admission
    def row(seq,critical=False,state='queued'):
        return {'seq':seq,'critical':critical,'reserve_slot':True,'state':state,'cancelled':False,
                'provider':'claude','realm':'r','agent':str(seq),'thread':'main'}
    state={'last_realm':'','tickets':{'0':row(0,state='running'),'1':row(1),'2':row(2,True)}}
    admission._promote(state)
    assert state['tickets']['2']['state']=='running'
    assert state['tickets']['1']['state']=='queued'


def test_gateway_refunds_only_completed_request_usage():
    from armada.api_gateway import Budget, _Usage
    body={'model':'claude-sonnet-5','max_tokens':32000,'messages':[]}
    budget=Budget(1)
    reserved=budget.authorise(body,100)
    remaining=budget.remaining
    usage=_Usage(True)
    usage.add(b'data: {"type":"message_start","message":{"usage":{"input_tokens":100,"output_tokens":1}}}\n\n')
    usage.add(b'data: {"type":"message_delta","usage":{"output_tokens":20}}\n\n')
    assert not usage.finish() and budget.remaining==remaining
    usage.add(b'data: {"type":"message_stop"}\n\n')
    assert usage.finish()
    budget.finish(body['model'],reserved,usage.usage)
    assert budget.remaining > .99


def test_credit_cycle_supports_month_end():
    start,reset=run_policy.cycle({'cycle_day':31},dt.datetime(2026,2,28,12,tzinfo=dt.timezone.utc))
    assert start.startswith('2026-02-28') and reset.startswith('2026-03-31')


def test_scheduler_usage_interval_is_25_minutes():
    from armada import sysjobs
    job=next(row for row in sysjobs.JOBS if row['id']=='usage-readings')
    assert sysjobs.interval_minutes(job)==25


def test_edited_job_cannot_launch_with_a_different_approved_ceiling(realm,monkeypatch):
    from armada.engine import MockEngine
    job={'id':'task','kind':'agent','prompt':'work','allow_tools':False,'timeout':600}
    path=realm/'agents/a/jobs/task.json'
    util.write_json_atomic(path,job)
    run_policy.seal_job(realm,'a',job)
    util.write_json_atomic(path,{**job,'timeout':2400})
    engine=MockEngine()
    monkeypatch.setattr(engine,'run',lambda **kw:pytest.fail('An edited ceiling reached the engine'))
    report=runner.run_job(realm,'a','task',engine=engine)
    assert report['status']=='error'
    assert 'after approval' in report['summary']


def test_missing_used_ledger_cannot_reset_the_monthly_cap():
    provider_keys.save('claude','sk-ant-synthetic-test')
    run_policy._ledger_path('claude').unlink()
    with pytest.raises(OSError,match='missing'):
        run_policy.credit()
    with pytest.raises(OSError,match='missing'):
        provider_keys.save('claude','sk-ant-synthetic-replacement')


def test_owner_can_disable_background_usage_upkeep(realm,monkeypatch):
    from armada import sysjobs
    sysjobs.set_enabled(realm,'usage-readings',False)
    monkeypatch.setattr('armada.provider_limits.read',lambda *a,**kw:pytest.fail('Disabled upkeep ran'))
    usage_snapshot.refresh_due(realm)


def test_stalled_job_cleans_up_and_can_start_again(realm,monkeypatch):
    import threading
    from armada.engine.base import EngineAdapter
    from armada.engine.contracts import ProviderCapabilities
    from armada import notify, execution_admission
    events=[]
    monkeypatch.setattr(notify,'emit',lambda root,event,*a,**kw:events.append(event))
    run_policy.save(realm,{'agent_inactivity_minutes':.002})
    job={'id':'work','kind':'agent','prompt':'Synthetic watchdog test','allow_tools':False}
    util.write_json_atomic(realm/'agents/a/jobs/work.json',job)
    run_policy.seal_job(realm,'a',job)
    class Engine(EngineAdapter):
        name='mock'
        capabilities=ProviderCapabilities(streaming=True,cancellation=True)
        healthy=False
        def doctor(self):return True,'Synthetic'
        def run(self,*a,**kw):raise AssertionError('Streaming was required')
        def run_stream(self,on_event,on_proc,**kw):
            stopped=threading.Event()
            on_proc(SimpleNamespace(kill=stopped.set,poll=lambda:None,pid=123456))
            on_event({'kind':'start'})
            if self.healthy:
                return RunResult(ok=True,output='Finished')
            assert stopped.wait(3),'The inactivity watchdog did not stop the owned process'
            return RunResult(ok=False,cancelled=True,error='Synthetic stop')
    engine=Engine()
    report=runner.run_job(realm,'a','work',engine=engine)
    assert report['result']['execution']=='stalled' and report['stalled']['last_event_at']
    assert events.count('job_stalled')==1
    journal=util.read_json_state(realm/'agents/a/runs/retries/work.json')
    assert journal['state']=='finished'
    assert not execution_admission.view(realm)
    with util.file_lock(realm/'agents/a/runs/.invocations/work.json',timeout=0):
        pass
    engine.healthy=True
    assert runner.run_job(realm,'a','work',engine=engine)['status']=='ok'


def test_new_cap_and_cycle_cannot_erase_already_spent_credit():
    from armada import clock
    with clock.frozen('2026-11-11T08:00:00+00:00'):
        provider_keys.save('claude','sk-ant-synthetic-test')
        run_policy.save(None,{'monthly_cap_usd':100,'api_run_ceiling_usd':80},global_provider=True)
        old={**run_policy.settings(),'critical':True}
        assert run_policy.reserve('claude','first',old)==80
        run_policy.settle('claude','first',60)
        run_policy.save(None,{'monthly_cap_usd':50,'cycle_day':11},global_provider=True)
        assert run_policy.credit()['spent_usd']==60
        with pytest.raises(ValueError,match='closed'):
            run_policy.reserve('claude','stale-controls',old)


def test_legacy_job_without_an_id_cannot_bypass_its_timeout_seal(realm,monkeypatch):
    from armada.engine import MockEngine
    path=realm/'agents/a/jobs/work.json'
    job={'kind':'agent','prompt':'work','allow_tools':False,'timeout':600}
    util.write_json_atomic(path,job)
    run_policy.import_legacy(realm)
    engine=MockEngine()
    util.write_json_atomic(path,{**job,'timeout':2400})
    monkeypatch.setattr(engine,'run',lambda **kw:pytest.fail('Legacy job bypassed its approval'))
    report=runner.run_job(realm,'a','work',engine=engine)
    assert report['status']=='error' and 'after approval' in report['summary']
