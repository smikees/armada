"""Tool intent is explicit, owner-controlled and checked before any provider work."""
import json
from pathlib import Path

import pytest

from armada import execution, job_tools, jobs, notify, reader, realm_registry, runner
from armada.engine import MockEngine
from armada.webui.agentcommon import _job_proposals_block, _job_tools_warnings_block


@pytest.fixture
def realm(tmp_path):
    (tmp_path / 'realm.json').write_text('{"name":"Synthetic realm"}', encoding='utf-8')
    ad = tmp_path / 'agents' / 'writer'
    (ad / 'jobs' / '_pending').mkdir(parents=True)
    (ad / 'agent.json').write_text('{"id":"writer","allow_tools":true}', encoding='utf-8')
    return tmp_path


def proposal(realm, **extra):
    job = {'id': 'report', 'name': 'Synthetic report', 'kind': 'agent', 'prompt': 'Explain the idea', **extra}
    path = realm / 'agents/writer/jobs/_pending/report.json'
    path.write_text(json.dumps(job), encoding='utf-8')
    return path


def saved(realm, **extra):
    job = {'id': 'report', 'name': 'Synthetic report', 'kind': 'agent', 'prompt': 'Explain the idea', **extra}
    path = realm / 'agents/writer/jobs/report.json'
    path.write_text(json.dumps(job), encoding='utf-8')
    return path


def test_missing_tools_is_rejected_without_promoting(realm):
    src = proposal(realm)
    result = jobs.approve(realm, 'writer', 'report')
    assert not result['ok'] and job_tools.TOOLS_REQUIRED in result['error']
    assert src.exists() and not (src.parent.parent / src.name).exists()


@pytest.mark.parametrize('value', [None, 0, 1, 'true', 'false', [], {}])
def test_proposal_tools_must_be_a_json_boolean(value):
    ok, errors, _ = jobs.validate({'name': 'Example', 'prompt': 'Text', 'allow_tools': value})
    assert not ok and any('allow_tools' in error for error in errors)


@pytest.mark.parametrize('value', [True, False])
def test_explicit_tool_intent_is_preserved(value):
    ok, errors, norm = jobs.validate({'name': 'Example', 'prompt': 'Text', 'allow_tools': value})
    assert ok and not errors and norm['allow_tools'] is value


def test_command_proposal_is_unchanged():
    assert jobs.validate({'name': 'Command', 'kind': 'command', 'run': 'echo fixture'})[0]


@pytest.mark.parametrize('prompt', [r'Write {workspace}\x\y.md', 'Read C:/notes/source.txt',
    'Write /tmp/reports/result.csv', 'Save results.json', 'Use an MCP connector',
    'Send via Telegram', 'Send an inbox message'])
def test_tool_dependent_text_warns(prompt):
    assert job_tools.warning({'kind': 'agent', 'allow_tools': False, 'prompt': prompt})


def test_pending_proposal_discloses_warning_and_editable_choice(realm):
    proposal(realm, allow_tools=False, prompt=r'Write {workspace}\x\y.md')
    html = _job_proposals_block(reader.read_native(realm), realm)
    assert job_tools.WITHOUT_TOOLS in html
    assert 'appears to need tools' in html and 'mc-proptools' in html
    assert 'value="false" selected' in html and 'Runs WITH tools' in html


def test_missing_choice_can_be_fixed_explicitly_at_approval(realm):
    proposal(realm)
    html = _job_proposals_block(reader.read_native(realm), realm)
    assert 'Choose whether this job uses tools' in html
    assert jobs.approve(realm, 'writer', 'report', allow_tools=True)['ok']
    assert json.loads((realm / 'agents/writer/jobs/report.json').read_text())['allow_tools'] is True


def test_false_warning_requires_acknowledgment_and_never_changes_choice(realm):
    proposal(realm, allow_tools=False, result_contract={'required_outputs': ['report.md']})
    result = jobs.approve(realm, 'writer', 'report')
    assert not result['ok'] and result['needs_tools_confirmation']
    assert jobs.approve(realm, 'writer', 'report', tools_warning_ack=True)['ok']
    assert json.loads((realm / 'agents/writer/jobs/report.json').read_text())['allow_tools'] is False


def test_approval_api_preserves_false_and_rejects_nonboolean(realm):
    from armada.routes.agents import AgentRoutes
    handler = type('Handler', (AgentRoutes,), {'realm': realm})()
    proposal(realm)
    body = {'agent': 'writer', 'slug': 'report', 'action': 'approve', 'allow_tools': 'false'}
    assert not handler._job_proposal(body)['ok']
    body['allow_tools'] = False
    assert handler._job_proposal(body)['ok']
    assert json.loads((realm / 'agents/writer/jobs/report.json').read_text())['allow_tools'] is False


def test_lint_notifies_once_leaves_jobs_unchanged_and_is_visible(realm, monkeypatch):
    path = saved(realm)
    original = path.read_bytes()
    calls = []
    monkeypatch.setattr(notify, 'emit', lambda *a, **kw: calls.append((a, kw)))
    assert job_tools.lint(realm)[0]['job'] == 'report'
    assert job_tools.lint(realm)[0]['job'] == 'report'
    assert len(calls) == 1 and calls[0][0][1] == 'approval_needed'
    assert path.read_bytes() == original
    html = _job_tools_warnings_block(realm)
    assert 'Synthetic report' in html and '/job/writer/report' in html
    assert job_tools.TOOLS_REQUIRED in html


@pytest.mark.parametrize('extra', [{'enabled': False}, {'kind': 'command', 'run': 'echo ok'},
                                 {'allow_tools': True}, {'allow_tools': False}])
