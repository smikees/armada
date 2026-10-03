"""The model sees live connector startup, not a stale stored-credentials label."""
import json
import sys
import pytest
from armada.engine import mcp_runtime
from armada.engine.codex import CodexEngine, _feature_args


@pytest.mark.parametrize('network', [False, True])
@pytest.mark.parametrize('connected', [False, True])
def test_jobs_and_threads_await_actual_mcp_startup(tmp_path, monkeypatch, network, connected):
    script = tmp_path / 'server.py'
    status = {'name': 'broker', 'authStatus': 'oAuth' if connected else 'notLoggedIn',
        'runtimeStatus': 'connected' if connected else 'authenticationRequired',
        'tools': {'get_account_positions': {}} if connected else {},
        'toolsError': None if connected else 'invalid_grant: Refresh token is not active'}
    script.write_text('''import json,sys
checked=False
def reply(x): print(json.dumps(x),flush=True)
for line in sys.stdin:
    x=json.loads(line)
    if x.get('method')=='initialize': reply({'id':1,'result':{}})
    elif x.get('method')=='thread/start': reply({'id':2,'result':{'thread':{'id':'fresh'}}})
    elif x.get('method')=='mcpServerStatus/list':
        assert x['params']['threadId']=='fresh' and x['params']['serverName']=='broker'
        checked=True
        reply({'id':4,'result':{'data': [STATUS]}})
    elif x.get('method')=='turn/start':
        assert checked
        text=x['params']['input'][0]['text']
        assert EXPECTED in text
        assert x['params']['sandboxPolicy']['networkAccess']==NETWORK
        reply({'id':3,'result':{}})
        reply({'method':'item/completed','params':{'item':{'id':'a','type':'agentMessage','text':'Qualified report'}}})
        reply({'method':'turn/completed','params':{'turn':{'status':'completed'}}})
'''.replace('STATUS',repr(status)).replace('EXPECTED',repr('get_account_positions' if connected else status['toolsError']))
       .replace('NETWORK',repr(network)), encoding='utf-8')
    engine=CodexEngine()
    engine.allowed_mcp_ids={'broker'}
    engine._turn_mcp_ids=('broker',)
    engine.network_access=network
    monkeypatch.setattr(engine,'_launcher',lambda:[sys.executable,'-u',str(script)])
    monkeypatch.setattr(engine,'_mcp_args',lambda *a,**kw:[])
    events=[]
    result=engine.run_stream('system','request',allow_tools=True,cwd=str(tmp_path),on_event=events.append,timeout=10)
    assert result.ok, result.error
    row=result.raw['connector_runtime'][0]
    assert row['state']==('ready' if connected else 'sign_in')
    assert any(e['kind']=='tool_result' and e['is_error']==(not connected) for e in events)
    assert result.output=='Qualified report'


@pytest.mark.parametrize('reply,state', [
    ({'result':None},'unknown'),
    ({'error':{'message':'method unavailable'}},'unknown'),
    ({'result':{'data':[]}},'missing'),
    ({'result':{'data':[{'name':'broker','authStatus':'oAuth','tools':{},'runtimeStatus':'connected'}]}},'unknown'),
    ({'result':{'data':[{'name':'broker','authStatus':'oAuth','tools':{'read':{}},'runtimeStatus':'starting'}]}},'unknown')])
def test_no_ready_label_without_live_callable_inventory(reply,state):
    row=mcp_runtime.status('broker',reply)
    assert row['state']==state and row['error']


def test_refresh_coordination_is_enabled_for_all_armada_codex_processes():
    assert 'features.mcp_oauth_refresh_coordination=true' in _feature_args()


def test_concurrent_runtimes_serialize_startup_but_release_before_model_work(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    marker = str(tmp_path / 'startup-active')
    script = tmp_path / 'concurrent.py'
    script.write_text('''import json,sys,time,os
def reply(x): print(json.dumps(x),flush=True)
for line in sys.stdin:
    x=json.loads(line)
    if x.get('method')=='initialize': reply({'id':1,'result':{}})
    elif x.get('method')=='thread/start': reply({'id':2,'result':{'thread':{'id':'fresh'}}})
    elif x.get('method')=='mcpServerStatus/list':
        fd=os.open(MARKER,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        time.sleep(.15)
        os.close(fd);os.unlink(MARKER)
        reply({'id':4,'result':{'data':[{'name':'broker','tools':{'read':{}},'runtimeStatus':'connected','authStatus':'oAuth'}]}})
    elif x.get('method')=='turn/start':
        time.sleep(.15)
        reply({'id':3,'result':{}})
        reply({'method':'turn/completed','params':{'turn':{'status':'completed'}}})
'''.replace('MARKER',repr(marker)),encoding='utf-8')
    def run(_):
        engine=CodexEngine()
        engine.allowed_mcp_ids={'broker'}
        engine._turn_mcp_ids=('broker',)
        engine._launcher=lambda:[sys.executable,'-u',str(script)]
        engine._mcp_args=lambda *a,**kw:[]
        return engine.run_stream('','read',allow_tools=True,cwd=str(tmp_path),on_event=lambda e:None,timeout=5)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,range(2)))
    assert all(r.ok for r in results), [r.error for r in results]


def test_connector_errors_are_separate_from_original_completed_job_answer(tmp_path, monkeypatch):
    from armada import runner, job_history, util
    from armada.engine.mock import MockEngine
    from armada.engine.base import RunResult
    ad=tmp_path/'agents/a'
    (ad/'jobs').mkdir(parents=True)
    util.write_json_atomic(tmp_path/'realm.json',{'name':'Test'})
    util.write_json_atomic(ad/'agent.json',{'id':'a'})
    util.write_json_atomic(ad/'jobs/work.json',{'id':'work','prompt':'Write qualified report'})
    engine=MockEngine()
    monkeypatch.setattr(engine,'run',lambda **kwargs:RunResult(ok=True,output='Report complete; live audit unavailable.',
        raw={'connector_runtime':[{'server':'broker','state':'sign_in','error':'invalid_grant: Refresh token is not active'}]}))
    report=runner.run_job(tmp_path,'a','work',engine=engine)
    assert report['result']['execution']=='completed' and report['status']=='warn'
    assert 'invalid_grant' in report['result']['app_errors'][0]
    assert job_history.transcript(ad,report)['content']=='Report complete; live audit unavailable.'
