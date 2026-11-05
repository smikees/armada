"""Synthetic authorization boundaries; never use a personal realm or provider."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada import access_policy as P, capabilities, clock, notify, runner, util
from armada.engine import claude, codex, gemini
from armada.engine.base import RunResult
from armada.policy_tools import PolicyAudit, PolicyTools
from armada.tool_admission import ToolAdmission, claude_args


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / 'realm'
    agent = root / 'agents' / 'analyst'
    agent.mkdir(parents=True)
    util.write_json_atomic(root / 'realm.json', {'name': 'Synthetic policy realm',
        'toolkit': {'connectors': [{'id': 'ibkr', 'name': 'Synthetic brokerage',
            'tool_names': ['get_balance', 'get_orders', 'submit_order', 'create_order_instruction', 'create_alert']} ]},
        'tool_policy': {'ibkr': {'deny': ['*order*', '*alert*']}}, 'read_only': ['skills/**']})
    util.write_json_atomic(agent / 'agent.json', {'id': 'analyst', 'allow_tools': True,
        'toolkit': {'connectors': [{'id': 'ibkr'}]},
        'tool_policy': {'ibkr': {'allow': ['get_*', 'submit_order'], 'deny': ['submit_*']}},
        'write_scope': ['Finance/data/**', 'agents/analyst/**']})
    return root


def test_allow_deny_and_realm_exceptions(realm):
    rule = P.load(realm, 'analyst').rule('ibkr')
    assert rule.permits('get_balance')
    assert rule.permits('get_orders')  # Explicit agent pattern overrides the default.
    assert not rule.permits('submit_order')  # Agent deny always wins.
    assert not rule.permits('create_order_instruction')
    P.save(realm, 'analyst', {'tool_policy': {'ibkr': {'allow': ['get_*', 'create_order_instruction']}}})
    assert P.load(realm, 'analyst').rule('ibkr').permits('create_order_instruction')
    P.save(realm, 'analyst', {'tool_policy': {}})
    assert P.load(realm, 'analyst').rule('ibkr').permits('get_balance')
    assert not P.load(realm, 'analyst').rule('ibkr').permits('create_order_instruction')


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_denied_order_absent_allowed_read_present_in_engine_list(realm, monkeypatch, provider):
    audit = PolicyAudit(realm, 'analyst')
    admission = ToolAdmission(realm, 'analyst', provider, audit)
    engine = {'claude': claude.ClaudeEngine, 'codex': codex.CodexEngine, 'gemini': gemini.GeminiEngine}[provider]()
    engine.allowed_mcp_ids = frozenset({'ibkr'})
    engine.tool_admission = admission
    if provider == 'claude':
        args = claude_args(engine)
        config = json.loads(args[args.index('--agents') + 1])['armada-policy']
        offered = config['tools']
        assert 'mcp__ibkr__get_balance' in offered
        assert 'mcp__ibkr__submit_order' not in offered
        assert 'mcp__ibkr__*' not in offered
        assert 'mcp__ibkr__submit_order' in args[args.index('--disallowedTools') + 1:]
    elif provider == 'codex':
        monkeypatch.setattr('armada.codex_apps.rpc', lambda *a, **kw: {'config': {}})
        monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0,
            stdout=json.dumps([{'name': 'ibkr', 'enabled': True}]), stderr=''))
        args = engine._mcp_args(True, [])
        offered = json.loads(next(a.split('=', 1)[1] for a in args if a.startswith('mcp_servers.ibkr.enabled_tools=')))
        assert 'get_balance' in offered and 'submit_order' not in offered
    else:
        path = Path.home() / '.gemini/config/mcp_config.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'mcpServers': {'ibkr': {'command': 'synthetic-only'}}}))
        entry = engine._connectors([])[0]
        assert 'get_balance' in entry['enabledTools']
        assert 'submit_order' not in entry['enabledTools']
        assert 'submit_order' in entry['disabledTools']
    assert 'mcp__ibkr__get_balance' in audit.report()['offered_tools']


def test_filesystem_refuses_skills_and_reports_without_mutation(realm, monkeypatch):
    seen = []
    monkeypatch.setattr(notify, 'emit', lambda *a, **kw: seen.append(a))
    skills = realm / 'skills/desk/main.py'
    skills.parent.mkdir(parents=True)
    skills.write_text('original')
    audit = PolicyAudit(realm, 'analyst')
    with PolicyTools(realm, 'analyst', audit) as tools:
        for _ in range(2):
            with pytest.raises(PermissionError, match='read-only'):
                tools.call('write_file', {'path': 'skills/desk/main.py', 'content': 'changed'})
        with pytest.raises(PermissionError, match='outside'):
            tools.call('write_file', {'path': 'Finance/desk/orders.txt', 'content': 'changed'})
        tools.call('write_file', {'path': 'Finance/data/balance.txt', 'content': 'synthetic'})
    assert skills.read_text() == 'original'
    assert not (realm / 'Finance/desk').exists()
    assert (realm / 'Finance/data/balance.txt').read_text() == 'synthetic'
    assert len(audit.report()['denied_attempts']) == 3
    assert audit.report()['warnings']
    assert len(seen) == 1
    # Durable suppression across another run, and reset on the next local day.
    with clock.frozen('2030-01-01T12:00:00+01:00'):
        PolicyAudit(realm, 'analyst').refuse(tool='submit_order')
        PolicyAudit(realm, 'analyst').refuse(tool='submit_order')
    assert len(seen) == 2


@pytest.mark.parametrize('path', ['agents/analyst/agent.json', 'realm.json', '../escape.txt',
    'Finance/data/../../skills/desk.py', 'Finance/data/file.txt:secret', '.armada/policy-notifications.json'])
def test_control_files_traversal_and_ads_refused(realm, path):
    with pytest.raises((ValueError, PermissionError)):
        P.writable_path(realm, P.load(realm, 'analyst'), path)


@pytest.mark.parametrize('relative', [
    'agents/analyst/jobs/unapproved.json',
    'agents/analyst/jobs/_proposals.jsonl',
    'agents/analyst/runs/analyst.jsonl',
    'agents/analyst/runs/annotations/example.json',
    'agents/analyst/threads/main/messages.jsonl',
    'agents/analyst/threads/main/summary.md',
    'agents/analyst/inbox/message.json',
    'agents/analyst/goals/example.md',
    'agents/analyst/memory-audits/example.json',
    'agents/analyst/skills.json',
    'agents/analyst/mandate.md',
    'agents/analyst/soul.md',
    'agents/analyst/tenets.md',
    'theme.json', 'dashboard.json', 'system_jobs.json',
    'notifications.jsonl', 'notifications.state.json',
    'memory/core-context.md', 'goals/example.md',
    'capture-index/example.json', 'addons/example/addon.json',
    'agents/other/memory/private.md', 'agents/other/jobs/example.json',
])
def test_broad_scope_cannot_rewrite_control_records(realm, monkeypatch, relative):
    P.save(realm, 'analyst', {'write_scope': ['**']})
    path = realm / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('original evidence', encoding='utf-8')
    notifications = []
    monkeypatch.setattr(notify, 'emit', lambda *a, **kw: notifications.append(a))
    audit = PolicyAudit(realm, 'analyst')
    with PolicyTools(realm, 'analyst', audit) as tools:
        with pytest.raises(PermissionError, match='control'):
            tools.call('write_file', {'path': relative, 'content': 'forged'})
    assert path.read_text(encoding='utf-8') == 'original evidence'
    assert audit.report()['denied_attempts'][0]['path'] == relative
    assert audit.report()['warnings'] and len(notifications) == 1


def test_scoped_proposal_stays_pending_until_owner_approves(realm):
    from armada import jobs, scheduler
    proposal = {'id': 'daily-check', 'name': 'Daily check', 'kind': 'agent',
                'prompt': 'Synthetic only', 'allow_tools': False, 'schedule': 'daily 09:00',
                'approved_at': 'forged', 'enabled': True, 'proposed_by': 'owner'}
    audit = PolicyAudit(realm, 'analyst')
    with PolicyTools(realm, 'analyst', audit) as tools:
        tools.call('write_file', {'path': 'agents/analyst/jobs/_pending/daily-check.json',
                                 'content': json.dumps(proposal)})
        tools.call('write_file', {'path': 'agents/analyst/memory/note.md', 'content': 'My own note'})
        tools.call('write_file', {'path': 'Finance/data/jobs/report.txt', 'content': 'Business data'})
    pending = util.read_json_state(realm / 'agents/analyst/jobs/_pending/daily-check.json')
    assert 'approved_at' not in pending
    assert pending['proposed_by'] == 'analyst' and pending['enabled'] is False
    assert list(scheduler.iter_jobs(realm)) == []
    assert not audit.report()['warnings']
    assert jobs.approve(realm, 'analyst', 'daily-check')['ok']
    assert list(scheduler.iter_jobs(realm))[0][1] == 'daily-check'


@pytest.mark.parametrize('relative,content', [
    ('agents/analyst/jobs/_pending/bad.json', '{'),
    ('agents/analyst/jobs/_pending/bad.json', '{}'),
    ('agents/analyst/jobs/_pending/bad.txt', 'not a proposal'),
    ('agents/analyst/jobs/_pending/nested/bad.json', '{}'),
    ('agents/other/jobs/_pending/bad.json', '{}'),
])
def test_pending_exception_cannot_bypass_validation(realm, relative, content):
    P.save(realm, 'analyst', {'write_scope': ['**']})
    audit = PolicyAudit(realm, 'analyst')
    with PolicyTools(realm, 'analyst', audit) as tools:
        with pytest.raises((PermissionError, ValueError)):
            tools.call('write_file', {'path': relative, 'content': content})
    assert not (realm / relative).exists()
    assert audit.report()['warnings']


def test_pending_and_own_memory_exceptions_respect_owner_scope(realm):
    P.save(realm, 'analyst', {'write_scope': ['Finance/data/**']})
    with PolicyTools(realm, 'analyst', PolicyAudit(realm, 'analyst')) as tools:
        for relative in ('agents/analyst/jobs/_pending/daily-check.json', 'agents/analyst/memory/note.md'):
            with pytest.raises(PermissionError, match='outside'):
                tools.call('write_file', {'path': relative, 'content': '{}'})


def test_agent_record_exceptions_do_not_override_read_only(realm):
    P.save(realm, None, {'read_only': ['agents/analyst/memory/**', 'agents/analyst/jobs/**']})
    with PolicyTools(realm, 'analyst', PolicyAudit(realm, 'analyst')) as tools:
        for relative in ('agents/analyst/jobs/_pending/daily-check.json', 'agents/analyst/memory/note.md'):
            with pytest.raises(PermissionError, match='read-only'):
                tools.call('write_file', {'path': relative, 'content': '{}'})


def test_scoped_control_guard_cannot_be_bypassed_by_a_nested_realm(realm):
    nested = realm / 'Finance/data/nested'
    util.write_json_atomic(nested / 'realm.json', {'name': 'Other realm'})
    with pytest.raises(PermissionError, match='control'):
        P.writable_path(realm, P.load(realm, 'analyst'), 'Finance/data/nested/report.txt')


def test_path_globs_and_builder(realm):
    assert P.path_matches('Finance/data/a/b.txt', 'finance/data/**')
    assert not P.path_matches('Finance/data2/a.txt', 'Finance/data/**')
    assert not P.path_matches('Finance/data/a/b.txt', 'Finance/data/*')
    util.write_json_atomic(realm / 'agents/builder/agent.json', {'id': 'builder'})
    builder = P.load(realm, 'builder')
    assert not builder.scoped
    assert P.writable_path(realm, builder, 'skills/desk/code.py') == realm / 'skills/desk/code.py'
    assert P.writable_path(realm, builder, 'agents/analyst/jobs/work.json') == realm / 'agents/analyst/jobs/work.json'


@pytest.mark.parametrize('value', [None, [], 'all', {'ibkr': []}, {'ibkr': {'allow': '*'}},
    {'ibkr': {'allow': ['get_[']}}, {'ibkr': {'alow': ['*']}}, {'unknown': {'allow': ['*']}}])
def test_malformed_tool_policy_stops_run_before_engine_selection(realm, monkeypatch, value):
    path = realm / 'agents/analyst/agent.json'
    data = util.read_json_state(path)
    data['tool_policy'] = value
    util.write_json_atomic(path, data)
    monkeypatch.setattr(runner, 'get_engine', lambda *a: pytest.fail('policy reached engine selection'))
    result = runner.chat(realm, 'analyst', 'main', 'Synthetic request', allow_tools=True)
    assert not result['ok']
    assert 'Capability policy' in result['error']
    assert 'tool_policy' in result['error']


def test_empty_allowlist_and_new_tools_fail_closed(realm):
    P.save(realm, 'analyst', {'tool_policy': {'ibkr': {'allow': []}}})
    admission = ToolAdmission(realm, 'analyst', 'codex', PolicyAudit(realm, 'analyst'))
    assert admission.allowed['ibkr'] == []
    assert admission.offer('ibkr', ['get_balance', 'new_read_tool']) == []


def test_scoped_codex_shell_and_native_writes_disabled(realm, monkeypatch):
    engine = codex.CodexEngine()
    engine.writable_roots = (str(realm),)
    engine.network_access = True
    monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0, stdout='[]', stderr=''))
    with PolicyTools(realm, 'analyst', PolicyAudit(realm, 'analyst')) as files:
        engine = files.configure(engine)
        args = engine._args(None, True, None, [])
        assert args[args.index('--sandbox') + 1] == 'read-only'
        assert 'features.shell_tool=false' in args
        assert 'features.unified_exec=false' in args
        assert 'features.code_mode=false' in args
        assert 'features.view_image=false' not in args
        assert 'web_search="disabled"' not in args
        assert engine.writable_roots == (str(realm),)
        assert engine.network_access


def test_owner_save_is_atomic_and_logged_and_rejects_invalid_update(realm):
    path = realm / 'agents/analyst/agent.json'
    original = path.read_bytes()
    with pytest.raises(capabilities.CapabilityPolicyError):
        P.save(realm, 'analyst', {'write_scope': ['../**']})
    assert path.read_bytes() == original
    P.save(realm, 'analyst', {'write_scope': []})
    saved = util.read_json_state(path)
    assert saved['write_scope'] == []
    assert saved['_policy_changes'][-1]['actor'] == 'owner'
    assert saved['_policy_changes'][-1]['before']['write_scope']


def test_run_refusal_surfaces_as_operational_warning(realm, monkeypatch):
    class Fake:
        name = 'codex'
        capabilities = codex.CodexEngine.capabilities
        def run(self, **kwargs):
            with pytest.raises(PermissionError):
                self.policy_tools.call('write_file', {'path': 'skills/desk.py', 'content': 'changed'})
            return RunResult(ok=True, output='Refused the write.')
    monkeypatch.setattr(notify, 'emit', lambda *a, **kw: None)
    result = runner.chat(realm, 'analyst', 'main', 'Synthetic request', engine=Fake(), allow_tools=True)
    assert result['ok'], result
    assert result['status'] == 'warn'
    assert result['operational_warnings']
    reports = (realm / 'agents/analyst/runs/analyst.jsonl').read_text().splitlines()
    assert json.loads(reports[-1])['access_audit']['denied_attempts'][0]['path'] == 'skills/desk.py'


@pytest.mark.parametrize('provider,version', [('codex', 'codex-cli 0.150.0'), ('gemini', '1.4.0')])
def test_old_cli_cannot_silently_ignore_restrictions(realm, provider, version):
    from armada.tool_admission import verify_engine_version
    engine = SimpleNamespace(name=provider,
        tool_admission=ToolAdmission(realm, 'analyst', provider, PolicyAudit(realm, 'analyst')),
        _probe=lambda args: SimpleNamespace(returncode=0, stdout=version))
    with pytest.raises(capabilities.CapabilityPolicyError, match='Update the engine'):
        verify_engine_version(engine)


def test_internal_file_tools_do_not_pollute_catalogue(realm):
    path = realm / 'realm.json'
    before = path.read_bytes()
    runner._record_used_capabilities(realm, ['mcp__armada_files_test__write_file'])
    assert path.read_bytes() == before


def test_inventory_edits_cannot_retain_removed_names(realm):
    from armada.tool_admission import save_names, remember, known_names
    remember(realm, 'ibkr', ['get_balance', 'submit_order'], 'codex')
    save_names(realm, 'ibkr', ['get_balance'])
    cap = capabilities.find(realm, 'ibkr')[1]
    assert known_names(realm, cap, 'gemini') == ['get_balance']


def test_policy_is_rechecked_after_context_assembly(realm, monkeypatch):
    class Fake:
        name = 'codex'
        capabilities = codex.CodexEngine.capabilities
        def run(self, **kwargs):
            assert self.tool_admission.allowed['ibkr'] == []
            return RunResult(ok=True, output='No tools allowed.')
    original = runner.memory.assemble_core
    def assemble(*args):
        text = original(*args)
        P.save(realm, 'analyst', {'tool_policy': {'ibkr': {'allow': []}}})
        return text
    monkeypatch.setattr(runner.memory, 'assemble_core', assemble)
    assert runner.chat(realm, 'analyst', 'main', 'Synthetic', engine=Fake(), allow_tools=True)['ok']


@pytest.mark.parametrize('provider', ['codex', 'gemini'])
def test_provider_restrictions_are_never_widened(realm, monkeypatch, provider):
    engine = codex.CodexEngine() if provider == 'codex' else gemini.GeminiEngine()
    engine.allowed_mcp_ids = frozenset({'ibkr'})
    engine.tool_admission = ToolAdmission(realm, 'analyst', provider, PolicyAudit(realm, 'analyst'))
    if provider == 'codex':
        monkeypatch.setattr(engine, '_probe', lambda *a, **kw: SimpleNamespace(returncode=0,
            stdout=json.dumps([{'name': 'ibkr', 'enabled': True}]), stderr=''))
        monkeypatch.setattr('armada.codex_apps.rpc', lambda *a, **kw: {'config': {'mcp_servers': {
            'ibkr': {'enabled_tools': ['get_balance'], 'disabled_tools': ['get_orders']}}}})
        args = engine._mcp_args(True, [])
        names = json.loads(next(a.split('=', 1)[1] for a in args if a.startswith('mcp_servers.ibkr.enabled_tools=')))
    else:
        path = Path.home() / '.gemini/config/mcp_config.json'
        path.parent.mkdir(parents=True)
        util.write_json_atomic(path, {'mcpServers': {'ibkr': {'command': 'synthetic-only',
            'enabledTools': ['get_balance'], 'disabledTools': ['get_orders']}}})
        names = engine._connectors([])[0]['enabledTools']
    assert names == ['get_balance']


def test_denied_attempts_are_audited_without_requiring_a_provider_call_id(realm, monkeypatch):
    monkeypatch.setattr(notify, 'emit', lambda *a, **kw: None)
    audit = PolicyAudit(realm, 'analyst')
    admission = ToolAdmission(realm, 'analyst', 'codex', audit)
    admission.observe({'kind': 'tool', 'name': 'mcp__ibkr__submit_order'})
    admission.observe({'kind': 'tool', 'name': 'mcp__ibkr__submit_order'})
    admission.observe({'kind': 'tool', 'name': 'mcp__ungranted__get_balance'})
    assert len(audit.report()['denied_attempts']) == 3


def test_claude_inventory_waits_for_connector_startup(realm, monkeypatch):
    from armada import tool_inventory
    calls = []
    def rpc(*args, start, on_message, **kwargs):
        start(calls.append)
        assert not on_message({'type': 'control_response', 'response': {'request_id': '1'}}, calls.append)
        assert not on_message({'type': 'control_response', 'response': {'request_id': '2', 'response': {
            'mcpServers': [{'name': 'ibkr', 'status': 'pending'}]}}}, calls.append)
        assert on_message({'type': 'control_response', 'response': {'request_id': '3', 'response': {
            'mcpServers': [{'name': 'ibkr', 'status': 'connected', 'tools': [{'name': 'get_balance'}]}]}}}, calls.append)
        return SimpleNamespace(error='')
    monkeypatch.setattr('armada.engine.process.supervise_rpc', rpc)
    monkeypatch.setattr(tool_inventory.time, 'sleep', lambda *a: None)
    engine = SimpleNamespace(_launcher=lambda: ['synthetic'], _mcp_args=lambda *a: [], _env=lambda: {})
    assert tool_inventory.claude_inventory(engine, realm) == {'ibkr': ['get_balance']}


def test_scoped_dry_run_cannot_bypass_shell_policy(realm, monkeypatch):
    from armada import dry_runs, inspection
    from tests.test_dry_runs import finished
    monkeypatch.setattr(notify, 'emit', lambda *a, **kw: None)
    monkeypatch.setattr(inspection, 'command_approved', lambda *a: True)
    monkeypatch.setattr(dry_runs, '_command', lambda *a: pytest.fail('Scoped dry run launched a command'))
    util.write_json_atomic(realm / 'agents/analyst/jobs/synthetic.json', {'id': 'synthetic',
        'kind': 'command', 'run': ['synthetic'], 'dry_run_command': ['synthetic']})
    run = dry_runs.start(realm, 'analyst', 'synthetic')
    info = finished(realm, run)
    assert info['status'] == 'failed' and 'Shell is disabled' in info['error']
    assert info['access_audit']['denied_attempts'][0]['tool'] == 'shell'
    assert info['operational_warnings']


def test_scope_cannot_grant_a_withheld_filesystem_capability(realm, monkeypatch):
    monkeypatch.setattr(notify, 'emit', lambda *a, **kw: None)
    util.mutate_json(realm / 'realm.json', lambda data: data['toolkit'].update(extensions=[{
        'id': 'files', 'extension_id': 'ant.dir.ant.anthropic.filesystem'}]))
    audit = PolicyAudit(realm, 'analyst')
    with PolicyTools(realm, 'analyst', audit) as tools:
        assert tools.tools() == []
        with pytest.raises(PermissionError):
            tools.call('write_file', {'path': 'Finance/data/result.txt', 'content': 'not allowed'})
    assert not (realm / 'Finance/data/result.txt').exists()
    assert audit.report()['denied_attempts']
