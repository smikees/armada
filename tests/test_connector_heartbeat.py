import threading
from types import SimpleNamespace
import pytest
from armada import connector_health as health, connector_runtime as runtime, capabilities, tool_inventory, util


@pytest.fixture
def realm(tmp_path,monkeypatch):
    util.write_json_atomic(tmp_path/'realm.json',{'name':'Synthetic','toolkit':{'connectors':[
        {'id':'claude_ai_Broker','name':'Broker','command':'https://broker.example/mcp','enabled':True}]}})
    monkeypatch.setattr(health,'server_check',lambda endpoint:{'state':'up','http_status':401,'error':''})
    monkeypatch.setattr(health,'incident_check',lambda:{'state':'incident','incidents':['Synthetic provider incident']})
    monkeypatch.setattr('armada.engine.get_engine',lambda provider:SimpleNamespace(configure=lambda policy:SimpleNamespace()))
    monkeypatch.setattr(tool_inventory,'claude_inventory',lambda engine,root:{'claude_ai_Broker':['get_positions']})
    return tmp_path


def test_successful_empty_claude_list_is_a_missing_connector(realm,monkeypatch):
    monkeypatch.setattr(runtime,'_claude_rows',lambda root:[])
    row=health.probe(realm,'claude',['claude_ai_Broker'])['claude_ai_Broker']
    assert row['state']=='down' and row['links']['server']['state']=='up'
    assert 'list was not returned' in row['reason']
    assert row['provider_incident']['incidents']==['Synthetic provider incident']


def test_transport_and_listing_do_not_substitute_for_fetched_tools(realm,monkeypatch):
    monkeypatch.setattr(runtime,'_claude_rows',lambda root:[{'name':'claude.ai Broker','ready':True,'state':'ready'}])
    assert health.probe(realm,'claude',['claude_ai_Broker'])['claude_ai_Broker']['state']=='up'
    monkeypatch.setattr(tool_inventory,'claude_inventory',lambda *a:{})
    row=health.probe(realm,'claude',['claude_ai_Broker'])['claude_ai_Broker']
    assert row['state']=='down' and row['links']['tools']['tool_count']==0


def test_server_outage_and_exact_error_survive_without_secrets(realm,monkeypatch):
    monkeypatch.setattr(runtime,'_claude_rows',lambda root:[{'name':'claude.ai Broker','ready':False,'state':'failed',
        'error':'Failed to connect — HTTP 503 https://host/path/private?token=private bearer hidden'}])
    row=health.probe(realm,'claude',['claude_ai_Broker'])['claude_ai_Broker']
    assert 'HTTP 503' in row['reason']
    assert 'private' not in str(row) and 'hidden' not in str(row)


def test_resolved_query_is_bounded_and_cancellable(monkeypatch):
    def pending(root):
        return {'pending':True,'providers':{'claude':'checking'},'connectors':{'broker':{'claude':'checking'}}}
    monkeypatch.setattr(runtime,'connection_snapshot',pending)
    result=runtime.resolved_snapshot('synthetic',timeout=0)
    assert not result['pending'] and result['connectors']['broker']['claude']=='unknown'
    with pytest.raises(ValueError,match='cancelled'):
        runtime.resolved_snapshot('synthetic',cancelled=lambda:True)


def test_inflight_query_survives_usage_metadata_change(realm,monkeypatch):
    from armada import providers
    calls=[]
    release=threading.Event()
    def status(provider,**kwargs):
        calls.append(provider);release.wait(3)
        return {'connected':False,'detail':'unavailable'}
    monkeypatch.setattr(providers,'status',status)
    try:
        runtime.connection_snapshot(realm)
        original=util.read_json_state(realm/'realm.json')
        original['toolkit']['connectors'][0]['last_seen']='tomorrow'
        original['toolkit']['connectors'][0]['runs']=99
        util.write_json_atomic(realm/'realm.json',original)
        runtime.connection_snapshot(realm)
        assert sorted(calls)==['claude','codex','gemini']
    finally:
        release.set()


def test_preamble_labels_stale_health(realm):
    row={'id':'broker','name':'Broker','provider':'claude','state':'down','checked_at':1,'down_since':1,'reason':'HTTP 503'}
    util.write_json_atomic(health._path(realm),{'connectors':{'claude:broker':row}})
    text=health.context(realm)
    assert 'stale' in text and 'down since' in text and 'HTTP 503' in text


@pytest.mark.parametrize('failure', ['timeout', 'stderr'])
def test_claude_inventory_failure_records_every_grant(monkeypatch, failure):
    import subprocess
    from armada.engine.claude import ClaudeEngine
    from armada import worker
    engine = ClaudeEngine()
    engine.allowed_mcp_ids = {'claude_ai_Broker', 'docs'}
    monkeypatch.setattr(engine, '_direct', lambda: True)
    monkeypatch.setattr(engine, '_launcher', lambda: ['claude'])
    def probe(argv, **kwargs):
        if argv[-1] == '--version':
            return SimpleNamespace(returncode=0, stdout='2.1.319')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(argv, 90)
        return SimpleNamespace(returncode=1, stdout='', stderr='HTTP 503 token=private')
    monkeypatch.setattr(worker, 'run', probe)
    with pytest.raises(ValueError):
        engine._mcp_args([])
    assert {r['server'] for r in engine.connector_unavailable} == engine.allowed_mcp_ids
    assert all(r['state'] == 'missing' for r in engine.connector_unavailable)
    assert 'private' not in str(engine.connector_unavailable)


def test_codex_inventory_records_legacy_missing_grants(monkeypatch):
    from armada.engine.codex import CodexEngine
    engine = CodexEngine()
    engine.allowed_mcp_ids = {'broker'}
    monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0, stdout='[]'))
    engine._mcp_args(True, [])
    assert engine.connector_unavailable[0]['server'] == 'broker'
    assert engine.connector_unavailable[0]['state'] == 'missing'


def test_corrupt_optional_health_context_does_not_break_chat(realm):
    path = health._path(realm)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{broken', encoding='utf-8')
    assert 'unavailable' in health.context(realm)
    # Required pre-start checks remain strict; only optional context degrades.
    with pytest.raises(util.StateError):
        health.request(realm, 'claude', ['claude_ai_Broker'])
