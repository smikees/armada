"""Disposable presentation indexes agree with canonical data and cannot grant execution."""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
from pathlib import Path
import threading
import os
from contextlib import contextmanager

import pytest

from armada import records, run_summary as summary, util, job_history, reader, thread_windows
from armada.threads import Thread
from armada.view_cache import ViewCache
from golden_support import build_fixture


def seed(tmp_path, rows):
    ad = tmp_path / 'agents/a'
    path = ad / 'runs/a.jsonl'
    path.parent.mkdir(parents=True)
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    return ad, path


def event(n, **changes):
    return dict({'ts': f'2026-11-{n % 6 + 1:02}T10:00:00', 'task': f'job{n % 3}',
                 'run_id': f'run{n}', 'status': 'ok', 'kind': 'job', 'thread': 'job-run--test',
                 'model': 'claude-sonnet-4-6', 'tokens': {'total': n, 'api_equiv_usd': n / 100}}, **changes)


def test_totals_and_recent_queries_match_full_scan(tmp_path):
    rows = [event(n, tokens={} if n % 7 == 0 else {'total': n, 'api_equiv_usd': n / 100}) for n in range(300)]
    rows.append(event(500, ts='2020-01-01T10:00:00', task='rarely-run'))
    ad, path = seed(tmp_path, rows)
    latest, count, tokens, cost, errors = summary.totals(ad, '2026-11-03')
    selected = [row for row in rows if row['ts'][:10] >= '2026-11-03']
    assert not errors and count == len(selected)
    assert tokens == sum(row['tokens'].get('total', 0) for row in selected) and cost is None
    assert latest['rarely-run'] == ('2020-01-01T10:00:00', 'ok')
    assert summary.recent(ad, '2026-11-03') == selected
    assert sum(row['_count'] for row in summary.usage(ad)) == len(rows)
    assert path.read_text(encoding='utf-8').count('\n') == len(rows)


def test_append_parses_only_suffix_and_warm_reads_parse_nothing(tmp_path, monkeypatch):
    ad, path = seed(tmp_path, [event(n) for n in range(100)])
    summary.totals(ad, '')
    decoded = []
    original = records.history_lines
    def parse(path, lines, **kw):
        decoded.extend(lines)
        return original(path, lines, **kw)
    monkeypatch.setattr(records, 'history_lines', parse)
    assert summary.totals(ad, '')[1] == 100 and not decoded
    with path.open('a', encoding='utf-8') as out:
        out.write(json.dumps(event(101)) + '\n')
    assert summary.totals(ad, '')[1] == 101 and len(decoded) == 1


@pytest.mark.parametrize('change', ['truncate', 'replace', 'edit_and_append', 'unfinished_line'])
def test_external_changes_rebuild_without_reusing_stale_offsets(tmp_path, change):
    ad, path = seed(tmp_path, [event(1), event(2)])
    summary.totals(ad, '')
    changed = [event(3, status='error')]
    if change == 'unfinished_line':
        path.write_text(json.dumps(event(3))[:-1], encoding='utf-8')
        assert summary.totals(ad, '')[4]
        with path.open('a', encoding='utf-8') as out:
            out.write('}\n')
        changed = [event(3)]
    elif change == 'replace':
        util.write_text_atomic(path, json.dumps(changed[0]) + '\n')
    elif change == 'edit_and_append':
        changed += [event(2), event(4)]
        path.write_text(''.join(json.dumps(row)+'\n' for row in changed), encoding='utf-8')
    else:
        path.write_text(json.dumps(changed[0])+'\n', encoding='utf-8')
    assert summary.totals(ad, '')[1] == len(changed)
    assert summary.recent(ad, '') == changed


def test_annotation_creation_edit_and_removal_rebuild_latest(tmp_path):
    ad, path = seed(tmp_path, [event(1)])
    assert summary.totals(ad, '')[0]['job1'][1] == 'ok'
    annotation = ad / 'runs/annotations/run1.json'
    result = {'schema_version': 1, 'run_id': 'run1', 'execution': 'failed'}
    util.write_json_atomic(annotation, {'schema_version': 1, 'run_id': 'run1', 'result': result})
    expected = job_history.reports(ad)[0]['status']
    assert summary.totals(ad, '')[0]['job1'][1] == expected
    annotation.write_text('{}', encoding='utf-8')
    assert summary.totals(ad, '')[0]['job1'][1] == 'ok'
    annotation.unlink()
    assert summary.totals(ad, '')[0]['job1'][1] == 'ok'


