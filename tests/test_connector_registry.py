"""One logical grant maps to independently authenticated engine registrations."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada import capabilities, connector_registry as registry, connector_runtime as runtime, runner, util
from armada.engine import claude, codex, gemini
from armada.routes.caps import CapabilityRoutes


@pytest.fixture
def realm(tmp_path):
    util.write_json_atomic(tmp_path/'realm.json', {'name': 'Synthetic connectors'})
    util.write_json_atomic(tmp_path/'agents/reviewer/agent.json', {'id': 'reviewer', 'allow_tools': True})
    return tmp_path


def test_service_discovery_preserves_account_labels_and_official_endpoint(realm):
    cid = registry.save(realm, service='notion', account_label='Work')['capability']
    cap = capabilities.find(realm, cid)[1]
    assert cap['name'] == 'Notion · Work' and cap['service_id'] == 'notion'
    assert cap['mcp_url'] == 'https://mcp.notion.com/mcp'
    assert cap['account_label'] == 'Work' and 'native_service' not in cap
    with pytest.raises(ValueError, match='account label'):
        registry.save(realm, service='gmail', account_label='bad\nlabel')


def test_import_does_not_persist_private_proxy_path(realm, monkeypatch):
    monkeypatch.setattr(runtime, '_claude_rows', lambda *a: [
        {'name':'private-docs', 'endpoint':'https://proxy.example/secret-account-token', 'remote': True, 'ready': True}])
    cid = registry.save(realm, provider='claude', server_name='private-docs')['capability']
    assert capabilities.find(realm, cid)[1]['provider_bindings']['claude']['endpoint'] == ''
    assert 'secret-account-token' not in (realm/'realm.json').read_text()


def test_unlink_blocks_legacy_fallback_and_keeps_other_engine_and_grant(realm, monkeypatch):
    cid = registry.save(realm, name='Documents', url='https://docs.example/mcp')['capability']
    monkeypatch.setattr(registry, 'inventory', lambda *a: [{'server_name':'documents', 'endpoint':'https://docs.example/mcp'}])
    registry.save(realm, provider='codex', server_name='documents', capability=cid, account_label='Personal')
    capabilities.grant(realm, 'reviewer', cid)
    registry.unlink(realm, cid, 'claude')
    cap = capabilities.find(realm, cid)[1]
    assert registry.provider_cap(cap, 'claude')['_unbound']
    assert not registry.provider_cap(cap, 'codex').get('_unbound')
    policy = capabilities.execution_policy(realm, 'reviewer')
    assert cid in policy.allowed_mcp_ids
    assert not capabilities.provider_policy(policy, 'claude').allowed_mcp_ids
    assert capabilities.provider_policy(policy, 'codex').allowed_mcp_ids == {'documents'}
    with pytest.raises(capabilities.CapabilityPolicyError, match='Connect'):
        runner._prepare_agent_run(realm, 'reviewer', 'claude', True)
    registry.save(realm, provider='claude', server_name='documents', capability=cid)
    assert not registry.provider_cap(capabilities.find(realm, cid)[1], 'claude').get('_unbound')


def test_model_change_warns_only_when_granted_connectors_are_affected(realm):
    cid = registry.save(realm, service='google-drive')['capability']
    assert registry.model_change_warning(realm, 'reviewer', 'claude', 'codex') == ''
    capabilities.grant(realm, 'reviewer', cid)
    assert 'Google Drive' in registry.model_change_warning(realm, 'reviewer', 'claude', 'codex')
    assert registry.model_change_warning(realm, 'reviewer', 'codex', 'codex') == ''


def test_agent_model_change_is_not_partially_saved_before_review(realm):
    from armada.routes.agents import AgentRoutes
    cid = registry.save(realm, service='gmail')['capability']
    capabilities.grant(realm, 'reviewer', cid)
    path = realm/'agents/reviewer/agent.json'
    before = path.read_bytes()
    handler = SimpleNamespace(realm=realm)
    body = {'agent': 'reviewer', 'model': 'gpt-6-sol', 'display': 'Changed'}
    response = AgentRoutes._save_agent(handler, body)
    assert response.get('connector_warning') and path.read_bytes() == before
    assert AgentRoutes._save_agent(handler, {**body, 'confirm_connector_change': True})['ok']
    assert util.read_json_state(path)['model'] == 'gpt-6-sol'


def test_job_model_change_review_is_atomic(realm):
    from armada.routes.jobs import JobRoutes
    cid = registry.save(realm, service='gmail')['capability']
    capabilities.grant(realm, 'reviewer', cid)
    path = realm/'agents/reviewer/jobs/check.json'
    util.write_json_atomic(path, {'id':'check', 'name':'Check', 'model':'claude-haiku-4-5'})
    before = path.read_bytes()
    response = JobRoutes._save_job(SimpleNamespace(realm=realm), {'agent':'reviewer', 'job':'check', 'model':'gpt-6-sol'})
    assert response.get('connector_warning') and path.read_bytes() == before


@pytest.mark.parametrize('value', ['http://example.com/mcp', 'https://u:password@example.com/mcp',
    'https://example.com/mcp?token=secret', 'https://example.com/mcp#secret', 'https://example.com/\nx',
    'https://example.com:bad/mcp', '', None, {'url': 'https://example.com'}])
def test_private_or_invalid_urls_do_not_enter_realm(realm, value):
    before = (realm/'realm.json').read_bytes()
    with pytest.raises(ValueError):
        registry.save(realm, name='Documents', url=value)
    assert (realm/'realm.json').read_bytes() == before


def test_add_and_link_all_engines_without_copying_credentials(realm, monkeypatch):
    cid = registry.save(realm, name='Documents', url='https://docs.example/mcp')['capability']
    for provider, server in [('claude', 'claude.ai Documents'), ('codex', 'work_documents'), ('gemini', 'docs')]:
        monkeypatch.setattr(registry, 'inventory', lambda *a: [{'server_name': server, 'endpoint': 'https://docs.example/mcp',
            'access_token': 'never-copy', 'headers': {'Authorization': 'never-copy'}}])
        registry.save(realm, provider=provider, server_name=server, capability=cid)
    cap = capabilities.find(realm, cid)[1]
    assert len(cap['provider_bindings']) == 3
    runner._record_used_capabilities(realm, ['mcp__work_documents__read', 'mcp__docs__read'])
    assert len(capabilities.catalogue(realm)['connectors']) == 1
    assert 'never-copy' not in (realm/'realm.json').read_text()
    assert capabilities.grant(realm, 'reviewer', cid)['ok']
    policy = capabilities.execution_policy(realm, 'reviewer')
    for provider, sid in [('claude', 'claude_ai_Documents'), ('codex', 'work_documents'), ('gemini', 'docs')]:
        assert capabilities.provider_policy(policy, provider).allowed_mcp_ids == {sid}
        engine, _ = runner._prepare_agent_run(realm, 'reviewer', provider, True)
        assert engine.allowed_mcp_ids == {sid}
        assert engine.connector_requirements == {sid: 'https://docs.example/mcp'}
    assert capabilities.revoke(realm, 'reviewer', cid)['ok']
    policy = capabilities.execution_policy(realm, 'reviewer')
    assert all(not capabilities.provider_policy(policy, p).allowed_mcp_ids for p in registry.PROVIDERS)


def test_import_does_not_claim_other_engines_support_a_private_connector(realm, monkeypatch):
    monkeypatch.setattr(registry, 'inventory', lambda *a: [{'server_name': 'claude.ai Private Docs', 'endpoint': ''}])
    cid = registry.save(realm, provider='claude', server_name='claude.ai Private Docs')['capability']
    capabilities.grant(realm, 'reviewer', cid)
    cap = capabilities.find(realm, cid)[1]
    assert runtime.codex_connection(cap, {}) == 'unsupported'
    assert runtime.gemini_connection(cap, {}) == 'unsupported'
    with pytest.raises(capabilities.CapabilityPolicyError, match='Connect .* Codex'):
        runner._prepare_agent_run(realm, 'reviewer', 'codex', True)


def test_cannot_grant_same_registration_through_two_cards(realm, monkeypatch):
    monkeypatch.setattr(registry, 'inventory', lambda *a: [{'server_name': 'docs', 'endpoint': 'https://docs.example/mcp'}])
    registry.save(realm, name='First', provider='codex', server_name='docs')
    with pytest.raises(ValueError, match='already belongs'):
        registry.save(realm, name='Second', provider='codex', server_name='docs')


def test_denied_alias_beats_granted_logical_binding(realm, monkeypatch):
    monkeypatch.setattr(registry, 'inventory', lambda *a: [{'server_name': 'docs', 'endpoint': ''}])
    cid = registry.save(realm, name='Documents', provider='codex', server_name='docs')['capability']
    capabilities.grant(realm, 'reviewer', cid)
    data = util.read_json_state(realm/'realm.json')
    data['toolkit']['extensions'] = [{'id': 'docs', 'enabled': False}]
    util.write_json_atomic(realm/'realm.json', data)
    assert not capabilities.provider_policy(capabilities.execution_policy(realm, 'reviewer'), 'codex').allowed_mcp_ids


@pytest.mark.parametrize('provider', registry.PROVIDERS)
def test_configuration_changes_fail_before_tool_execution(provider, tmp_path, monkeypatch):
    engine = {'claude': claude.ClaudeEngine, 'codex': codex.CodexEngine, 'gemini': gemini.GeminiEngine}[provider]()
    engine.connector_requirements = {'docs': 'https://approved.example/mcp'}
    engine.allowed_mcp_ids = {'docs'}
    if provider == 'claude':
        monkeypatch.setattr(engine, '_direct', lambda: ['claude'])
        monkeypatch.setattr(engine, '_launcher', lambda: ['claude'])
        monkeypatch.setattr(claude.subprocess, 'run', lambda args, **kw: SimpleNamespace(returncode=0, stderr='',
            stdout='2.1.263' if '--version' in args else 'docs: https://changed.example/mcp - Connected\n'))
        call = lambda: engine._mcp_args([])
    elif provider == 'codex':
        monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps([
            {'name': 'docs', 'transport': {'url': 'https://changed.example/mcp'}}])))
        call = lambda: engine._mcp_args(True, [])
    else:
        util.write_json_atomic(Path.home()/'.gemini/config/mcp_config.json', {'mcpServers': {
            'docs': {'serverUrl': 'https://changed.example/mcp'}}})
        call = lambda: engine._connectors([])
    with pytest.raises(ValueError, match='different settings'):
        call()


def test_inventory_drops_headers_oauth_env_and_private_urls(monkeypatch):
    from armada import codex_apps
    monkeypatch.setattr(codex_apps, 'inventory', lambda **kw: [])
    monkeypatch.setattr(runtime, 'codex_inventory', lambda: {'docs': {'transport': {
        'url': 'https://docs.example/mcp?secret=hidden', 'headers': {'Authorization': 'Bearer hidden'}},
        'oauth': {'client_secret': 'hidden'}}})
    assert registry.inventory('codex') == [{'server_name': 'docs', 'endpoint': '', 'state': 'configured'}]
    monkeypatch.setattr(runtime, 'gemini_inventory', lambda: {'docs': {'serverUrl': 'https://docs.example/mcp',
        'headers': {'Authorization': 'hidden'}}, 'local': {'command': 'hidden', 'env': {'KEY': 'hidden'}}})
    assert registry.inventory('gemini') == [{'server_name': 'docs', 'endpoint': 'https://docs.example/mcp', 'state': 'configured'}]


def test_bind_route_checks_registration_from_its_engine(realm, monkeypatch):
    handler = CapabilityRoutes(); handler.realm = realm
    monkeypatch.setattr(registry, 'inventory', lambda *a: [])
    assert not handler._connector_action({'action': 'add', 'provider': 'codex', 'server_name': 'invented'})['ok']
    assert handler._connector_action({'action': 'add', 'name': 'Docs', 'url': 'https://docs.example/mcp'})['ok']


def test_claude_registers_public_endpoint_without_unnecessary_oauth(monkeypatch):
    rows = iter([[], [{'name': 'docs', 'ready': True, 'endpoint': 'https://docs.example/mcp'}]])
    monkeypatch.setattr(runtime, '_claude_rows', lambda *a: next(rows))
    monkeypatch.setattr(claude.ClaudeEngine, '_launcher', lambda self: ['claude'])
    calls = []
    monkeypatch.setattr(runtime.subprocess, 'run', lambda args, **kw: calls.append(args) or SimpleNamespace(returncode=0))
    assert runtime.connect_claude({'id': 'docs', 'mcp_url': 'https://docs.example/mcp'})['state'] == 'ready'
    assert calls == [['claude', 'mcp', 'add', '--scope', 'user', '--transport', 'http', 'docs', 'https://docs.example/mcp']]


def test_gemini_connect_registers_without_claiming_authentication(monkeypatch):
    monkeypatch.setattr(runtime, 'gemini_inventory', lambda: {})
    monkeypatch.setattr(gemini.GeminiEngine, '_launcher', lambda self: ['agy'])
    calls = []
    monkeypatch.setattr(gemini.GeminiEngine, '_probe', lambda self, args: calls.append(args) or SimpleNamespace(returncode=0))
    result = runtime.connect_gemini({'id': 'docs', 'mcp_url': 'https://docs.example/mcp'})
    assert result['state'] == 'configured' and result['action'] == 'authenticate'
    assert calls == [['mcp', 'add', '--type', 'http', 'docs', 'https://docs.example/mcp']]


def test_gemini_does_not_overwrite_existing_registration(monkeypatch):
    monkeypatch.setattr(runtime, 'gemini_inventory', lambda: {'docs': {'serverUrl': 'https://different.example/mcp'}})
    assert not runtime.connect_gemini({'id': 'docs', 'mcp_url': 'https://docs.example/mcp'})['ok']


def test_forged_binding_fails_closed(realm):
    data = {'toolkit': {'connectors': [{'id': 'docs', 'provider_bindings': {'codex': {'server_name': '*'}}}]}}
    util.write_json_atomic(realm/'realm.json', data)
    with pytest.raises(capabilities.CapabilityPolicyError):
        capabilities.execution_policy(realm, 'reviewer')


def test_codex_approval_translation_is_invocation_scoped_to_granted_connector(monkeypatch):
    engine = codex.CodexEngine()
    engine.allowed_mcp_ids = {'docs'}
    engine.connector_requirements = {'docs': ''}
    monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps([
        {'name': n, 'transport': {'url': 'https://example.com/mcp'}} for n in ['docs', 'ambient']])))
    args = engine._mcp_args(True, [])
    assert 'mcp_servers.docs.default_tools_approval_mode="approve"' in args
    assert 'mcp_servers.ambient.enabled=false' in args
    assert not any('ambient.default_tools_approval' in value for value in args)
    assert not any('default_tools_approval' in value for value in engine._mcp_args(False, []))
    assert not any('default_tools_approval' in value for value in engine._mcp_args(True, ['mcp__docs']))
