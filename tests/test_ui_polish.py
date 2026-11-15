"""Owner-facing polish: saved policy, honest estimates and shared rendering."""
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from armada import api_fallback, jobs, reader, run_policy, util
from armada.engine.base import RunResult
from armada.webui import pages
from golden_support import build_fixture


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('ARMADA_DATA_DIR', str(tmp_path/'account'))
    root = Path(build_fixture(tmp_path/'realm'))
    for aid, coordinator in [('captain', True), ('reader', False)]:
        path = root/'agents'/aid/'agent.json'
        cfg = util.read_json_state(path, default=dict)
        util.write_json_atomic(path, {**cfg, 'id': aid, 'coordinator': coordinator})
    return root


def test_proposal_defaults_are_owner_owned_and_explicit_opt_out_survives(root):
    bad = root/'agents/damaged/agent.json'
    bad.parent.mkdir(); bad.write_text('{broken', encoding='utf-8')
    run_policy.remember_coordinators(root)
    assert run_policy.proposal_permission(root, 'captain')
    assert not run_policy.proposal_permission(root, 'reader')
    util.write_json_atomic(root/'agents/reader/agent.json', {'coordinator': True})
    run_policy.remember_coordinators(root)
    assert not run_policy.proposal_permission(root, 'reader')
    run_policy.save(root, {'may_propose_job_changes': False}, agent='captain')
    run_policy.remember_coordinators(root, ['captain', 'reader'])
    assert not run_policy.proposal_permission(root, 'captain')
    assert run_policy.proposal_permission(root, 'reader')


@pytest.mark.parametrize('allowed', [False, True])
def test_migrate_legacy_proposal_choice_before_realm_controls_replace_it(root, allowed):
    run_policy.save(root, {'coordinator_may_propose_changes': allowed})
    run_policy.remember_coordinators(root)
    run_policy.save(root, {'critical_usage_percent': 80})
    assert run_policy.proposal_permission(root, 'captain') is allowed
    assert not run_policy.proposal_permission(root, 'reader')


def test_regular_agent_permission_proposes_but_does_not_replace_without_review(root):
    original = {'id':'daily','name':'Daily','kind':'agent','prompt':'Original','allow_tools':False}
    path = root/'agents/captain/jobs/daily.json'
    util.write_json_atomic(path, original)
    pending = root/'agents/reader/jobs/_pending/daily.json'
    proposal = {**original, 'target_agent':'captain', 'prompt':'Proposed'}
    util.write_json_atomic(pending, proposal)
    with pytest.raises(ValueError):
        jobs.review(root, 'reader', jobs.validate(proposal)[2])
    run_policy.save(root, {'may_propose_job_changes':True}, agent='reader')
    reviewed = jobs.review(root, 'reader', jobs.validate(proposal)[2])
    assert util.read_json_state(path)['prompt'] == 'Original'
    assert jobs.approve(root, 'reader', 'daily', review_token=reviewed['token'])['ok']
    assert util.read_json_state(path)['prompt'] == 'Proposed'


def test_budget_is_estimate_only_and_missing_receipts_are_visible(root):
    api_fallback.save('claude', enabled=False, display_budget_usd=100)
    api_fallback.start('claude','one',root,'captain')
    api_fallback.finish('claude','one',RunResult(ok=True,raw={'total_cost_usd':12.34}))
    c = api_fallback.credit()
    assert c['estimated_remaining_usd'] == 87.66
    assert c['remaining_usd'] is None and c['cap_usd'] is None
    api_fallback.save('claude', enabled=False)
    assert api_fallback.settings('claude')['display_budget_usd'] == 100
    api_fallback.start('claude','two',root,'reader')
    api_fallback.finish('claude','two',RunResult(ok=True,raw={}))
    assert api_fallback.credit()['estimated_remaining_usd'] is None


