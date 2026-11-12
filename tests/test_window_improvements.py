import json
from pathlib import Path
from types import SimpleNamespace
from armada import app,util,reader,clock
from armada.monitor_recovery import reachable,fit
from armada.webui.activity_monitor import content
from golden_support import build_fixture


def test_monitor_snapshot_cannot_wait_for_native_window_creation(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock=threading.RLock()
    main,companion=object(),object()
    monkeypatch.setattr(app,'_window_lock',lock)
    monkeypatch.setattr(app,'_main_window',main)
    monkeypatch.setattr(app,'_alex_window',None)
    monkeypatch.setattr(app,'_thread_windows',{'saved':companion})
    lock.acquire()
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            assert pool.submit(app._desktop_windows).result(timeout=1)==[main,companion]
        finally:
            lock.release()


def test_display_removal_and_negative_monitor_coordinates():
    areas=[(-1920,0,1920,1080),(1920,0,1920,1080)]
    assert not reachable((100,100,1440,800),areas)
    assert reachable((-1800,20,1440,800),areas)
    assert not reachable((10,-790,1440,800),[(0,0,1920,1080)])
    assert fit((100,100,1440,900),(-1280,0,1280,720)) == (-1280,0,1280,720)
    assert fit((40,40,520,600),(0,0,1920,1080),20) == (60,60,520,600)


def test_session_retains_quit_windows_and_removes_explicitly_closed_ones(tmp_path,monkeypatch):
    monkeypatch.setattr(util,'data_dir',lambda:tmp_path)
    row={'root':str(tmp_path/'realm'),'agent':'a','thread':'main'}
    window=SimpleNamespace(_armada_thread_target=row)
    monkeypatch.setattr(app,'_thread_windows',{'one':window})
    monkeypatch.setattr(app,'_quitting',False)
    app._save_thread_windows()
    assert json.loads((tmp_path/'desktop-threads.json').read_text())['threads'] == [row]
    monkeypatch.setattr(app,'_quitting',True)
    app._clear_thread_window('one',window)
    assert json.loads((tmp_path/'desktop-threads.json').read_text())['threads'] == [row]
    monkeypatch.setattr(app,'_quitting',False)
    monkeypatch.setattr(app,'_thread_windows',{'one':window})
    app._clear_thread_window('one',window)
    assert json.loads((tmp_path/'desktop-threads.json').read_text())['threads'] == []


def test_restore_snapshots_all_realms_even_when_open_updates_the_file(tmp_path,monkeypatch):
    monkeypatch.setattr(util,'data_dir',lambda:tmp_path)
    rows=[{'root':str(tmp_path/name),'agent':'a','thread':'main'} for name in ('first','second')]
    util.write_json_atomic(tmp_path/'desktop-threads.json',{'threads':rows})
    opened=[]
    def open_saved(root,agent,thread):
        opened.append((root,agent,thread))
        util.write_json_atomic(tmp_path/'desktop-threads.json',{'threads':[]})
    monkeypatch.setattr(app,'open_thread',open_saved)
    monkeypatch.setattr(app,'_quitting',False)
    app._restore_thread_windows()
    assert opened == [(r['root'],'a','main') for r in rows]


def test_activity_separates_simultaneous_states_and_clears_recovered_failure(tmp_path,monkeypatch):
    from armada.webui import activity_monitor as monitor
    root=Path(build_fixture(tmp_path/'realm'))
    monkeypatch.setattr(monitor,'_agent_busy',lambda *_:True)
    monkeypatch.setattr(monitor,'_has_pending_proposals',lambda *_:True)
    meta=root/'agents/captain/threads/meta.json'
    util.write_json_atomic(meta,{'unread':{'main':True},'titles':{'main':'<Unread>'}})
    runs=root/'agents/captain/runs/captain.jsonl'
    runs.parent.mkdir(exist_ok=True)
    rows=[{'ts':clock.now().isoformat(),'task':'chat:main','thread':'main','status':'error'}]
    runs.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
    rendered=content(reader.read(root),root)
    assert all(name in rendered for name in ('Working','Unread replies','Needs input','Failed replies','Needs attention'))
    assert '&lt;Unread&gt;' in rendered and '<Unread>' not in rendered
    assert json.loads(meta.read_text())['unread']['main'] is True
    assert 'Failed replies <span>1</span>' in rendered
    rows.append({**rows[0],'ts':(clock.now()+__import__('datetime').timedelta(seconds=1)).isoformat(),'status':'ok'})
    runs.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
    assert 'Failed replies <span>0</span>' in content(reader.read(root),root)


def test_detached_header_shares_badge_and_has_no_redundant_thread_label(tmp_path):
    from armada.webui.thread_window import render
    root=build_fixture(tmp_path/'realm')
    meta=Path(root)/'agents/captain/threads/meta.json'
    util.write_json_atomic(meta,{'unread':{'main':True}})
    html=render(root,'captain','main')
    assert 'mc-agent-model-badge' in html
    assert html.index('mc-agent-model-badge') < html.index('class="mc-ax-subtitle"')
    assert 'main thread ·' not in html
    assert json.loads(meta.read_text())['unread']['main'] is True


def test_activity_is_a_builtin_widget_and_outside_dashboard_header(tmp_path):
    from armada import addons
    from armada.webui.pages import render_dashboard
    root=build_fixture(tmp_path/'realm')
    html=render_dashboard(reader.read(root),root)
    assert 'activity' in addons.BUILTIN_WIDGETS
    assert 'data-id="activity"' in html and 'Activity monitor' in html
    assert html.index('data-activity-monitor') > html.index('id="mc-grid"')
    assert 'mc-attention-summary' not in html[html.index('id="mc-ovh"'):html.index('id="mc-grid"')]
    assert 'data-activity-refresh' in html and 'aria-label="Refresh activity"' in html


def test_activity_deduplicates_portraits_and_tracks_completion_without_marking_read(tmp_path):
    root=Path(build_fixture(tmp_path/'realm'))
    agent=root/'agents/captain'
    util.write_json_atomic(agent/'threads/meta.json',{'unread':{'main':True,'other':True}})
    marker=agent/'runs/.running/avatar-test.json'
    util.write_json_atomic(marker,{})
    rendered=content(reader.read(root),root)
    assert rendered.count('data-activity-key="working:captain"')==1
    assert rendered.count('data-activity-key="unread-replies:captain"')==1
    assert 'data-act="working"' in rendered and 'animation:mc-actwork' in rendered
    assert '<details' not in rendered and '<summary' not in rendered
    assert rendered.index('class="mc-attention-summary')>rendered.index('data-activity-group="failed-replies"')
    assert 'border-radius:50%' in rendered
    marker.unlink()
    completed=content(reader.read(root),root)
    assert 'data-activity-key="working:captain"' not in completed
    assert 'data-activity-key="unread-replies:captain"' in completed
    assert 'data-act="unseen"' in completed
    assert util.read_json_state(agent/'threads/meta.json')['unread']=={'main':True,'other':True}


def test_mark_read_requires_an_explicit_thread_action(tmp_path):
    import http.client
    from golden_support import ServedRealm
    from armada.request_context import RealmContext
    root=build_fixture(tmp_path/'realm')
    meta=Path(root)/'agents/captain/threads/meta.json'
    util.write_json_atomic(meta,{'unread':{'main':True}})
    with ServedRealm(root) as server:
        headers={**server.auth_headers(),'Content-Type':'application/json','X-Armada-Realm':RealmContext.capture(root).realm_id,'X-Armada-Companion':'thread'}
        connection=http.client.HTTPConnection('127.0.0.1',server.port,timeout=10)
        try:
            connection.request('POST','/api/thread-read',json.dumps({'agent':'captain','thread':'main'}),headers)
            response=connection.getresponse()
            assert response.status==200 and json.loads(response.read())['ok']
        finally:
            connection.close()
    assert json.loads(meta.read_text())['unread']['main'] is False
