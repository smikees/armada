"""Synthetic long-history benchmark; no live configuration, engines or notifications.

Run: python tools/history_benchmark.py build/history-benchmark.json
Warm p50/p95 use 12 samples. The cold observation is one sample, not a percentile.
Four-window timings measure the whole concurrent batch. This is not app startup.
"""
import concurrent.futures
import datetime
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from golden_support import build_fixture
from armada import util, instance, reader, thread_windows
from armada.threads import Thread
from armada.webui import _core

def samples(fn, n=12):
    values = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000)
    values.sort()
    return {'p50_ms': round(statistics.median(values), 3),
            'p95_ms': round(values[min(len(values)-1, int(len(values)*.95))], 3)}

with tempfile.TemporaryDirectory(prefix='armada-m9-') as directory:
    home = Path(directory)
    with patch.object(util, 'data_dir', lambda: home / 'account'), \
            patch.object(instance, '_account_directory', lambda: home / 'account'), \
            patch.object(Path, 'home', lambda: home):
        root = Path(build_fixture(home / 'realm'))
        today = datetime.date.today()
        for ad in (root / 'agents').iterdir():
            rows = [{'run_id': f'run-{n}', 'task': 'daily', 'kind': 'job',
                     'thread': 'job-run--daily', 'status': 'ok', 'model': 'claude-sonnet-4-6',
                     'ts': (today-datetime.timedelta(days=n % 1500)).isoformat()+'T10:00:00',
                     'tokens': {'total': 200, 'api_equiv_usd': .002}} for n in range(10000)]
            p = ad / 'runs' / (ad.name + '.jsonl')
            p.parent.mkdir(exist_ok=True)
            p.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        ad = root / 'agents/captain'
        messages = [{'role': 'user' if n % 2 == 0 else 'assistant', 'content': f'Synthetic message {n}',
                     'ts': '2026-11-06T10:00:00'} for n in range(1000)]
        for name in ['main', *[f'sibling-{n}' for n in range(20)]]:
            th = Thread(ad, name)
            th.dir.mkdir(parents=True, exist_ok=True)
            th.msgs.write_text(''.join(json.dumps(m)+'\n' for m in messages), encoding='utf-8')
        out = {'runs': 30000, 'messages_per_thread': 1000, 'siblings': 20}
        out['realm_cold_ms'] = samples(lambda: reader.read(root), 1)['p50_ms']
        out['realm_warm'] = samples(lambda: reader.read(root))
        roster = reader.roster(root)
        out['usage_warm'] = samples(lambda: _core._usage_data(roster, root, 'line', '7d'))
        first = thread_windows.state(root, 'captain', 'main')
        poll = lambda: thread_windows.state(root, 'captain', 'main', first['revision'])
        out['unchanged_poll'] = samples(poll)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            out['four_windows'] = samples(lambda: list(pool.map(lambda _: poll(), range(4))))
        out['metadata'] = samples(lambda: (reader.name(root), reader.roster(root)))
        util.write_text_atomic(Path(sys.argv[1]), json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