def test_corruption_is_reported_preserved_and_rechecked_by_execution(tmp_path):
    ad, path = seed(tmp_path, [event(1)])
    summary.totals(ad, '')
    with path.open('a', encoding='utf-8') as out:
        out.write('{broken\n')
    before = path.read_bytes()
    result = summary.totals(ad, '')
    assert result[1] == 1 and 'row 2' in result[4][0] and path.read_bytes() == before
    util.write_json_atomic(tmp_path / 'realm.json', {'name': 'synthetic'})
    util.write_json_atomic(ad / 'agent.json', {'id': 'a'})
    reader.read(tmp_path)
    (ad / 'agent.json').write_text('{broken', encoding='utf-8')
    with pytest.raises(util.StateError):
        records.admit_agent(tmp_path, 'a')


def test_revalidation_and_eviction_are_disposable(tmp_path, monkeypatch):
    ad, path = seed(tmp_path, [event(1)])
    summary.totals(ad, '')
    monkeypatch.setattr(summary, 'MAX_AGE', 0)
    assert summary.totals(ad, '')[1] == 1
    monkeypatch.setattr(summary, 'MAX_BYTES', 1)
    assert summary.totals(ad, '')[1] == 1
    assert not summary._values and summary._bytes == 0


def test_multiple_windows_coalesce_rebuild_and_recover_from_builder_error():
    cache = ViewCache()
    entered, release = threading.Event(), threading.Event()
    built = []
    def build():
        built.append(True)
        entered.set()
        assert release.wait(5)
        return 'one coherent render'
    with ThreadPoolExecutor(max_workers=4) as pool:
        calls = [pool.submit(cache.read, 'thread', lambda: 1, build) for _ in range(4)]
        try:
            assert entered.wait(5)
            release.set()
            assert all(call.result(5) == 'one coherent render' for call in calls)
        finally:
            release.set()
    assert len(built) == 1
    with pytest.raises(ValueError):
        cache.read('error', lambda: 1, lambda: (_ for _ in ()).throw(ValueError()))
    assert cache.read('error', lambda: 1, lambda: 'recovered') == 'recovered'


def test_unrelated_job_report_does_not_invalidate_conversation_previews(tmp_path, monkeypatch):
    root = Path(build_fixture(tmp_path / 'realm'))
    ad = root / 'agents/captain'
    Thread(ad, 'other').append('Question', 'Answer')
    first = thread_windows.state(root, 'captain', 'main')
    path = ad / 'runs/captain.jsonl'
    path.parent.mkdir(exist_ok=True)
    with path.open('a', encoding='utf-8') as out:
        out.write(json.dumps(event(1))+'\n')
    monkeypatch.setattr(Thread, 'snapshot', lambda *a: pytest.fail('Unrelated report rebuilt transcript/preview'))
    same = thread_windows.state(root, 'captain', 'main', first['revision'])
    assert 'html' not in same and same['previews']['other'] == 'Answer'


def test_unicode_separators_remain_json_string_content(tmp_path):
    row = event(1, summary='First\u2028Second\u0085Third\u2029Fourth')
    ad, path = seed(tmp_path, [row])
    assert records.history(path) == ([row], [])
    assert summary.recent(ad, '') == [row]


def test_only_file_leading_bom_is_accepted_like_canonical_reader(tmp_path):
    ad, path = seed(tmp_path, [])
    path.write_bytes(('\ufeff'+json.dumps(event(1))+'\n\ufeff'+json.dumps(event(2))+'\n').encode('utf-8'))
    rows, errors = records.history(path)
    assert rows == [event(1)] and errors
    assert summary.totals(ad, '')[4] == errors
    assert summary.recent(ad, '') == rows


def test_date_query_retries_append_between_stamp_and_lock(tmp_path, monkeypatch):
    ad, path = seed(tmp_path, [event(1)])
    summary.totals(ad, '')
    original = util.file_lock
    injected = []
    @contextmanager
    def racing_lock(*args, **kwargs):
        if not injected:
            injected.append(True)
            with path.open('a', encoding='utf-8') as out:
                out.write(json.dumps(event(2))+'\n')
        with original(*args, **kwargs):
            yield
    monkeypatch.setattr(util, 'file_lock', racing_lock)
    assert summary.recent(ad, '') == [event(1), event(2)]


