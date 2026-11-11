"""Fail-closed identity selection and explicit environment/folder boundaries."""
import os
from pathlib import Path
import pytest
from armada import worker, provider_keys, util


def test_key_cannot_be_saved_before_worker_setup():
    with pytest.raises(OSError, match='isolated Windows worker'):
        provider_keys.save('claude','sk-ant-synthetic-isolation-test')
    assert not provider_keys.configured('claude')


def test_broken_worker_never_reverts_to_owner(monkeypatch):
    util.write_json_atomic(worker._path(), {'ready':False})
    launched=[]
    monkeypatch.setattr(worker.subprocess,'Popen',lambda *a,**k:launched.append(a))
    with pytest.raises(OSError,match='isolated Windows worker'):
        worker.popen(['synthetic-engine'])
    assert not launched


def test_worker_environment_drops_owner_secrets_and_configuration(tmp_path,monkeypatch):
    profile=tmp_path/'profile'; profile.mkdir()
    value={'home':str(profile),'username':'synthetic-worker','path':['C:/Windows/System32'],
           'protected_roots':[], 'allowed_roots':[], 'sid':'synthetic'}
    for key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','OPENAI_API_KEY','AZURE_API_KEY',
                'CODEX_HOME','CLAUDE_CONFIG_DIR','ARMADA_DATA_DIR','ARMADA_SIGNING_CONFIG',
                'HTTP_PROXY','HTTPS_PROXY','GITHUB_TOKEN','TELEGRAM_BOT_TOKEN','NODE_OPTIONS','PYTHONPATH'):
        monkeypatch.setenv(key,'synthetic-owner-secret')
    env=worker.environment(value,dict(os.environ))
    assert 'synthetic-owner-secret' not in env.values()
    assert env['CODEX_HOME']==str(profile/'.codex')
    assert env['CLAUDE_CONFIG_DIR']==str(profile/'.claude')
    assert env['USERPROFILE']==str(profile)
    env=worker.environment(value,{**os.environ,'ANTHROPIC_API_KEY':'opaque-invocation-token',
                                  'ANTHROPIC_BASE_URL':'http://127.0.0.1:1234'})
    assert env['ANTHROPIC_API_KEY']=='opaque-invocation-token'
    assert env['ANTHROPIC_BASE_URL']=='http://127.0.0.1:1234'


def test_owner_controls_are_denied_even_below_a_shared_parent(tmp_path):
    secret=tmp_path/'owner'; secret.mkdir()
    value={'home':str(tmp_path/'worker'), 'allowed_roots':[str(tmp_path)], 'protected_roots':[str(secret)]}
    with pytest.raises(OSError,match='owner credential'):
        worker._access(secret/'provider-secrets.json',value)
    assert worker._access(tmp_path/'realm',value)==str(tmp_path/'realm')
    with pytest.raises(OSError,match='not shared'):
        worker._access(tmp_path.parent/'outside',value)


def test_station_keeper_never_reuses_existing_station_or_accepts_commands():
    script=Path(worker.__file__).with_name('worker_station.ps1').read_text()
    assert 'CreateWindowStation($cfg.station,1,' in script
    assert 'Start-Process' not in script and 'Invoke-Expression' not in script
    assert 'WinSta0' not in script and 'CreateNamedPipe' not in script


def test_lost_worker_config_does_not_restore_owner_launch(monkeypatch):
    monkeypatch.setattr(provider_keys,'configured',lambda provider:True)
    assert worker.enabled()
    with pytest.raises(OSError):worker.require()


def test_realm_file_cannot_remove_an_imported_owner_ceiling(tmp_path):
    from armada import run_policy, runner
    root=tmp_path/'realm'
    util.write_json_atomic(root/'realm.json',{'default_job_timeout':600})
    run_policy.import_legacy(root)
    util.write_json_atomic(root/'realm.json',{'default_job_timeout':None})
    assert runner._resolve_timeout(root,{})==600
    run_policy.save(root,{'default_job_timeout':''})
    assert runner._resolve_timeout(root,{}) is None


def test_upgrade_does_not_approve_agent_authored_new_controls(tmp_path):
    from armada import run_policy
    root=tmp_path/'realm'
    util.write_json_atomic(root/'realm.json',{})
    job={'id':'forged','prompt':'work','critical':True}
    util.write_json_atomic(root/'agents/a/jobs/forged.json',job)
    run_policy.import_legacy(root)
    with pytest.raises(ValueError,match='owner must approve'):
        run_policy.verify_job(root,'a',job)
    with pytest.raises(ValueError,match='owner must approve'):
        run_policy.verify_job(root,'a',{'id':'new','prompt':'work','timeout':10000})


