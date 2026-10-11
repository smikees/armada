"""Connector preparation cannot grant access or overwrite arbitrary provider settings."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada import capabilities, connector_runtime as runtime, providers, runner, util
from armada.connector_tools import ConnectorTools, claude_args, codex_args
from armada.engine.claude import ClaudeEngine
from armada.engine.mcp import claude_rows


@pytest.fixture
def realm(tmp_path):
    util.write_json_atomic(tmp_path/'realm.json', {'name':'Synthetic', 'toolkit':{'connectors':[
        {'id':'docs', 'name':'Documents', 'mcp_url':'https://docs.example/mcp', 'enabled':True},
        {'id':'off', 'mcp_url':'https://off.example/mcp', 'enabled':False}]}})
    for aid in ('reviewer','other'):
        util.write_json_atomic(tmp_path/f'agents/{aid}/agent.json', {'id':aid})
    capabilities.grant(tmp_path,'reviewer','docs')
    return tmp_path


def test_real_claude_transport_suffix_and_auth_status_are_parsed():
    rows = claude_rows('eodhd: https://mcp.example/v2/mcp (HTTP) - ! Needs authentication\n'
                       'docs: https://docs.example/mcp (SSE) - ✓ Connected\n')
    assert rows[0]['endpoint'] == 'https://mcp.example/v2/mcp' and rows[0]['state'] == 'sign_in'
    assert not rows[0]['ready'] and rows[1]['ready']
    assert rows[1]['endpoint'] == 'https://docs.example/mcp'


def test_bound_claude_endpoint_is_not_mistaken_for_different_settings(monkeypatch):
    monkeypatch.setattr(ClaudeEngine,'_launcher',lambda s:['claude'])
    monkeypatch.setattr(runtime.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,
        stdout='docs: https://docs.example/mcp (HTTP) - ! Needs authentication'))
    cap={'id':'logical','provider_bindings':{'claude':{'server_name':'docs','endpoint':'https://docs.example/mcp'}}}
    assert runtime.claude_connection(cap,runtime.claude_inventory()) == 'sign_in'


def test_connect_only_uses_existing_approved_identity_and_rechecks_revocation(realm, monkeypatch):
    calls=[]
    monkeypatch.setattr(providers,'status',lambda *a,**kw:{'connected':True})
    monkeypatch.setattr(runtime,'connect_claude',lambda cap,root:calls.append(cap['id']) or {'ok':True,'state':'sign_in'})
    tools=ConnectorTools(realm,'reviewer')
    for cid in ('off','missing'):
        with pytest.raises(ValueError):tools.call('connect_connector',{'capability':cid,'provider':'claude'})
    with pytest.raises(ValueError):
        tools.call('connect_connector',{'capability':'docs','provider':'claude','url':'https://other.example/mcp'})
    assert tools.call('connect_connector',{'capability':'docs','provider':'claude'})['state']=='sign_in'
    capabilities.revoke(realm,'reviewer','docs')
    with pytest.raises(ValueError):tools.call('connect_connector',{'capability':'docs','provider':'claude'})
    assert calls==['docs']
    assert tools.actions==[{'tool':'connect_connector','capability':'docs','provider':'claude',
                           'agent':'reviewer','ok':True,'state':'sign_in'}]


def test_request_is_owner_approval_not_a_grant_and_only_coordinator_can_target_others(realm):
    tools=ConnectorTools(realm,'reviewer')
    with pytest.raises(ValueError):
        tools.call('request_connector_access',{'capability':'docs','agent':'other','reason':'Review'})
    util.write_json_atomic(realm/'agents/reviewer/agent.json',{'id':'reviewer','coordinator':True})
    assert tools.call('request_connector_access',{'capability':'docs','agent':'other','reason':'Review'})['ok']
    assert not capabilities.may_use(realm,'other','docs')
    assert len(list(capabilities.iter_requests(realm)))==1


def test_sidecar_expiry_cancellation_and_configuration_preserve_normal_grants(realm, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, 'tempdir', str(realm))
    engine=ClaudeEngine();engine.allowed_mcp_ids={'docs'}
    with ConnectorTools(realm,'reviewer') as tools:
        configured=tools.configure(engine)
        assert configured.allowed_mcp_ids=={'docs'} and not hasattr(configured,'managed_tools')
        assert configured.connector_tools is tools and not hasattr(engine,'connector_tools')
        cfg=json.loads(tools.config_path.read_text())
        assert set(cfg['mcpServers'])=={tools.server_name}
        assert '--strict-mcp-config' not in claude_args(tools)
        assert any(tools.server_name+'.enabled=true' in s for s in codex_args(tools))
    with pytest.raises(ValueError,match='expired'):tools.call('list_connectors',{})
    stopped=ConnectorTools(realm,'reviewer',cancelled=lambda:True)
    with pytest.raises(ValueError,match='stopped'):stopped.call('list_connectors',{})


def test_host_setup_tools_are_never_discovered_as_user_connectors(realm):
    before=(realm/'realm.json').read_bytes()
    runner._record_used_capabilities(realm,['mcp__armada_setup_123abc__list_connectors'])
    assert (realm/'realm.json').read_bytes()==before


@pytest.mark.parametrize('job_turn', [False, True])
def test_unbound_connector_does_not_abort_turn_and_setup_is_chat_only(realm, monkeypatch, job_turn):
    import tempfile
    from armada import connector_registry as registry
    from armada.engine.base import RunResult
    monkeypatch.setattr(tempfile, 'tempdir', str(realm))
    monkeypatch.setattr(registry, 'inventory', lambda *a: [{'server_name':'documents', 'endpoint':'https://docs.example/mcp'}])
    registry.save(realm, provider='claude', server_name='documents', capability='docs')
    registry.unlink(realm, 'docs', 'claude')
    captured = []
    class Synthetic(ClaudeEngine):
        def run_stream(self, **kwargs):
            tools = getattr(self, 'connector_tools', None)
            captured.append((tools, self.allowed_mcp_ids, kwargs['system']))
            if tools:
                assert tools.call('list_connectors', {})['connectors']
            return RunResult(ok=True, output='The conversation can continue.', model='claude:default')
    monkeypatch.setattr(runtime, 'connection_snapshot', lambda *a: {'connectors':{}})
    if job_turn:
        util.write_json_atomic(realm/'agents/reviewer/jobs/work.json', {'id':'work','prompt':'Check unrelated text'})
        result=runner.run_job(realm, 'reviewer', 'work', engine=Synthetic(), allow_tools=True)
        assert result['result']['execution']=='completed'
    else:
        result=runner.chat(realm, 'reviewer', 'main', 'Discuss an unrelated topic', engine=Synthetic(), allow_tools=True)
        assert result['ok'] and result['output']=='The conversation can continue.'
    tools, allowed, system = captured[-1]
    assert not allowed
    if job_turn:
        assert tools is None and 'ARMADA provides connector setup tools' not in system
    else:
        assert tools.closed and 'ARMADA provides connector setup tools' in system
        with pytest.raises(ValueError,match='expired'):tools.call('list_connectors',{})


def test_status_list_and_connect_result_never_expose_oauth_urls(realm, monkeypatch):
    monkeypatch.setattr(runtime, 'connection_snapshot', lambda *a: {'connectors': {'docs': {
        'details': {'claude': {'state':'sign_in', 'reason':'Sign in', 'login_url':'https://auth.example/?state=private'}}}}})
    tools=ConnectorTools(realm,'reviewer')
    assert 'private' not in json.dumps(tools.call('list_connectors',{}))
    monkeypatch.setattr(providers,'status',lambda *a,**kw:{'connected':True})
    monkeypatch.setattr(runtime,'connect_claude',lambda *a:{'ok':True,'state':'sign_in','login_url':'https://auth.example/?state=private'})
    assert 'private' not in json.dumps(tools.call('connect_connector',{'capability':'docs','provider':'claude'}))
