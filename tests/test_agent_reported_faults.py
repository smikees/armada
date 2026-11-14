"""Synthetic regressions for schedule loss, late results and false connector faults."""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from armada import capabilities, reader, run_policy, util
from armada.engine import claude
from armada.engine.mcp import registration_id
from armada.engine.mcp_runtime import job_errors
from armada.engine.process import ProcessResult
from armada.routes.jobs import JobRoutes


@pytest.fixture
def realm(tmp_path, monkeypatch):
    monkeypatch.setenv('ARMADA_DATA_DIR', str(tmp_path/'account'))
    root = tmp_path/'realm'
    util.write_json_atomic(root/'realm.json', {'name': 'Synthetic realm'})
    util.write_json_atomic(root/'agents/a/agent.json', {'id':'a', 'display':'Ada'})
    return root


@pytest.mark.parametrize('cadence', [
    {'schedule':'mon-fri 17:45'}, {'schedule':'daily 09:00'},
    {'schedule':'45 17 * * 1-5'}, {'cron':'45 17 * * 1-5'}, {'schedule':'manual'}])
def test_unrelated_save_preserves_exact_schedule_and_approval(realm, cadence):
    path = realm/'agents/a/jobs/brief.json'
    job = {'id':'brief', 'kind':'agent', 'prompt':'Write a brief', **cadence}
    util.write_json_atomic(path, job)
    run_policy.seal_job(realm, 'a', job)
    response = JobRoutes._save_job(SimpleNamespace(realm=realm),
                                  {'agent':'a', 'job':'brief', 'critical':True})
    assert response['ok'] and not response['schedule_changed']
    saved = util.read_json_state(path)
    assert {k:saved[k] for k in ('schedule','cron') if k in saved} == cadence
    assert saved['critical'] and run_policy.verify_job(realm, 'a', saved)


@pytest.mark.parametrize('cron', ['', '0 8 * * 1-5'])
def test_explicit_schedule_edit_discloses_change(realm, cron):
    path = realm/'agents/a/jobs/brief.json'
    util.write_json_atomic(path, {'id':'brief', 'kind':'agent', 'prompt':'Brief', 'schedule':'mon-fri 17:45'})
    response = JobRoutes._save_job(SimpleNamespace(realm=realm), {'agent':'a','job':'brief','cron':cron})
    assert response['ok'] and response['schedule_changed']
    assert response['schedule_before'] == 'mon-fri 17:45'
    assert response['schedule_after'] == (cron or 'manual')
    assert util.read_json_state(path).get('cron') == (cron or None)


def test_editor_preserves_legacy_schedule_until_cadence_control_changes(realm):
    from armada.webui.pages import render_job
    util.write_json_atomic(realm/'agents/a/jobs/brief.json', {
        'id':'brief', 'name':'Brief', 'prompt':'Brief', 'schedule':'mon-fri 17:45'})
    html = render_job(reader.read(realm), realm, 'a', 'brief')
    assert 'data-cadence="mon-fri 17:45"' in html
    subprocess.run(['node', str(Path(__file__).with_name('job_schedule_harness.js'))], check=True,
                   capture_output=True, text=True)


@pytest.mark.parametrize('late', [
    {'type':'system','subtype':'task_notification'},
    {'type':'assistant','message':{'content':[{'type':'text','text':'late text'}]}},
    {'type':'result','subtype':'success','result':'duplicate','total_cost_usd':999},
    {'type':'error','message':'late event'},
])
@pytest.mark.parametrize('host_error', ['', 'CLI exited with code 1: '])
def test_late_events_preserve_terminal_output_usage_and_host_failures(monkeypatch, late, host_error):
    engine = claude.ClaudeEngine()
    monkeypatch.setattr(engine, '_launcher', lambda: ['synthetic-claude'])
    monkeypatch.setattr(engine, '_direct', lambda: True)
    monkeypatch.setattr(engine, '_env', lambda: {})
    terminal = {'type':'result','subtype':'success','result':'Complete report',
                'usage':{'input_tokens':17,'output_tokens':8}, 'total_cost_usd':.42}
    def supervise(*a, on_line, **kw):
        for event in (terminal, late):
            on_line(json.dumps(event))
        return ProcessResult(returncode=1 if host_error else 0, error=host_error)
    monkeypatch.setattr(claude, 'supervise', supervise)
    events = []
    result = engine.run_stream('', '', on_event=events.append)
    assert result.ok == (not host_error) and result.error == host_error
    assert result.output == 'Complete report' and result.usage.output == 8
    assert result.raw['total_cost_usd'] == .42 and result.raw['protocol_warnings']
    assert not any(e.get('text') == 'late text' for e in events)