def test_changing_an_agent_job_to_command_does_not_escape_its_seal(tmp_path,monkeypatch):
    from armada import run_policy,runner
    from armada.capabilities import CapabilityPolicyError
    from armada.engine import MockEngine
    root=tmp_path/'realm'
    util.write_json_atomic(root/'realm.json',{})
    util.write_json_atomic(root/'agents/a/agent.json',{'id':'a'})
    job={'id':'work','kind':'agent','prompt':'work','allow_tools':False,'timeout':600}
    run_policy.seal_job(root,'a',job)
    util.write_json_atomic(root/'agents/a/jobs/work.json',{**job,'kind':'command','timeout':100000,'run':['cmd','/c','echo forbidden']})
    with pytest.raises(CapabilityPolicyError,match='changed after approval'):
        runner.run_job(root,'a','work',engine=MockEngine())


def test_gateway_reconciliation_uses_provider_counters_and_cache_tiers():
    from armada.api_gateway import Budget, metered_cost
    data={'input_tokens':100,'output_tokens':20,'cache_read_input_tokens':1000,'cache_creation_input_tokens':400,
          'cache_creation':{'ephemeral_5m_input_tokens':300,'ephemeral_1h_input_tokens':100}}
    assert metered_cost('claude-opus-5-5',data)==pytest.approx(.0033)
    assert metered_cost('claude-haiku-5-5',{**data,'input_tokens':100001}) > .01
    assert metered_cost('claude-opus-5-5',{**data,'cache_creation':{}}) is None
    budget=Budget(1);bound=budget.authorise({'model':'claude-opus-5-5','messages':[],'max_tokens':1000},100)
    assert budget.cost() is None
    budget.finish('claude-opus-5-5',bound,data)
    assert budget.cost()==pytest.approx(.0033)


def test_gateway_refuses_unbounded_media_and_does_not_trust_count_underestimate():
    from armada.api_gateway import Budget
    body={'model':'claude-opus-5-5','max_tokens':10,'messages':[{'role':'user','content':'x'*100000}]}
    with pytest.raises(ValueError,match='remaining run reservation'):
        Budget(.1).authorise(body,1)
    body['messages'][0]['content']=[{'type':'image','source':{'type':'base64','media_type':'image/png','data':'synthetic'}}]
    with pytest.raises(ValueError,match='inline media'):
        Budget(5).authorise(body,1)


def test_runtime_temporary_paths_use_worker_profile_without_sharing_owner_parents(tmp_path,monkeypatch):
    profile=tmp_path/'worker'
    base=profile/'AppData/Local/Temp'
    base.mkdir(parents=True)
    monkeypatch.setattr(worker.tempfile,'gettempdir',lambda:str(tmp_path/'owner-temp'))
    monkeypatch.setattr(worker,'state',lambda:{'home':str(profile)})
    monkeypatch.setattr(worker,'enabled',lambda:True)
    monkeypatch.setattr(worker,'require',lambda:{'home':str(profile)})
    assert worker.temp_root()==str(base)
    assert worker._safe_temporary(base/'armada-probe'/'input.json')==base/'armada-probe'
    assert worker._safe_temporary(base/'unrelated') is None
    assert worker._safe_temporary(profile/'credentials') is None


def test_path_based_grants_cannot_change_trusted_or_unregistered_folders(tmp_path):
    with pytest.raises(OSError,match='outside a held worker runtime'):
        worker._acl(tmp_path,'synthetic-worker','M')


def test_realm_usage_edits_cannot_spend_credit_or_override_owner_reading(tmp_path):
    from armada import usage_snapshot,billing
    import time
    root=tmp_path/'realm';root.mkdir()
    usage_snapshot.remember(root,'claude',{'available':True,'session':{'pct':10}})
    util.write_json_atomic(root/'usage-last.json',{'engines':{'claude':{'available':True,'at':time.time(),'session':{'pct':100}}}})
    assert billing.exhausted(root)==('',None)
    assert usage_snapshot.trusted_read(root)['claude']['session']['pct']==10


def test_critical_capacity_is_reserved_before_other_realm_work_starts(tmp_path):
    from armada import run_policy
    first,second=tmp_path/'first',tmp_path/'second'
    for root in (first,second):
        util.write_json_atomic(root/'realm.json',{'default_engine':'claude'})
        util.write_json_atomic(root/'agents/a/agent.json',{'id':'a'})
    job={'id':'desk','kind':'agent','prompt':'work','critical':True,'engine':'claude'}
    util.write_json_atomic(second/'agents/a/jobs/desk.json',job)
    run_policy.seal_job(second,'a',job)
    hints=run_policy.admission(first,'a','main','claude')
    assert hints['reserve_slot'] and hints['reserve_provider'] and not hints['reserve_realm'] and not hints['critical']
    other=run_policy.admission(first,'a','main','codex')
    assert other['reserve_slot'] and not other['reserve_provider']
