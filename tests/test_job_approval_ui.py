"""Owner approval status is visible without rendering a page granting approval."""
import datetime as dt
import hashlib
import json

import pytest
from armada import appconfig, reader, run_policy, util, webui
from armada.job_access import identity, fingerprint
from armada.webui.realmpages import _job_row


@pytest.fixture
def saved(tmp_path):
    root=tmp_path/'realm';p=root/'agents/a/jobs/daily.json'
    util.write_json_atomic(root/'realm.json', {'name':'Synthetic','schema_version':4})
    util.write_json_atomic(root/'agents/a/agent.json', {'id':'a','display':'Ada','coordinator':True})
    job={'id':'daily','name':'Daily report','kind':'agent','prompt':'Synthetic text',
         'allow_tools':True,'schedule':'daily 09:00'}
    util.write_json_atomic(p,job);run_policy.seal_job(root,'a',job)
    return root,p,job


def row(root):
    realm=reader.read(root);a=realm.agents[0];j=a.jobs[0]
    return _job_row(root,a,j,dt.datetime.now(),[],set(),True)


@pytest.mark.parametrize('change',[{'critical':True},{'timeout':600},{'prompt':'Changed text'},
                                   {'plan_limit_action':'api'},{'schedule':'daily 10:00'}])
def test_saved_job_approval_badge_reason_filter_and_action(saved,change):
    root,p,job=saved;updated={**job,**change};util.write_json_atomic(p,updated)
    before=run_policy._path().read_bytes(),p.read_bytes()
    html=row(root)
    assert 'Needs approval' in html and 'changed after approval' in html
    assert 'data-jstatus="approval"' in html and 'Review and approve' in html
    assert 'disabled ' in html.split('Run now</button>')[0].rsplit('<button',1)[1]
    assert before==(run_policy._path().read_bytes(),p.read_bytes())
    run_policy.seal_job(root,'a',updated)
    assert 'Needs approval' not in row(root)


@pytest.mark.parametrize('grant', [{}, {'fingerprint':'changed','roots':[]}])
def test_unsealed_control_and_stale_extra_access_are_marked(saved, grant):
    root,p,job=saved
    assert run_policy.approval_reason(root,'a',{**job,'id':'new','critical':True})
    appconfig.save({'job_access':{identity(root,'a','daily'):grant}})
    assert 'Approved access' in run_policy.approval_reason(root,'a',job)
    assert 'Needs approval' in row(root)


def test_legacy_preview_has_no_side_effects(saved):
    root,p,job=saved
    old={k:job.get(k) for k in ('id','kind','prompt','allow_tools',*run_policy.LEGACY_JOB_FIELDS)}
    seal=hashlib.sha256(json.dumps(old,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key=identity(root,'a','daily')
    util.write_json_atomic(run_policy._path(),{'jobs':{key:seal}})
    appconfig.save({'job_access':{key:{'fingerprint':seal,'roots':[]}}})
    before=run_policy._path().read_bytes(),appconfig._path().read_bytes()
    assert run_policy.approval_reason(root,'a',job)==''
    assert before==(run_policy._path().read_bytes(),appconfig._path().read_bytes())


def test_unreadable_approval_state_never_looks_approved(saved,monkeypatch):
    root,p,job=saved
    def fail(): raise util.StateError('Approval record unreadable')
    monkeypatch.setattr(run_policy,'_read',fail)
    assert 'Approval record unreadable' in row(root)


def test_calendar_marks_future_hold_without_rewriting_past_result(saved):
    root,p,job=saved;util.write_json_atomic(p,{**job,'critical':True})
    today=dt.date.today();future=today+dt.timedelta(days=1)
    realm=reader.read(root)
    events=webui._jobcal_events(realm,root,future,future)
    assert events and events[0]['status']=='approval' and events[0]['approval_reason']


def test_frequent_system_jobs_remain_calendar_entries(saved):
    root,_,_=saved;now=dt.datetime.now();past=now-dt.timedelta(minutes=2)
    jobs=[{'id':'inbox-dispatch','name':'Inbox','every_minutes':1,'enabled':True,
           'last_run':past.isoformat(),'status':'ok','runs':[{'ts':past.isoformat(),'status':'ok'}]}]
    events=webui._sysjobcal_events(root,now.date(),now.date()+dt.timedelta(days=7),jobs=jobs)
    assert [r['status'] for r in events]==['success','scheduled']
    jobs[0]['status']='running'
    assert any(r['status']=='running' for r in webui._sysjobcal_events(root,now.date(),now.date(),jobs=jobs))


def test_broken_saved_job_is_in_review_filter(saved):
    root,p,job=saved
    p.write_text('{broken', encoding='utf-8')
    html=row(root)
    assert 'Needs repair' in html and 'Needs review' in html
    assert 'data-jstatus="approval"' in html


def test_missing_tool_choice_is_marked_for_review(saved):
    root,p,job=saved
    job.pop('allow_tools')
    util.write_json_atomic(p,job)
    run_policy.seal_job(root,'a',job)
    html=row(root)
    assert 'Needs review' in html and 'Review job' in html
    assert 'data-jstatus="approval"' in html
    assert 'Needs approval' not in html
