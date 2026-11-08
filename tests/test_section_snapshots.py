"""Slow or invalid snapshot sources never block rendering or replace a good local copy."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time

import pytest

from armada import section_snapshots as snapshots, serve, util


def fixture(tmp_path, count=1):
    root = tmp_path / 'realm'
    root.mkdir()
    source = tmp_path / 'source.html'
    source.write_text('<html>new synthetic copy</html>')
    sections = [{'name': str(n), 'source': str(source), 'snapshot': f'shared/copy-{n}.html'} for n in range(count)]
    util.write_json_atomic(root / 'realm.json', {'name': 'Synthetic', 'sections': sections})
    handler = object.__new__(serve.Handler)
    handler.realm = str(root)
    return root, source, sections, handler


def done(root, ticket, index=0):
    end = time.monotonic() + 5
    while time.monotonic() < end:
        state = snapshots.request(root, index, ticket=ticket)
        if not state.get('pending'):
            return state
        time.sleep(.01)
    pytest.fail('Background refresh did not finish')


def test_slow_source_does_not_block_render_or_duplicate_work(tmp_path, monkeypatch):
    root, source, sections, handler = fixture(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original, calls = snapshots._local, []
    def slow(path):
        calls.append(path)
        entered.set()
        assert release.wait(5)
        return original(path)
    monkeypatch.setattr(snapshots, '_local', slow)
    try:
        first = handler._section_snapshot({'index': 0})
        assert first['ok'] and first['pending'] and entered.wait(2)
        assert handler._section_snapshot({'index': 0})['ticket'] == first['ticket']
        responses = []
        handler._send = lambda *args: responses.append(args)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(handler._section_raw, '/section-raw/0').result(1)
        assert responses[0][0] == 200 and 'not ready' in responses[0][1]
        assert len(calls) == 1
    finally:
        release.set()
    assert done(root, first['ticket'])['changed']
    assert (root / sections[0]['snapshot']).read_text() == source.read_text()


def test_failure_preserves_copy_and_reports_failure(tmp_path, monkeypatch):
    root, _, sections, handler = fixture(tmp_path)
    dest = root / sections[0]['snapshot']
    util.write_text_atomic(dest, 'existing copy')
    monkeypatch.setattr(snapshots, '_local', lambda _: (_ for _ in ()).throw(OSError('synthetic failure')))
    start = handler._section_snapshot({'index': 0})
    state = done(root, start['ticket'])
    assert state['ok'] is False and state['error'] and dest.read_text() == 'existing copy'


def test_changed_section_cannot_receive_obsolete_refresh(tmp_path, monkeypatch):
    root, _, sections, handler = fixture(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def read(_):
        entered.set()
        assert release.wait(5)
        return '<html>obsolete</html>'
    monkeypatch.setattr(snapshots, '_local', read)
    try:
        first = handler._section_snapshot({'index': 0})
        assert entered.wait(2)
        util.write_json_atomic(root / 'realm.json', {'name': 'Synthetic', 'sections': []})
    finally:
        release.set()
    # Poll the retained internal job only to wait for cleanup after its public section disappeared.
    end = time.monotonic() + 5
    while time.monotonic() < end:
        with snapshots._lock:
            state = next(s for s in snapshots._jobs.values() if s['ticket'] == first['ticket'])
            if not state['pending']:
                break
        time.sleep(.01)
    assert not state['pending'] and not state['ok']
    assert not (root / sections[0]['snapshot']).exists()


def test_queue_and_worker_counts_are_bounded(tmp_path, monkeypatch):
    root, _, _, _ = fixture(tmp_path, 10)
    release, entered = threading.Event(), threading.Event()
    active, maximum, calls = 0, 0, 0
    lock = threading.Lock()
    def refresh(*args, **kwargs):
        nonlocal active, maximum, calls
        with lock:
            calls += 1
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                entered.set()
        try:
            assert release.wait(5)
        finally:
            with lock:
                active -= 1
        return {'changed': False}
    monkeypatch.setattr(snapshots, 'refresh', refresh)
    try:
        accepted = [snapshots.request(root, n) for n in range(8)]
        assert all(s['pending'] for s in accepted) and entered.wait(2)
        assert snapshots.request(root, 8)['ok'] is False
    finally:
        release.set()
    assert all(done(root, s['ticket'], n)['ok'] for n, s in enumerate(accepted))
    assert maximum == 2 and calls == 8


def test_oversized_source_is_refused(tmp_path, monkeypatch):
    root, source, sections, _ = fixture(tmp_path)
    monkeypatch.setattr(snapshots, 'MAX_BYTES', 8)
    with pytest.raises(ValueError, match='limit'):
        snapshots.refresh(root, sections[0])
    assert not (root / sections[0]['snapshot']).exists()


@pytest.mark.parametrize('fault', ['size', 'deadline', 'disconnect'])
def test_http_failure_preserves_existing_copy(tmp_path, monkeypatch, fault):
    root, _, sections, _ = fixture(tmp_path)
    section = dict(sections[0], source='https://synthetic.invalid/report')
    dest = root / section['snapshot']
    util.write_text_atomic(dest, 'previous complete copy')
    monkeypatch.setattr(snapshots, 'MAX_BYTES', 32)
    clock = [0]
    monkeypatch.setattr(snapshots.time, 'monotonic', lambda: clock[0])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read1(self, size):
            if fault == 'disconnect':
                raise OSError('synthetic disconnect')
            if fault == 'deadline':
                clock[0] = 21
            return b'x' * size

    def open_url(request, timeout):
        assert timeout == 5 and request.full_url == section['source']
        return Response()

    monkeypatch.setattr(snapshots.urllib.request, 'urlopen', open_url)
    with pytest.raises((ValueError, TimeoutError, OSError)):
        snapshots.refresh(root, section, force=True)
    assert dest.read_text() == 'previous complete copy'


def test_combined_css_and_fragment_limit(tmp_path, monkeypatch):
    root, source, sections, _ = fixture(tmp_path)
    source.write_text('x' * 200)
    css = tmp_path / 'style.css'
    css.write_text('y' * 200)
    monkeypatch.setattr(snapshots, 'MAX_BYTES', 450)
    with pytest.raises(ValueError, match='limit'):
        snapshots.refresh(root, dict(sections[0], css=str(css)))
    assert not (root / sections[0]['snapshot']).exists()
