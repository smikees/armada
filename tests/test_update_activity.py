"""Update draining, lifetime ownership and visibility, without provider calls."""
import datetime
import json
import os
import threading
import time
import shutil
import subprocess
from pathlib import Path
import pytest

from armada import activerealm, execution, execution_admission as admission, reader, sysjobs, updater, util
from armada.request_context import RunContext
from armada.webui.activity_monitor import content
from armada.webui.agentbits import _running_markers
from armada.routes.jobs import JobRoutes
from golden_support import build_fixture
from test_updater import inst, _release


@pytest.mark.skipif(shutil.which('node') is None,reason='Node is needed for browser checks')
def test_calendar_browser_views():
    result=subprocess.run(['node',str(Path(__file__).with_name('job_calendar_harness.js'))],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_update_drains_nested_inbox_wait_without_killing_running_work(inst, tmp_path, monkeypatch):
    root=Path(build_fixture(tmp_path/'realm'))
    monkeypatch.setattr(activerealm,'every',lambda:[root])
    updater.check(fetch=_release())
    parent=admission.Ticket(RunContext.capture(root,'system','system-inbox-dispatch'),'maintenance')
    assert parent.ready()
    from armada import run_policy
    monkeypatch.setattr(run_policy,'admission',lambda *a,**k:{'usage_deferred':True})
    queued=threading.Event()
    results=[]
    def inbox():
        try:
            with parent.activate(), execution.RunSession(RunContext.capture(root,'captain','inbox')):
                with admission.scope(RunContext.capture(root,'captain','inbox'),'claude',on_wait=queued.set):
                    results.append('must not execute')
        except admission.Cancelled as exc:
            results.append(str(exc))
        finally:
            parent.close()
    worker=threading.Thread(target=inbox)
    worker.start()
    try:
        assert queued.wait(5)
        updater.request_apply()
        worker.join(5)
        assert not worker.is_alive()
        assert len(results)==1 and 'update' in results[0]
        assert updater.progress()['phase']=='restarting'
        assert not admission.snapshot()
    finally:
        if worker.is_alive():
            admission.cancel(parent.context.realm.realm_id)
            worker.join(5)


def test_update_does_not_cancel_already_running_ticket(inst,tmp_path):
    root=Path(build_fixture(tmp_path/'realm'))
    updater.check(fetch=_release())
    ticket=admission.Ticket(RunContext.capture(root,'captain','main'),'claude')
    try:
        assert ticket.ready()
        assert updater.request_apply()['phase']=='waiting_tasks'
        assert ticket.ready() and not ticket.cancelled
    finally:
        ticket.close()
    assert updater.progress()['phase']=='restarting'


def test_owned_activity_survives_age_but_not_its_owner(inst,tmp_path,monkeypatch):
    root=Path(build_fixture(tmp_path/'realm'))
    monkeypatch.setattr(activerealm,'every',lambda:[root])
    ctx=RunContext.capture(root,'captain','main')
    with execution.RunSession(ctx):
        os.utime(ctx.marker,(time.time()-7200,time.time()-7200))
        assert ctx.marker.stem in _running_markers(root,'captain')
        assert updater.pending_work()
        receipt=ctx.marker.read_text()
    # Simulate failed telemetry cleanup while the same application PID lives.
    ctx.marker.write_text(receipt)
    assert ctx.marker.stem not in _running_markers(root,'captain')
    assert updater.pending_work()==[]


def test_system_job_live_lock_is_running_then_interrupted(tmp_path):
    root=Path(build_fixture(tmp_path/'realm'))
    jid='inbox-dispatch'
    util.write_json_atomic(root/'system_jobs.json',{jid:{'attempt':{
        'state':'claimed','owner_pid':os.getpid(),'attempt_id':'test','started':'2026-11-13T16:00:00+01:00'}}})
    def job():return next(j for j in sysjobs.status(root) if j['id']==jid)
    with util.file_lock(root/'.scheduler/system'/f'{jid}.json',validate_state=False):
        assert job()['status']=='running'
        assert 'System work' in content(reader.read(root),root)
    assert job()['status']=='held'
    assert 'interrupted' in job()['detail']


def test_activity_queue_moves_to_working_and_is_realm_scoped(tmp_path):
    root=Path(build_fixture(tmp_path/'realm'))
    ticket=admission.Ticket(RunContext.capture(root,'captain','inbox'),'claude')
    try:
        html=content(reader.read(root),root)
        assert 'Queued <span>1</span>' in html and 'Working <span>0</span>' in html
        assert 'data-act="queued"' in html and 'thread=inbox' in html
        assert ticket.ready()
        html=content(reader.read(root),root)
        assert 'Queued <span>0</span>' in html and 'Working <span>1</span>' in html
        other=Path(build_fixture(tmp_path/'other'))
        assert 'Working <span>0</span>' in content(reader.read(other),other)
    finally:
        ticket.close()
    assert 'Working <span>0</span>' in content(reader.read(root),root)


def test_every_calendar_scope_includes_frequent_inbox_system_jobs(tmp_path):
    root=Path(build_fixture(tmp_path/'realm'))
    route=JobRoutes()
    route.realm=root
    day=datetime.date.today().isoformat()
    for scope in ('','system'):
        data=route._job_calendar(day,day,scope)
        assert data['ok'],data
        jobs={j['id']:j for j in data['systems']}
        assert jobs['inbox-dispatch']['every_minutes']==1
        assert 'telegram-inbox' in jobs
        assert any(e['agent']=='system' for e in data['events'])
