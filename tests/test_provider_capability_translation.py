import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada import runner, util
from armada.engine import claude, codex, gemini
from armada.engine.base import RunResult
from armada.engine.contracts import RunRequest, validate_request

IBKR = 'claude_ai_Interactive_Brokers_IBKR'


@pytest.fixture
def realm(tmp_path):
    util.write_json_atomic(tmp_path/'realm.json', {'name': 'Mixed providers', 'toolkit': {
        'connectors': [{'id': IBKR}, {'id': 'claude.ai Gmail'}, {'id': 'claude.ai Claude Docs'}],
        'extensions': [{'id': 'revoked', 'enabled': False}]}})
    util.write_json_atomic(tmp_path/'agents/finance/agent.json', {'id': 'finance', 'model': 'gpt-6-astra',
        'allow_tools': True, 'toolkit': {'connectors': [{'id': IBKR}], 'extensions': [{'id': 'revoked'}]}})
    util.write_json_atomic(tmp_path/'agents/finance/jobs/check.json', {'id': 'check', 'prompt': 'Fixture only'})
    return tmp_path


@pytest.mark.parametrize('entry', ['chat', 'stream', 'job', 'inbox'])
def test_codex_mixed_catalogue_never_becomes_individual_tool_denials(realm, monkeypatch, entry):
    engine = codex.CodexEngine()
    # The synthetic turn below tests grant translation, not a live Windows sandbox.
    monkeypatch.setattr(engine, '_execution_probe', lambda *a: {"ok": True, "reason": ""})
    launches = []
    monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0,
        stdout=json.dumps([{'name': IBKR}, {'name': 'ambient'}, {'name': 'revoked'}])))
    def stream(self, **kw):
        validate_request('codex', self.capabilities, RunRequest('', '', disallowed_tools=tuple(kw['disallowed_tools'])))
        args = self._mcp_args(True, kw['disallowed_tools'])
        assert self.allowed_mcp_ids == {IBKR}
        assert self._turn_mcp_ids == (IBKR,)
        assert 'mcp_servers.ambient.enabled=false' in args
        assert 'mcp_servers.revoked.enabled=false' in args
        assert f'mcp_servers.{IBKR}.enabled=false' not in args
        assert not kw['disallowed_tools']
        launches.append(True)
        return RunResult(ok=True, output='Fixture completion')
    monkeypatch.setattr(codex.CodexEngine, 'run_stream', stream)
    if entry == 'chat':
        result = runner.chat(realm, 'finance', 'main', 'Fixture', engine=engine)
    elif entry == 'stream':
        result = runner.chat_stream(realm, 'finance', 'main', 'Fixture', lambda event: None, engine=engine)
    elif entry == 'job':
        result = runner.run_job(realm, 'finance', 'check', engine=engine)
    else:
        result = runner.run_job_prompt(realm, 'finance', 'Fixture', engine=engine)
    assert launches and result['status'] in ('ok', 'warn')


def test_revocation_and_no_tools_still_remove_codex_grants(realm, monkeypatch):
    engine = codex.CodexEngine()
    monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps([{'name': IBKR}])))
    runner._tool_grants(realm, 'finance', engine, True)
    util.write_json_atomic(realm/'agents/finance/agent.json', {'id': 'finance'})
    denied = runner._tool_grants(realm, 'finance', engine, True)
    assert not engine.allowed_mcp_ids
    assert f'mcp_servers.{IBKR}.enabled=false' in engine._mcp_args(True, denied)
    runner._tool_grants(realm, 'finance', engine, False)
    assert not engine.allowed_mcp_ids


@pytest.mark.parametrize('provider', [claude.ClaudeEngine, codex.CodexEngine, gemini.GeminiEngine])
def test_disabled_cloud_alias_revokes_canonical_grant(realm, provider):
    config = json.loads((realm/'realm.json').read_text())
    config['toolkit']['connectors'].append({'id': 'claude_ai_Gmail'})
    next(c for c in config['toolkit']['connectors'] if c['id'] == 'claude.ai Gmail')['enabled'] = False
    util.write_json_atomic(realm/'realm.json', config)
    agent = json.loads((realm/'agents/finance/agent.json').read_text())
    agent['toolkit']['connectors'].append({'id': 'claude_ai_Gmail'})
    util.write_json_atomic(realm/'agents/finance/agent.json', agent)
    engine = provider()
    runner._tool_grants(realm, 'finance', engine, True)
    assert 'claude_ai_Gmail' not in engine.allowed_mcp_ids
    assert IBKR in engine.allowed_mcp_ids


def test_gemini_selects_only_granted_provider_local_servers(realm, monkeypatch, tmp_path):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    util.write_json_atomic(tmp_path/'.gemini/config/mcp_config.json', {'mcpServers': {
        IBKR: {'command': 'fixture-only'}, 'ambient': {'command': 'other'}}})
    engine = gemini.GeminiEngine()
    denied = runner._tool_grants(realm, 'finance', engine, True)
    assert not denied
    assert [server['name'] for server in engine._connectors(denied)] == [IBKR]


