"""Native apps obey logical grants and fail closed before a model turn."""
import json
import sys

import pytest

from armada import capabilities, codex_apps, connector_registry as registry, connector_runtime as runtime, runner, util
from armada.engine.codex import CodexEngine

APP = 'connector_synthetic_drive'
OTHER = 'connector_synthetic_mail'


@pytest.fixture
def realm(tmp_path):
    util.write_json_atomic(tmp_path/'realm.json', {'name': 'Synthetic native apps'})
    util.write_json_atomic(tmp_path/'agents/reviewer/agent.json', {'id': 'reviewer', 'allow_tools': True})
    return tmp_path


def test_add_service_requires_no_codex_account_and_connect_links_native_app(realm, monkeypatch):
    monkeypatch.setattr(codex_apps, 'rpc', lambda *a, **kw: pytest.fail('Adding a service must not call a provider'))
    cid = registry.save(realm, service='google-drive', engine='codex')['capability']
    cap = capabilities.find(realm, cid)[1]
    assert cap['provider_bindings'] == {} and cap['reach'] == 'codex'
    assert runtime.connection_detail(cap, 'codex', 'unsupported')['action'] == 'connect'
    assert runtime.connection_detail(cap, 'claude', 'unsupported')['action'] == 'connect'
    assert runtime.connection_detail(cap, 'gemini', 'unsupported')['state'] == 'unsupported'
    monkeypatch.setattr(codex_apps, 'service', lambda *a, **kw: {'app_id': APP, 'name': 'Google Drive'})
    monkeypatch.setattr(runtime, 'open_native_setup', lambda cap, provider: {'ok': True})
    assert runtime.connect_codex(cap, realm)['ok']
    assert capabilities.find(realm, cid)[1]['provider_bindings'] == {'codex': {'app_id': APP}}
    capabilities.grant(realm, 'reviewer', cid)
    engine, _ = runner._prepare_agent_run(realm, 'reviewer', 'codex', True)
    assert engine.allowed_app_ids == {APP}
    assert not engine.allowed_mcp_ids and not engine.connector_requirements
    inspector, _ = runner._prepare_agent_run(realm, 'reviewer', 'codex', True, {'inspector': True})
    assert not inspector.allowed_app_ids
    # A Codex-only connector is withheld on Claude rather than failing the turn (capreach): the
    # agent is told it is unavailable on that engine.
    claude_engine, _ = runner._prepare_agent_run(realm, 'reviewer', 'claude', True)
    assert cid not in (claude_engine.allowed_mcp_ids or ())
    capabilities.revoke(realm, 'reviewer', cid)
    runner._tool_grants(realm, 'reviewer', engine, True)
    assert not engine.allowed_app_ids
    engine, _ = runner._prepare_agent_run(realm, 'reviewer', 'codex', True)
    assert not engine.allowed_app_ids


def test_native_tools_never_create_blanket_codex_apps_capability(realm):
    runner._record_used_capabilities(realm, ['mcp__codex_apps__synthetic_tool'])
    assert capabilities.catalogue(realm)['connectors'] == []


def test_reconfiguring_adapter_never_inherits_native_grants():
    from armada.engine.contracts import ExecutionPolicy
    granted=CodexEngine().configure(ExecutionPolicy(allowed_app_ids=frozenset({APP})))
    assert granted.allowed_app_ids == {APP}
    assert not granted.configure(ExecutionPolicy()).allowed_app_ids


def test_native_import_preserves_one_logical_connector_and_duplicate_denial(realm, monkeypatch):
    monkeypatch.setattr(registry, 'inventory', lambda *a: [{'server_name': 'app:'+APP, 'app_id': APP, 'label': 'Drive'}])
    cid = registry.save(realm, provider='codex', server_name='app:'+APP)['capability']
    with pytest.raises(ValueError, match='already belongs'):
        registry.save(realm, provider='codex', server_name='app:'+APP)
    capabilities.grant(realm, 'reviewer', cid)
    data = util.read_json_state(realm/'realm.json')
    data['toolkit']['connectors'].append({'id':'denied-alias', 'enabled': False,
        'provider_bindings': {'codex': {'app_id': APP}}})
    util.write_json_atomic(realm/'realm.json', data)
    assert not capabilities.provider_policy(capabilities.execution_policy(realm, 'reviewer'), 'codex').allowed_app_ids


def test_a_native_app_is_never_linked_onto_a_claude_connector(realm, monkeypatch):
    # One row reaches one service (0.99.100): the ChatGPT app gets its own Codex row instead.
    util.write_json_atomic(realm/'realm.json', {'toolkit': {'connectors': [
        {'id':'claude_ai_Google_Drive', 'name':'Google Drive'}]}})
    before = (realm/'realm.json').read_bytes()
    monkeypatch.setattr(codex_apps, 'service', lambda *a, **kw: {'app_id': APP, 'name':'Google Drive'})
    with pytest.raises(ValueError, match='add it for Codex'):
        registry.save(realm, capability='claude_ai_Google_Drive', service='google-drive')
    assert (realm/'realm.json').read_bytes() == before
    capabilities.grant(realm, 'reviewer', 'claude_ai_Google_Drive')
    policy=capabilities.execution_policy(realm,'reviewer')
    assert 'claude_ai_Google_Drive' in capabilities.provider_policy(policy,'claude').allowed_mcp_ids
    assert not capabilities.provider_policy(policy,'codex').allowed_app_ids