@pytest.mark.parametrize('value', [-1, True, float('nan'), float('inf'), '100'])
def test_invalid_display_budget_does_not_overwrite_settings(root, value):
    api_fallback.save('claude', enabled=False, display_budget_usd=50)
    with pytest.raises(ValueError):
        api_fallback.save('claude', display_budget_usd=value)
    assert api_fallback.settings('claude')['display_budget_usd'] == 50


def test_estimate_excludes_old_cycle_and_clamps_at_zero(root):
    api_fallback.save('claude', enabled=False, display_budget_usd=5)
    util.write_json_atomic(api_fallback._usage_path('claude'), {'runs': {
        'old':{'started_at':1,'finished_at':2,'status':'finished','cost_usd':100},
        'now':{'started_at':time.time(),'finished_at':time.time(),'status':'finished','cost_usd':6}}})
    assert api_fallback.credit()['estimated_remaining_usd'] == 0
    assert api_fallback.credit()['spent_usd'] == 6


@pytest.mark.parametrize('section', [
    {'name':'Local','assets':'app','entry':'index.html'},
    {'name':'Mirror','snapshot':'snapshot.html'},
    {'name':'Website','url':'https://example.invalid'},
])
def test_custom_section_has_navigation_content_container(root, section):
    realm = reader.read(root); realm.sections = [section]
    html = pages.render_section(realm, 0)
    assert 'class="mc-appscroll"' in html
    assert 'navigation.js' in html and '<iframe' in html


def test_job_description_renders_markdown_safely():
    from armada.webui.realmpages import _job_description
    html = _job_description('**Important** [Details](https://example.invalid) <script>alert(1)</script>')
    assert '<strong>Important</strong>' in html
    assert 'href="https://example.invalid"' in html
    assert '<script>' not in html
    assert 'aria-expanded="false"' in html and 'show less' in html and '...more' in html


def test_running_job_is_deduplicated_and_disappears_after_finish(root, monkeypatch):
    from armada.webui import activity_monitor, agentbits
    from armada import execution_admission
    from armada.job_history import JOB_PREFIX
    monkeypatch.setattr(agentbits, '_running_jobs', lambda *a: {'daily'} if a[1]=='captain' else set())
    monkeypatch.setattr(execution_admission, 'snapshot', lambda: [dict(root=str(root), agent='captain', thread=JOB_PREFIX+'daily',state='running')])
    html = activity_monitor.content(reader.read(root), root)
    assert html.count('data-activity-key="job:captain:daily"') == 1
    monkeypatch.setattr(agentbits, '_running_jobs', lambda *a:set())
    monkeypatch.setattr(execution_admission, 'snapshot', lambda: [])
    assert 'data-activity-key="job:captain:daily"' not in activity_monitor.content(reader.read(root), root)


def test_settings_dirty_browser_contract():
    result = subprocess.run(['node','tests/settings_dirty_harness.js'],capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr


def test_realm_save_validates_and_persists_run_controls_together(root):
    from armada import serve
    handler=object.__new__(serve.Handler);handler.realm=root
    old=util.read_json_state(root/'realm.json')['name']
    result=handler._save_realm_settings({'name':'Changed','run_controls':{'agent_inactivity_minutes':-5}})
    assert not result['ok'] and util.read_json_state(root/'realm.json')['name']==old
    result=handler._save_realm_settings({'name':'Changed','run_controls':{'agent_inactivity_minutes':47}})
    assert result['ok']
    assert util.read_json_state(root/'realm.json')['name']=='Changed'
    assert run_policy.settings(root)['agent_inactivity_minutes']==47


def test_new_coordinator_defaults_to_cross_agent_proposals(root):
    from armada import serve
    handler=object.__new__(serve.Handler);handler.realm=root
    result=handler._new_agent({'display':'New leader','coordinator':True})
    assert result['ok'] and run_policy.proposal_permission(root,result['id'])
    result=handler._new_agent({'display':'New reader','coordinator':False})
    assert result['ok'] and not run_policy.proposal_permission(root,result['id'])