@pytest.mark.parametrize('granted', [True, False])
def test_claude_cloud_name_maps_to_existing_ibkr_grant(monkeypatch, granted):
    engine = claude.ClaudeEngine()
    engine.allowed_mcp_ids = {IBKR} if granted else set()
    monkeypatch.setattr(engine, '_launcher', lambda: ['claude'])
    def probe(args, **kwargs):
        return SimpleNamespace(returncode=0, stderr='', stdout='2.1.286' if args[-1]=='--version' else
            'claude.ai Interactive Brokers (IBKR): https://broker.invalid/mcp - Connected\n'
            'claude.ai Gmail: https://mail.invalid/mcp - Connected\n')
    monkeypatch.setattr(claude.subprocess, 'run', probe)
    args = engine._mcp_args([])
    blocked = json.loads(args[args.index('--settings')+1])['deniedMcpServers']
    assert ({'serverName': 'claude.ai Interactive Brokers (IBKR)'} in blocked) is not granted
    assert {'serverName': 'claude.ai Gmail'} in blocked


def test_claude_alias_collision_is_blocked(monkeypatch):
    engine = claude.ClaudeEngine()
    engine.allowed_mcp_ids = {IBKR}
    monkeypatch.setattr(engine, '_launcher', lambda: ['claude'])
    def probe(args, **kwargs):
        return SimpleNamespace(returncode=0, stderr='', stdout='2.1.286' if args[-1]=='--version' else
            f'{IBKR}: https://first.invalid - Connected\n'
            'claude.ai Interactive Brokers (IBKR): https://second.invalid - Connected\n')
    monkeypatch.setattr(claude.subprocess, 'run', probe)
    with pytest.raises(ValueError, match='Ambiguous'):
        engine._mcp_args([])


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_portable_registration_keeps_grant_and_revocation(provider, tmp_path, monkeypatch):
    from armada import capabilities
    from armada.engine import get_engine
    from armada.engine.mcp import registration_id
    cid = 'claude.ai Google Drive'
    util.write_json_atomic(tmp_path/'realm.json', {'toolkit': {'connectors': [{'id': cid}]}})
    util.write_json_atomic(tmp_path/'agents/steve/agent.json', {'id': 'steve', 'toolkit': {'connectors': [{'id': cid}]}})
    engine = get_engine(provider)
    runner._tool_grants(tmp_path, 'steve', engine, True)
    assert registration_id(cid) in engine.allowed_mcp_ids
    assert (cid in engine.allowed_mcp_ids) == (provider == 'claude')
    assert capabilities.revoke(tmp_path, 'steve', cid)['ok']
    runner._tool_grants(tmp_path, 'steve', engine, True)
    assert registration_id(cid) not in engine.allowed_mcp_ids


def test_portable_registration_does_not_create_duplicate_discovery(tmp_path):
    from armada.engine.mcp import registration_id
    cid = 'claude.ai Google Drive'
    util.write_json_atomic(tmp_path/'realm.json', {'toolkit': {'connectors': [{'id': cid}]}})
    runner._record_used_capabilities(tmp_path, ['mcp__'+registration_id(cid)+'__read_file_content'])
    assert len(json.loads((tmp_path/'realm.json').read_text())['toolkit']['connectors']) == 1


def test_codex_portable_registration_is_admitted_while_ambient_servers_are_disabled(tmp_path, monkeypatch):
    from armada.engine.mcp import registration_id
    cid = 'claude.ai Google Drive'
    sid = registration_id(cid)
    util.write_json_atomic(tmp_path/'realm.json', {'toolkit': {'connectors': [{'id': cid}]}})
    util.write_json_atomic(tmp_path/'agents/steve/agent.json', {'id': 'steve', 'toolkit': {'connectors': [{'id': cid}]}})
    engine = codex.CodexEngine()
    runner._tool_grants(tmp_path, 'steve', engine, True)
    monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0,
        stdout=json.dumps([{'name': sid}, {'name': 'ambient'}, {'name': registration_id('claude.ai Google/Drive')}])) )
    args = engine._mcp_args(True, [])
    assert f'mcp_servers.{sid}.enabled=false' not in args
    assert 'mcp_servers.ambient.enabled=false' in args
    assert f'mcp_servers.{registration_id("claude.ai Google/Drive")}.enabled=false' in args
    assert engine._turn_mcp_ids == (sid,)


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_disabled_registration_alias_revokes_logical_grant(provider):
    from armada.capabilities import CapabilityPolicy, provider_policy
    from armada.engine.mcp import registration_id
    cid = 'claude.ai Google Drive'
    policy = CapabilityPolicy(frozenset({cid}), ('mcp__'+registration_id(cid),))
    assert provider_policy(policy, provider).allowed_mcp_ids == frozenset()