@pytest.mark.parametrize('native', [True, False])
@pytest.mark.parametrize('connected', [True, False])
def test_claude_alternative_registration_is_not_a_missing_connector(monkeypatch, native, connected):
    name = 'claude.ai Documents'
    direct = registration_id(name)
    engine = claude.ClaudeEngine()
    engine.allowed_mcp_ids = capabilities.provider_policy(
        capabilities.CapabilityPolicy(frozenset({name}), (), frozenset()), 'claude').allowed_mcp_ids
    monkeypatch.setattr(engine, '_launcher', lambda: ['synthetic-claude'])
    monkeypatch.setattr(engine, '_direct', lambda: True)
    state = 'Connected' if connected else 'Failed to connect — HTTP 503'
    row = f'{name if native else direct}: https://docs.example/mcp - {state}'
    monkeypatch.setattr(claude.worker, 'run', lambda args, **kw: SimpleNamespace(
        returncode=0, stderr='', stdout='2.1.319' if '--version' in args else row))
    args = engine._mcp_args([])
    unavailable = getattr(engine, 'connector_unavailable', [])
    assert not any(r['state'] == 'missing' for r in unavailable)
    assert bool(unavailable) == (not connected)
    denied = json.loads(args[args.index('--settings')+1])['deniedMcpServers']
    assert bool(denied) == (not connected)
    from armada import connector_runtime
    from armada.engine.mcp import claude_rows
    monkeypatch.setattr(connector_runtime, '_claude_rows', lambda: claude_rows(row))
    assert connector_runtime.claude_connection({'id':name}, connector_runtime.claude_inventory()) == ('ready' if connected else 'failed')


@pytest.mark.parametrize('required,tools,expect_error', [([],[],False),
    (['filesystem'],[],True), ([],['mcp__filesystem__read_file'],True),
    ([],['mcp__other__read_file'],False)])
def test_unused_optional_connector_does_not_contaminate_audit(realm, required, tools, expect_error):
    rows = [{'server':'filesystem','state':'failed','tool_names':[], 'error':'Connection closed'}]
    assert bool(job_errors(rows, required, tools, root=realm, provider='claude')) == expect_error
    assert rows[0]['state'] == 'failed'  # keep diagnostic evidence


def test_logical_required_connector_resolves_to_provider_registration(realm):
    util.write_json_atomic(realm/'realm.json', {'toolkit':{'connectors':[
        {'id':'documents', 'name':'Documents', 'provider_bindings':{
            'claude':{'server_name':'claude.ai Docs','endpoint':'https://docs.example/mcp'}}}]}})
    rows = [{'server':'claude_ai_Docs','state':'failed','error':'503'}]
    assert job_errors(rows, ['documents'], [], root=realm, provider='claude')


def test_required_native_grant_covers_its_direct_registration_alias(realm):
    name = 'claude.ai Documents'
    rows = [{'server':registration_id(name),'state':'failed','error':'503'}]
    assert job_errors(rows, [name], [], root=realm, provider='claude')


def test_no_runtime_evidence_does_not_reopen_a_broken_catalogue(realm):
    util.write_json_atomic(realm/'realm.json', {'toolkit':{'connectors':'invalid'}})
    assert job_errors([], ['documents'], [], root=realm, provider='unknown') == []


def test_actual_claude_tools_override_preflight_failure(monkeypatch):
    from armada.engine.contracts import RunRequest
    engine = claude.ClaudeEngine()
    engine.connector_unavailable = [{'server':'claude_ai_Docs', 'state':'failed',
                                    'tool_names':[], 'error':'Earlier probe failed'}]
    monkeypatch.setattr(engine, '_launcher', lambda: ['synthetic-claude'])
    monkeypatch.setattr(engine, '_direct', lambda: True)
    monkeypatch.setattr(engine, '_env', lambda: {})
    def supervise(*a, on_line, **kw):
        for event in [
            {'type':'system','subtype':'init','mcp_servers':[{'name':'claude.ai Docs','status':'connected'}],
             'tools':['mcp__claude_ai_Docs__search']},
            {'type':'result','subtype':'success','result':'Done','usage':{}}]:
            on_line(json.dumps(event))
        return ProcessResult(returncode=0)
    monkeypatch.setattr(claude, 'supervise', supervise)
    result = engine.execute(RunRequest('', ''))
    assert result.ok and result.raw['connector_runtime'] == [
        {'server':'claude_ai_Docs','state':'ready','tool_names':['mcp__claude_ai_Docs__search'],'error':''}]


def test_connected_without_exposed_tools_is_not_claimed_callable():
    from armada.engine.mcp_runtime import claude_startup
    assert not claude_startup({'mcp_servers':[{'name':'docs','status':'connected'}], 'tools':['Read']})
