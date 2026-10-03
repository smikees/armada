import json
from pathlib import Path
import pytest
from armada import job_retries as jr, util, realmops, job_results


def report(execution='failed', delivery='failed'):
    return {'run_id': 'r', 'status': 'error', 'summary': 'connection reset', 'result': {
        'execution': execution, 'delivery': [{'status': delivery}], 'evidence': {}}}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    job = {'id': 'j', 'retries': 3, 'prompt': 'Do work'}
    path = tmp_path/'agents/a/jobs/j.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(job))
    monkeypatch.setattr(realmops, 'archived', lambda root: False)
    monkeypatch.setattr(jr, 'BACKOFF', (0, 0, 0))
    return tmp_path, job


@pytest.mark.parametrize('n', range(4))
def test_exact_retry_budget_and_persisted_attempts(setup, n):
    root, job = setup; job['retries'] = n
    util.write_json_atomic(root/'agents/a/jobs/j.json', job)
    calls = []
    result = jr.execute(root, 'a', 'j', job, lambda j: calls.append(j) or report())
    assert len(calls) == n+1
    state = util.read_json_state(jr.state_path(root, 'a', 'j'))
    assert state['state'] == 'finished' and len(state['attempts']) == n+1
    if n: assert calls[1]['prompt']==job['prompt']


@pytest.mark.parametrize('execution,delivery', [('completed','failed'),('completed','sent'),
    ('stopped','failed'),('failed','sent'),('timed_out','unknown')])
def test_does_not_repeat_completed_cancelled_or_uncertain_delivery(setup, execution, delivery):
    root, job = setup; calls=[]
    jr.execute(root,'a','j',job,lambda j:calls.append(j) or report(execution,delivery))
    assert len(calls)==1


def test_recovered_run_stops_retrying(setup):
    root, job=setup; calls=[]
    def run(j):
        calls.append(j)
        return report('completed','sent') if len(calls)==2 else report()
    assert jr.execute(root,'a','j',job,run)['result']['execution']=='completed'
    assert len(calls)==2


def test_restart_resumes_backoff_without_repeating_finished_attempt(setup):
    root, job=setup
    path=jr.state_path(root,'a','j')
    util.write_json_atomic(path,{'schema_version':1,'series_id':'old','max_retries':3,
        'state':'waiting','next_at':0,'started_at':0,'attempts':[{'run_id':'old'}], 'last_report':report()})
    calls=[]
    jr.execute(root,'a','j',job,lambda j:calls.append(j) or report('completed','sent'))
    state=util.read_json_state(path)
    assert len(calls)==1 and state['series_id']=='old' and len(state['attempts'])==2


def test_disabled_during_wait_cancels_retry(setup):
    root, job=setup; calls=[]
    def run(j):
        calls.append(j); util.write_json_atomic(root/'agents/a/jobs/j.json',{**job,'enabled':False})
        return report()
    jr.execute(root,'a','j',job,run)
    assert len(calls)==1
    assert util.read_json_state(jr.state_path(root,'a','j'))['state']=='cancelled'


def test_exception_leaves_uncertain_journal(setup):
    root,job=setup
    with pytest.raises(RuntimeError):
        jr.execute(root,'a','j',job,lambda j:(_ for _ in ()).throw(RuntimeError('unknown outcome')))
    assert util.read_json_state(jr.state_path(root,'a','j'))['state']=='uncertain'


@pytest.mark.parametrize('value',[-1,4,True,'3',None,1.5])
def test_rejects_invalid_retry_settings(value):
    with pytest.raises(ValueError):jr.validate(value)


def test_legacy_policy_and_operational_reason():
    assert jr.count({'on_failure':'Retry ×3, then alert me'})==3
    assert jr.count({})==0
    assert jr.count({'on_failure':'Something custom'})==0
    r=report()['result'];r['evidence']['operational_errors']=['WinError 10054']
    r['app_errors']=['Audit claim contradicts evidence']
    assert job_results.reason(r)=='WinError 10054'


def test_admission_and_unknown_results_do_not_retry():
    r=report();r['engine']='unknown'
    assert not jr.retryable(r)
    r=report();r['result']['detail_level']='unstructured'
    assert not jr.retryable(r)


@pytest.mark.parametrize('change', [
    {'schema_version':2}, {'max_retries':4}, {'next_at':'tomorrow'},
    {'attempts':[]}, {'last_report':{'result':{'execution':'completed'}}},
])
def test_damaged_or_unsafe_journal_never_replays(setup, change):
    root,job=setup
    util.write_json_atomic(jr.state_path(root,'a','j'),{
        'schema_version':1,'max_retries':3,'state':'waiting','started_at':0,
        'next_at':1,'attempts':[{'run_id':'old'}],'last_report':report(),**change})
    with pytest.raises(util.StateError):
        jr.pending(root,'a','j')
    calls=[]
    with pytest.raises(util.StateError):
        jr.execute(root,'a','j',job,lambda j:calls.append(j))
    assert not calls


def test_lowering_retry_count_cancels_wait_immediately(setup, monkeypatch):
    root,job=setup
    monkeypatch.setattr(jr,'BACKOFF',(30,60,120))
    calls=[]
    def run(j):
        calls.append(j)
        util.write_json_atomic(root/'agents/a/jobs/j.json',{**job,'retries':0})
        return report()
    def unexpected_sleep(seconds):
        pytest.fail('A cancelled retry must not wait out the backoff')
    jr.execute(root,'a','j',job,run,sleep=unexpected_sleep)
    assert len(calls)==1


def test_job_editor_saves_numeric_choice_and_rejects_bad_values(setup):
    from armada.routes.jobs import JobRoutes
    root,job=setup
    handler=JobRoutes();handler.realm=root
    body={'agent':'a','job':'j','retries':2}
    assert handler._save_job(body)['ok']
    path=root/'agents/a/jobs/j.json'
    assert util.read_json_state(path)['retries']==2
    assert not handler._save_job({**body,'retries':4})['ok']
    assert util.read_json_state(path)['retries']==2
