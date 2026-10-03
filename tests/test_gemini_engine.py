"""Google integration contracts, offline and independent of the owner's saved account."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from armada import appconfig, models, providers
from armada.engine import gemini as g, get_engine
from armada.engine.contracts import ExecutionPolicy, RunRequest
from armada.engine.process import ProcessResult
from armada.engine.selection import engine_for, model_provider

_REAL_LAUNCHER = g.GeminiEngine._launcher


@pytest.fixture
def engine(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path/'home'))
    monkeypatch.setattr(g.GeminiEngine, '_launcher', lambda self: ['agy-fixture'])
    monkeypatch.setattr(g.GeminiEngine, 'auth_status', lambda self, force=False: {'ok':True,'logged_in':True})
    monkeypatch.setattr(g, 'cached_models', lambda: [
        {'id':'gemini-3.8-flash','label':'Google · Gemini 3.8 Flash','efforts':['low','medium','high']},
        {'id':'gemini-3.1-pro','label':'Google · Gemini 3.1 Pro','efforts':['low','high']}])
    return g.GeminiEngine()


def stream(monkeypatch, events, result=None, inspect=None):
    def call(args, **kwargs):
        if inspect: inspect(args, kwargs)
        for event in events: kwargs['on_line'](json.dumps(event))
        return result or ProcessResult(returncode=0)
    monkeypatch.setattr(g, 'supervise', call)


def final(response='Verified.', **extra):
    return {'event':'result','result':{'status':'SUCCESS','response':response,**extra}}


def test_model_routes_include_agent_and_job_overrides(tmp_path):
    (tmp_path/'realm.json').write_text('{"default_model":"gpt-6-sol"}')
    assert model_provider('gemini-3.8-flash-low') == 'gemini'
    assert engine_for(tmp_path, {'model':'gemini:auto'}) == 'gemini'
    assert engine_for(tmp_path, {'model':'gpt-6-sol'}, {'model':'gemini-3.1-pro'}) == 'gemini'
    assert isinstance(get_engine('gemini'), g.GeminiEngine)


def test_live_catalogue_excludes_other_provider_models():
    rows = g.parse_models('gemini-3.8-flash-high\tGemini 3.8 Flash (High)\n'
        'gemini-3.8-flash-low\tGemini 3.8 Flash (Low)\nclaude-opus\tClaude Opus\n')
    assert rows == [{'id':'gemini-3.8-flash','label':'Google · Gemini 3.8 Flash','efforts':['high','low']}]


@pytest.mark.skipif(g.os.name != 'nt', reason='Windows desktop install discovery')
@pytest.mark.parametrize('local', [None, 'stale-profile'])
def test_desktop_launch_finds_installed_cli_without_fresh_environment(monkeypatch, tmp_path, local):
    monkeypatch.setattr(g.GeminiEngine, '_launcher', _REAL_LAUNCHER)
    home = tmp_path/'home'
    cli = home/'AppData/Local/agy/bin/agy.exe'
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b'fixture')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.setattr(g.shutil, 'which', lambda binary: None)
    if local is None: monkeypatch.delenv('LOCALAPPDATA', raising=False)
    else: monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/local))
    assert g.GeminiEngine()._launcher() == [str(cli)]
    assert g.GeminiEngine(binary='custom-agy')._launcher() is None


def test_friendly_labels_group_effort_variants_under_actual_model():
    from armada.webui.agentbits import _pretty_model, _model_chip
    assert _pretty_model('gemini-3.7-flash-low') == _pretty_model('gemini-3.7-flash') == 'Gemini 3.7 Flash'
    assert 'Gemini 3.7 Flash · low' in _model_chip('gemini-3.7-flash','low')


def test_stream_and_usage_preserve_output_without_double_counting_cache(engine, monkeypatch, tmp_path):
    seen = []
    stream(monkeypatch, [
        {'event':'init'},
        {'event':'step_update','step_update':{'step_type':'agent_response','text_delta':'Verified'}},
        {'event':'step_update','step_update':{'step_type':'agent_response','text_delta':'.','state':'DONE'}},
        final(usage={'input_tokens':100,'cache_read_tokens':80,'output_tokens':20,'thinking_tokens':5})])
    result = engine.run_stream('system','prompt',cwd=tmp_path,on_event=seen.append)
    assert result.ok and result.model == 'gemini-3.8-flash-medium'
    assert ''.join(e['text'] for e in seen if e['kind']=='text') == result.output == 'Verified.'
    assert result.usage.total == 120 and result.usage.input == 20
    assert not list((Path.home()/'.gemini/config/projects').glob('armada-*.json'))


def test_scoped_project_and_custom_agent_never_inherit_ambient_tools(engine, monkeypatch, tmp_path):
    own = tmp_path/'realm/agents/test'; own.mkdir(parents=True)
    extra = tmp_path/'approved'; extra.mkdir()
    engine = engine.configure(ExecutionPolicy(writable_roots=(str(tmp_path/'realm'), str(extra))))
    def inspect(args, kwargs):
        assert '--dangerously-skip-permissions' not in args
        pid = args[args.index('--project')+1]
        config = json.loads((Path.home()/'.gemini/config/projects'/f'{pid}.json').read_text())
        grants = config['permissionGrants']['permissionGrants']
        assert grants['allow'] == [f'write_file({own.as_posix()})',f'write_file({extra.as_posix()})']
        assert 'command(*)' in grants['deny'] and 'read_url(*)' in grants['deny']
        agent = (Path(kwargs['cwd'])/'.agents/agents/armada-turn.md').read_text()
        front = json.loads(agent.split('---')[1])
        assert front['excludeDefaultComponents'] is True
        assert front['inheritMcp'] is front['inheritCustomizations'] is False
        assert 'run_command' not in front['tools'] and 'search_web' not in front['tools']
        assert 'How much to write (Brief)' in agent
        assert str(tmp_path/'realm') not in args
    stream(monkeypatch,[final()],inspect=inspect)
    assert engine.run_stream('system','prompt',cwd=own,allow_tools=True,verbosity='brief').ok


def test_tool_events_have_canonical_names_and_paths(engine, monkeypatch, tmp_path):
    seen=[]
    tool={'event':'step_update','step_update':{'step_type':'tool','step_index':4,'tool_name':'write_to_file',
        'state':'ACTIVE','tool_info':{'parameters':{'TargetFile':'report.md'}}}}
    done=json.loads(json.dumps(tool)); done['step_update']['state']='DONE'
    stream(monkeypatch,[tool,done,done,final()])
    assert engine.run_stream('','',cwd=tmp_path,on_event=seen.append).ok
    assert [(e['kind'],e['id']) for e in seen] == [('tool','4'),('tool_result','4')]
    assert seen[0]['name']=='Write' and seen[0]['input']['file_path']=='report.md'


@pytest.mark.parametrize('events,result,message',[
    ([],ProcessResult(returncode=0),'without a final result'),
    ([final('')],ProcessResult(returncode=0,stderr='jetski: no output produced — write_file auto-denied'),'write_file auto-denied'),
    ([final()],ProcessResult(returncode=0,timed_out=True),'timed out'),
    ([final()],ProcessResult(returncode=0,cancelled=True),'stopped'),
    ([{'event':'result','result':{'status':'ERROR','error':'specific provider error'}}],None,'specific provider error')])
def test_no_false_success(engine, monkeypatch, tmp_path, events, result, message):
    stream(monkeypatch,events,result)
    outcome=engine.run_stream('','',cwd=tmp_path)
    assert not outcome.ok and message in outcome.error


@pytest.mark.parametrize('kwargs,message',[
    ({'only_tools':['Read']},'sealed'),({'max_budget_usd':1},'budget'),
    ({'fallback_model':'gemini-3.1-pro'},'fallback'),({'disallowed_tools':['mcp__server__individual']},'individual')])
def test_unsupported_requirements_fail_before_launch(engine, monkeypatch, tmp_path, kwargs, message):
    monkeypatch.setattr(g,'supervise',lambda *a,**k: pytest.fail('unsafe request launched'))
    with pytest.raises(ValueError,match=message): engine.run_stream('','',cwd=tmp_path,**kwargs)


def test_missing_assigned_connector_fails_closed(engine, tmp_path):
    engine.allowed_mcp_ids=frozenset({'ibkr'})
    with pytest.raises(ValueError,match='not configured for Gemini'):
        engine.run_stream('','',cwd=tmp_path,allow_tools=True)


@pytest.mark.parametrize('path',['chat','job'])
@pytest.mark.parametrize('enabled',[True,False])
@pytest.mark.parametrize('granted',[True,False])
def test_real_filesystem_extension_maps_to_scoped_native_tools(engine, monkeypatch, tmp_path, path, enabled, granted):
    from armada import runner, util
    own = tmp_path/'agents/health'
    cap = {'id':'filesystem','extension_id':'ant.dir.ant.anthropic.filesystem','enabled':enabled,
           'command':'node legacy-extension.js D:/Work'}
    util.write_json_atomic(tmp_path/'realm.json',{'name':'Fixture','default_model':'gemini-3.8-flash',
        'toolkit':{'extensions':[cap]}})
    util.write_json_atomic(own/'agent.json',{'id':'health','allow_tools':True,
        'toolkit':{'extensions':[{'id':'filesystem'}] if granted else []}})
    util.write_json_atomic(own/'jobs/ping.json',{'id':'ping','prompt':'Test ping'})
    launches = []
    def inspect(args, kwargs):
        launches.append(args)
        content = (Path(kwargs['cwd'])/'.agents/agents/armada-turn.md').read_text()
        front = json.loads(content.split('---')[1])
        assert front['mcpServers'] == []  # No Google MCP setup or ambient legacy command.
        effective = enabled and granted
        assert bool(set(front['tools']) & set(g._FILE_TOOLS)) is effective
        project = args[args.index('--project')+1]
        config = json.loads((Path.home()/'.gemini/config/projects'/f'{project}.json').read_text())
        allowed = config['permissionGrants']['permissionGrants']['allow']
        assert not any(s.startswith('mcp(') for s in allowed)
        assert allowed == ([f'write_file({own.as_posix()})'] if effective else [])
        assert ('No separate filesystem connector login is needed' in content) is effective
    stream(monkeypatch,[final('PONG\nARMADA_JOB_RESULT: SUCCESS')],inspect=inspect)
    result = (runner.chat(tmp_path,'health','main','Test ping',engine='auto') if path=='chat'
              else runner.run_job(tmp_path,'health','ping',engine='auto'))
    assert launches and result['status'] in ('ok','warn')


def test_filesystem_server_name_alone_never_bypasses_mcp_configuration(engine, tmp_path):
    from armada import runner, util
    util.write_json_atomic(tmp_path/'realm.json',{'toolkit':{'extensions':[{'id':'filesystem'}]}})
    util.write_json_atomic(tmp_path/'agents/a/agent.json',{'id':'a','toolkit':{'extensions':[{'id':'filesystem'}]}})
    denied = runner._tool_grants(tmp_path,'a',engine,True)
    assert not engine.native_filesystem_ids
    with pytest.raises(ValueError,match='not configured for Gemini'):
        engine.run_stream('','',cwd=tmp_path/'agents/a',allow_tools=True,disallowed_tools=denied)


def test_provider_local_connectors_are_explicitly_selected(engine):
    path=Path.home()/'.gemini/config/mcp_config.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'mcpServers':{'allowed':{'command':'fixture'},'ambient':{'command':'other'}}}))
    engine.allowed_mcp_ids=frozenset({'allowed'})
    config=json.loads(engine._agent('system',True,[]).split('---')[1])
    assert [s['name'] for s in config['mcpServers']]==['allowed']
    assert not json.loads(engine._agent('',True,['mcp__allowed__*']).split('---')[1])['mcpServers']


def test_effort_and_estimated_gradient_match_effective_gemini_settings(engine, monkeypatch, tmp_path):
    models_used=[]
    stream(monkeypatch,[final()],inspect=lambda args,kw: models_used.append(args[args.index('--model')+1]))
    engine.run_stream('','',model='gemini-3.1-pro',effort='medium',cwd=tmp_path)
    engine.run_stream('','',model='gemini-3.8-flash-high',effort='max',cwd=tmp_path)
    assert models_used==['gemini-3.1-pro-high','gemini-3.8-flash-high']
    assert models.combo_index('gemini-3.1-pro','medium')==models.combo_index('gemini-3.1-pro','high')


def test_saved_login_reused_without_interactive_auth(monkeypatch):
    monkeypatch.setattr(g,'_auth_cache',None)
    monkeypatch.setattr(g.GeminiEngine,'_launcher',lambda self:['agy'])
    calls=[]
    def probe(self,args):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='gemini-3.8-flash-low\tGemini 3.8 Flash (Low)',stderr='')
    monkeypatch.setattr(g.GeminiEngine,'_probe',probe)
    assert g.GeminiEngine().auth_status()['logged_in']
    assert g.GeminiEngine().auth_status()['logged_in']
    assert calls==[['models']]


def test_quota_is_actual_weekly_and_cached(engine, monkeypatch):
    monkeypatch.setattr(g,'_usage_cache',None)
    calls=[]
    def probe(args):
        calls.append(args)
        return SimpleNamespace(stdout='Gemini Models\tWeekly Limit Remaining\t83%\t2099-10-08T18:11:29Z',returncode=0)
    monkeypatch.setattr(engine,'_probe',probe)
    assert engine.usage_limits()['weekly']['pct']==17
    assert 'session' not in engine.usage_limits()
    assert len(calls)==1


def test_connected_google_exposes_live_options_and_disconnect_blocks_runs(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(g.GeminiEngine,'_probe',lambda self,args:SimpleNamespace(stdout='1.2.14',returncode=0))
    assert providers.status('gemini')['connected']
    assert 'gemini-3.8-flash' in dict(models.options(tmp_path))
    providers.disconnect('gemini')
    with pytest.raises(ValueError,match='disconnected'): engine.execute(RunRequest('',''))


@pytest.mark.parametrize('path',['chat','job'])
def test_public_runner_uses_gemini_and_persists_usage(engine, monkeypatch, tmp_path, path):
    from armada import runner, util
    own=tmp_path/'agents/a'
    util.write_json_atomic(tmp_path/'realm.json',{'name':'Gemini fixture','default_model':'gemini-3.8-flash'})
    util.write_json_atomic(own/'agent.json',{'id':'a','allow_tools':False})
    util.write_json_atomic(own/'jobs/work.json',{'id':'work','prompt':'hello','model':'gemini-3.1-pro','effort':'low'})
    stream(monkeypatch,[final('Verified.\nARMADA_JOB_RESULT: SUCCESS',usage={'input_tokens':10,'output_tokens':5})])
    result=(runner.chat(tmp_path,'a','main','hello',engine='auto') if path=='chat' else runner.run_job(tmp_path,'a','work',engine='auto'))
    assert result['status']==('ok' if path=='chat' else 'warn')  # Legacy success preserves an audit warning.
    report=json.loads((own/'runs/a.jsonl').read_text(encoding='utf-8').splitlines()[-1])
    assert report['engine']=='gemini' and report['model']==('gemini-3.8-flash-high' if path=='chat' else 'gemini-3.1-pro-low')
    assert report['tokens']['total']==15 and report['run_id']