@pytest.mark.parametrize('row', [{'app_id':'bad.id'}, {'app_id': APP, 'endpoint':'https://example.com'}, {'app_id': ['bad']}])
def test_invalid_native_bindings_rejected(row):
    with pytest.raises(ValueError):
        registry.policy_bindings({'id':'drive', 'provider_bindings': {'codex':row}})


def test_native_binding_never_authorizes_claude_namespace():
    with pytest.raises(ValueError):
        registry.policy_bindings({'id':'drive', 'provider_bindings': {'claude': {'app_id': APP}}})


def test_grant_never_reenables_owner_disabled_native_app(monkeypatch):
    monkeypatch.setattr(codex_apps, 'inventory', lambda **kw: [])
    monkeypatch.setattr(codex_apps, 'rpc', lambda *a, **kw: {'config': {'apps': {APP: {'enabled': False}}}})
    with pytest.raises(ValueError, match='disabled in Codex'):
        codex_apps.scoped_args({APP})


def test_native_ids_cover_both_documented_runtime_families():
    assert codex_apps.valid_id('asdk_app_synthetic_slack')
    assert codex_apps.valid_id(APP)
    assert not codex_apps.valid_id('asdk_app_bad.key')


def test_scoped_overrides_disable_ambient_and_configured_apps_without_erasing_tool_rules(monkeypatch):
    monkeypatch.setattr(codex_apps, 'inventory', lambda **kw: [{'id': APP}, {'id': OTHER}])
    monkeypatch.setattr(codex_apps, 'rpc', lambda *a, **kw: {'config': {'apps': {
        'configured_alias': {'enabled': True}, APP: {'tools': {'delete': {'enabled': False}}}}}})
    args = codex_apps.scoped_args({APP})
    assert 'apps._default.enabled=false' in args
    assert f'apps.{APP}.enabled=true' in args
    assert f'apps.{OTHER}.enabled=false' in args
    assert 'apps.configured_alias.enabled=false' in args
    assert not any('tools.delete' in arg for arg in args)
    assert not any('features.plugins=true' in arg for arg in args)


@pytest.mark.parametrize('rows', [[], [{'id':APP, 'enabled':True, 'callable':False}],
    [{'id':APP, 'enabled':True, 'callable':True}, {'id':OTHER, 'enabled':True, 'callable':True}],
    [{'id':APP, 'enabled':True, 'callable':'true'}]])
def test_unavailable_or_ungranted_native_tool_blocks_turn(rows):
    with pytest.raises(ValueError):
        codex_apps.verify_snapshot({'apps':rows}, {APP})


def test_native_readiness_is_runtime_evidence_only():
    cap = {'id':'drive', 'provider_bindings': {'codex': {'app_id': APP}}}
    assert runtime.codex_connection(cap, {}) == 'missing'
    assert runtime.codex_connection(cap, {APP:{'enabled':True, 'callable':False}}) == 'sign_in'
    assert runtime.codex_connection(cap, {APP:{'enabled':True, 'callable':True}}) == 'ready'
    assert runtime.codex_connection(cap, None) == 'unknown'
    setup = runtime.connector_setup(cap, 'codex')
    assert not setup['snippet'] and 'OAuth client' in setup['instructions']


@pytest.mark.parametrize('extra', [False, True])
def test_real_transport_checks_thread_before_sending_prompt(tmp_path, monkeypatch, extra):
    script = tmp_path/'server.py'
    script.write_text('''import json,sys
checked=False
for line in sys.stdin:
 m=json.loads(line); method=m.get('method')
 if method=='initialize': print(json.dumps({'id':1,'result':{}}),flush=True)
 elif method=='thread/start': print(json.dumps({'id':2,'result':{'thread':{'id':'test'}}}),flush=True)
 elif method=='app/installed':
  assert m['params']['threadId']=='test'
  checked=True
  rows=[{'id':'connector_synthetic_drive','enabled':True,'callable':True}]
  if EXTRA: rows.append({'id':'connector_synthetic_mail','enabled':True,'callable':True})
  print(json.dumps({'id':5,'result':{'apps':rows}}),flush=True)
 elif method=='turn/start':
  assert checked and not EXTRA
  assert any(i.get('path')=='app://connector_synthetic_drive' for i in m['params']['input'])
  print(json.dumps({'id':3,'result':{}}),flush=True)
  print(json.dumps({'method':'turn/completed','params':{'threadId':'test','turn':{'status':'completed'}}}),flush=True)
'''.replace('EXTRA', repr(extra)), encoding='utf-8')
    engine=CodexEngine()
    engine.allowed_app_ids={APP}
    monkeypatch.setattr(engine,'_launcher',lambda:[sys.executable,'-u',str(script)])
    monkeypatch.setattr(engine,'_mcp_args',lambda *a,**kw:[])
    monkeypatch.setattr(codex_apps,'scoped_args',lambda *a,**kw:[])
    result=engine.run_stream('synthetic instructions','synthetic prompt',cwd=str(tmp_path),allow_tools=True,timeout=10)
    assert result.ok is (not extra), result.error
    if extra: assert 'ungranted' in result.error