def test_same_size_edit_with_restored_mtime_is_revalidated(tmp_path, monkeypatch):
    ad, path = seed(tmp_path, [event(1)])
    assert summary.totals(ad, '')[2] == 1
    before = path.stat()
    path.write_text(json.dumps(event(2))+'\n', encoding='utf-8')
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    # Windows creation time can also stay unchanged; the bounded revalidation is
    # required when an external editor deliberately preserves all stamp fields.
    monkeypatch.setattr(summary, 'MAX_AGE', 0)
    assert summary.totals(ad, '')[2] == 2


def test_concurrent_appends_and_readers_never_mix_generations(tmp_path):
    ad, path = seed(tmp_path, [event(1)])
    def append():
        for n in range(2, 32):
            with util.file_lock(path, validate_state=False), path.open('a', encoding='utf-8') as out:
                out.write(json.dumps(event(n))+'\n')
    def read():
        for _ in range(12):
            rows = summary.recent(ad, '')
            assert [r['run_id'] for r in rows] == [f'run{n}' for n in range(1, len(rows)+1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        work = [pool.submit(append), *(pool.submit(read) for _ in range(3))]
        for future in work:
            future.result(20)
    assert summary.recent(ad, '') == [event(n) for n in range(1, 32)]


@pytest.mark.parametrize('mode,window', [('line','today'), ('line','7d'), ('line','mtd'),
                                      ('graph','daily'), ('graph','weekly'), ('graph','monthly')])
@pytest.mark.parametrize('by', ['agents', 'models'])
def test_usage_summary_matches_full_scan_for_all_views(tmp_path, monkeypatch, mode, window, by):
    from armada.webui import _core
    from armada import clock, sysusage
    root = Path(build_fixture(tmp_path / 'realm'))
    agents = list((root / 'agents').iterdir())
    for ad in agents:
        rows = []
        for n in range(180):
            day = clock.today() - dt.timedelta(days=n % 70)
            accounting = [{}, {'total': None}, {'total': n, 'api_equiv_usd': .01},
                          {'total': n, 'input': n, 'output': 3}, {'total': n, 'api_equiv_usd': None}][n % 5]
            rows.append(event(n, ts=day.isoformat()+'T10:00:00', tokens=accounting,
                              model=['gpt-6-sol', 'gemini-3.8-flash', '', 'unknown'][n % 4]))
        util.write_text_atomic(ad / 'runs' / (ad.name+'.jsonl'),
                               ''.join(json.dumps(row)+'\n' for row in rows))
    util.write_text_atomic(root / 'system_runs.jsonl', ''.join(json.dumps(row)+'\n' for row in rows[:15]))
    realm = reader.roster(root)
    actual = _core._usage_data(realm, root, mode, window, by)
    # Feed canonical individual records through the same presentation: this is an
    # independent oracle for aggregation, date windows, known/unknown counts and costs.
    monkeypatch.setattr(summary, 'usage', lambda ad=None, **kw:
                        job_history.reports(ad) if ad is not None else sysusage.runs(kw['system_root']))
    assert actual == _core._usage_data(realm, root, mode, window, by)


def test_render_and_metrics_share_one_completed_snapshot(tmp_path, monkeypatch):
    from armada.webui import threadsview
    root = Path(build_fixture(tmp_path / 'realm'))
    th = Thread(root / 'agents/captain', 'main')
    th.append('One question', 'One answer')
    original = Thread.display_snapshot
    calls = []
    def snapshot(self):
        calls.append(self.name)
        return original(self)
    monkeypatch.setattr(Thread, 'display_snapshot', snapshot)
    monkeypatch.setattr(Thread, 'render', lambda *args: pytest.fail('Metrics reread canonical history'))
    a = reader.roster(root).coordinator
    state = threadsview._turn_snapshot(root, a.id, 'main', th)
    html = threadsview._render_turns(root, a, 'main', state=state)
    metrics = threadsview.thread_metrics(root, a.id, 'main', thread=th, snapshot=state[:2])
    assert calls == ['main'] and 'One answer' in html and metrics['messages'] >= 2


def test_legacy_filter_tolerates_invalid_message_timestamp(tmp_path):
    ad, _ = seed(tmp_path, [event(1, thread='main')])
    assert job_history.legacy_turns(ad, 'main', [{'role':'assistant', 'ts': []}]) == set()
