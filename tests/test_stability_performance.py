"""Scaling contracts and stalled-observer regressions, without live providers."""
import io
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from armada import app, job_history, reader, thread_windows, util
from armada.stream_observer import StreamObserver
from armada.threads import Thread
from armada.view_cache import ViewCache, history_stamp
from armada.webui import threadsview
from golden_support import build_fixture


def test_roster_and_startup_do_not_open_history(tmp_path, monkeypatch):
    root = Path(build_fixture(tmp_path / 'realm'))
    original = reader._read
    def read(path):
        assert 'runs' not in path.parts and 'jobs' not in path.parts
        return original(path)
    monkeypatch.setattr(reader, '_read', read)
    assert reader.name(root)
    assert len(reader.roster(root).agents) == 3


def test_history_annotation_scan_has_no_per_record_stat(tmp_path, monkeypatch):
    root = Path(build_fixture(tmp_path / 'realm'))
    ad = root / 'agents/captain'
    path = ad / 'runs/captain.jsonl'
    path.parent.mkdir(exist_ok=True)
    path.write_text(''.join(json.dumps({'run_id': f'run-{n}', 'task': 'test',
                                      'status': 'ok', 'ts': '2026-10-27T10:00:00'}) + '\n'
                            for n in range(1000)))
    original = Path.stat
    def stat(self, *args, **kwargs):
        assert not (self.parent.name == 'annotations' and self.suffix == '.json')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat)
    assert len(job_history.reports(ad)) == 1000
    assert reader.read(root).agents


def test_new_annotation_is_seen_on_next_scan(tmp_path):
    ad = tmp_path / 'agents/a'
    before = job_history.annotation_names(ad)
    assert before == frozenset()
    p = ad / 'runs/annotations/run-1.json'
    p.parent.mkdir(parents=True)
    p.write_text('{}')
    assert job_history.annotation_names(ad) == frozenset({'run-1.json'})


def test_unchanged_poll_does_not_render_or_parse_histories(tmp_path, monkeypatch):
    root = Path(build_fixture(tmp_path / 'realm'))
    other = Thread(root / 'agents/captain', 'other')
    other.append('Second question', 'Second answer')
    first = thread_windows.state(root, 'captain', 'main')
    def forbidden(*args, **kwargs):
        raise AssertionError('unchanged conversation rebuilt')
    with monkeypatch.context() as patch:
        patch.setattr(threadsview, '_render_turns', forbidden)
        patch.setattr(Thread, 'snapshot', forbidden)
        same = thread_windows.state(root, 'captain', 'main', first['revision'])
    assert 'html' not in same
    assert same['previews']['other'] == 'Second answer'
    other.append('New question', 'New answer')
    changed = thread_windows.state(root, 'captain', 'main', first['revision'])
    assert 'html' not in changed and changed['previews']['other'] == 'New answer'


def test_external_replacement_progress_and_truncate_invalidate(tmp_path):
    root = Path(build_fixture(tmp_path / 'realm'))
    th = Thread(root / 'agents/captain')
    first = thread_windows.state(root, 'captain', 'main')
    util.write_text_atomic(th.msgs, json.dumps({'role': 'user', 'content': 'External edit', 'turn': 'external'}) + '\n')
    changed = thread_windows.state(root, 'captain', 'main', first['revision'])
    assert 'External edit' in changed['html']
    th.save_progress('external', 'Saved progress', 'Working', [])
    progress = thread_windows.state(root, 'captain', 'main', changed['revision'])
    assert 'Saved progress' in progress['html']
    th.truncate(0)
    assert 'No messages yet' in thread_windows.state(root, 'captain', 'main', progress['revision'])['html']


def test_pending_transaction_cannot_reuse_cached_history(tmp_path):
    th = Thread(tmp_path, 'main')
    th.append('Q', 'A')
    stamp = history_stamp(th)
    (th.dir / '.history-transaction.json').write_text('{}')
    assert history_stamp(th) != stamp
    assert history_stamp(th) != history_stamp(th)


def test_view_cache_bounds_and_racing_mutation():
    cache = ViewCache(limit=2, bytes_limit=100)
    version = [0]
    def race():
        version[0] += 1
        return 'outdated'
    assert cache.read('race', lambda: version[0], race) == 'outdated'
    assert not cache.values
    for i in range(5):
        cache.read(i, lambda: 0, lambda: 'x' * 20)
    assert len(cache.values) == 2 and cache.bytes <= 100
    cache.read('large', lambda: 0, lambda: 'x' * 200)
    assert 'large' not in cache.values


def test_browser_deadline_covers_evaluate_and_bounds_stalled_workers(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(app, '_browser_calls', slots)
    entered, release = threading.Event(), threading.Event()
    calls = []
    class Browser:
        def evaluate_js(self, script, callback):
            calls.append(script)
            entered.set()
            release.wait(3)
            callback('late')
    start = time.monotonic()
    try:
        with pytest.raises(OSError, match='did not complete'):
            app._browser_result(Browser(), 'one', timeout=.04)
        assert entered.is_set() and time.monotonic() - start < 1
        with pytest.raises(OSError, match='busy'):
            app._browser_result(Browser(), 'two', timeout=.04)
        assert len(calls) == 1 and '"one"' in calls[0]
    finally:
        release.set()
        assert slots.acquire(timeout=2)
        slots.release()


def test_observer_does_not_block_producer_and_is_bounded():
    entered, release = threading.Event(), threading.Event()
    class SlowWriter:
        def write(self, data):
            entered.set()
            release.wait(3)
        def flush(self):
            pass
    observer = StreamObserver(SimpleNamespace(wfile=SlowWriter()))
    try:
        observer({'kind': 'text', 'text': 'first'})
        assert entered.wait(1)
        start = time.monotonic()
        for _ in range(200):
            observer({'kind': 'render', 'html': 'x' * 10000})
        assert time.monotonic() - start < 1
        assert observer.closed.is_set()
        assert observer.events.qsize() <= 128 and observer.bytes <= observer.MAX_BYTES
    finally:
        release.set()
        observer.close()
    assert not observer.worker.is_alive()


def test_observer_delivers_ordered_terminal_event():
    writer = io.BytesIO()
    observer = StreamObserver(SimpleNamespace(wfile=writer))
    for event in [{'kind': 'text', 'text': 'Hello'}, {'kind': 'done', 'ok': True}]:
        observer(event)
    observer.close()
    events = [json.loads(line[6:]) for line in writer.getvalue().decode().splitlines() if line]
    assert [e['kind'] for e in events] == ['text', 'done']