def test_lint_ignores_disabled_command_and_valid_text_jobs(realm, extra):
    path = saved(realm, **extra)
    before = path.read_bytes()
    assert job_tools.findings(realm) == []
    assert path.read_bytes() == before


def test_lint_covers_all_realms_and_contract_destinations(realm, tmp_path, monkeypatch):
    other = tmp_path / 'other'
    (other / 'agents/reviewer/jobs').mkdir(parents=True)
    (other / 'realm.json').write_text('{"name":"Other"}')
    (other / 'agents/reviewer/jobs/deliver.json').write_text(json.dumps({
        'kind': 'agent', 'allow_tools': False, 'result_contract': {'required_destinations': ['inbox']}}))
    saved(realm)
    monkeypatch.setattr(realm_registry, 'load', lambda: [{'path': str(other)}, {'path': str(realm)}])
    calls = []
    monkeypatch.setattr(notify, 'emit', lambda root, *a, **kw: calls.append(Path(root)))
    job_tools.scan_all(realm)
    assert set(calls) == {realm, other}


def test_monitor_checks_startup_and_daily_without_browser_or_scheduler(monkeypatch):
    calls = []
    monkeypatch.setattr(job_tools, 'scan_all', lambda primary: calls.append(primary))
    class Stop:
        def is_set(self): return False
        def wait(self, interval):
            assert interval == 86400
            return len(calls) == 2
    job_tools.monitor('fixture', Stop())
    assert calls == ['fixture', 'fixture']


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
@pytest.mark.parametrize('contract', [{'required_outputs': ['report.md']}, {'required_destinations': ['inbox']}])
@pytest.mark.parametrize('setting', [{}, {'allow_tools': False}, {'allow_tools': 'true'}])
def test_required_outputs_fail_before_any_engine_or_model_turn(realm, monkeypatch, provider, contract, setting):
    saved(realm, retries=3, result_contract=contract, **setting)
    calls = []
    monkeypatch.setattr(runner, '_notify', lambda *a, **kw: calls.append(a))
    monkeypatch.setattr(runner, '_select_engine', lambda *a, **kw: pytest.fail('selected an engine'))
    monkeypatch.setattr(execution, 'execute_request', lambda *a, **kw: pytest.fail('spent a model turn'))
    if setting.get('allow_tools') == 'true':
        # Structurally damaged configuration is now refused before a turn exists;
        # valid-but-contradictory intent still gets the durable startup failure below.
        from armada import util
        with pytest.raises(util.StateError, match='allow_tools must be true or false'):
            runner.run_job(realm, 'writer', 'report', engine=provider)
        assert not list((realm / 'agents/writer/runs/.running').glob('*.json'))
        assert not calls
        return
    report = runner.run_job(realm, 'writer', 'report', engine=provider)
    assert report['status'] == 'error'
    assert 'configured without tools but requires outputs' in report['summary']
    assert report['result']['startup_failure']['code'] == 'job_tools'
    assert any(row[1] == 'job_failed' and 'configured without tools' in row[3] for row in calls)


def test_saved_false_does_not_inherit_agent_or_caller_tools(realm, monkeypatch):
    saved(realm, allow_tools=False)
    engine = MockEngine()
    monkeypatch.setattr(runner, '_select_engine', lambda *a, **kw: engine)
    observed = []
    def execute(eng, req, **kw):
        observed.append(req.allow_tools)
        return engine.run(req.system, req.prompt)
    monkeypatch.setattr(execution, 'execute_request', execute)
    runner.run_job(realm, 'writer', 'report', engine=engine, allow_tools=True)
    assert observed == [False]


def test_approval_browser_keeps_boolean_choice_and_requires_warning_confirmation():
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is unavailable')
    script = Path(__file__).parents[1] / 'armada/webui/static/js/job_proposal.js'
    harness = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
const status={},warning={},approve={disabled:true},msg={style:{}};
const select={value:'',dataset:{needsTools:'true',validOther:'true'},closest:()=>box};
const box={dataset:{reviewToken:'reviewed-proposal-token'},querySelector:s=>({'.mc-proptools':select,'.mc-proptoolstatus':status,
  '.mc-proptoolwarning':warning,'.mc-propapprove':approve,'.mc-propmsg':msg})[s]};
const btn={closest:()=>box};let sent=[],reloads=0,confirmed=false;
global.location={reload:()=>reloads++};
global.fetch=async(url,args)=>{sent.push(JSON.parse(args.body));return {json:async()=>({ok:true})}};
global.mcConfirm=async()=>confirmed;
(async()=>{
 mcJobProposalTools(select);assert.equal(approve.disabled,true);
 select.value='false';mcJobProposalTools(select);
 assert.equal(approve.disabled,false);assert.equal(warning.hidden,false);
 assert.match(status.textContent,/cannot read or write files/);
 await mcJobProposal('writer','report','approve',btn);assert.equal(sent.length,0);
 confirmed=true;await mcJobProposal('writer','report','approve',btn);
 assert.equal(sent[0].allow_tools,false);assert.equal(sent[0].tools_warning_ack,true);
 assert.equal(sent[0].review_token,'reviewed-proposal-token');
 select.value='true';mcJobProposalTools(select);assert.equal(warning.hidden,true);
 confirmed=false;await mcJobProposal('writer','report','approve',btn);
 assert.equal(sent[1].allow_tools,true);assert.equal(sent[1].tools_warning_ack,undefined);
 assert.equal(reloads,2);
 select.dataset.validOther='false';mcJobProposalTools(select);assert.equal(approve.disabled,true);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run([node, '-e', harness, str(script)], check=True, capture_output=True, text=True)


