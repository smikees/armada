"""Disposable presentation summaries and date indexes; never execution or policy evidence.

Canonical JSONL stays authoritative. Warm reads use file identities; growth is incremental
only after hashing the complete old prefix. Edits, truncation, replacement, annotations
and a 30-second revalidation interval cause a rebuild. Indexes are never persisted;
reads may create the existing protocol's sibling lock file.
"""
from collections import OrderedDict
import hashlib
import os
from pathlib import Path
import threading
import time

from . import records, util
from .view_cache import file_stamp

_lock = threading.Lock()
_builders = tuple(threading.RLock() for _ in range(64))
_values = OrderedDict()
_bytes = 0
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 64
MAX_AGE = 30


class _Changed(Exception):
    """A projection observed another source generation; retry with fresh offsets."""


def _path(agent_dir):
    ad = Path(agent_dir)
    return ad / 'runs' / (ad.name + '.jsonl')


def _annotations(ad):
    if ad is None:
        return ()
    directory = Path(ad) / 'runs' / 'annotations'
    try:
        return tuple((p.name, file_stamp(p)) for p in sorted(directory.iterdir()) if p.suffix == '.json')
    except FileNotFoundError:
        return ()


def _empty():
    return dict(stamp=None, annotations=(), checked=0., size=0, digest='', complete=True,
                lines=0, latest={}, days={}, usage={}, legacy={}, legacy_view={}, offsets={}, errors=[], entries=0)


def _add(index, row, offset, length):
    from .token_cost import for_run
    from .job_history import JOB_PREFIX
    ts = str(row.get('ts', ''))[:19]
    day = ts[:10]
    task = row.get('task')
    if task and (task not in index['latest'] or ts > index['latest'][task][0]):
        index['latest'][task] = (ts, str(row.get('status', 'ok')))
    if len(day) == 10:
        index['offsets'].setdefault(day, []).append((offset, length))
        index['entries'] += 1
        bucket = index['days'].setdefault(day, dict(count=0, tokens=0, cost=0.))
        bucket['count'] += 1
        tk = row.get('tokens')
        if isinstance(tk, dict):
            bucket['tokens'] += int(tk.get('total', 0) or 0)
            bucket['cost'] = (bucket['cost'] + float(tk['api_equiv_usd'])
                              if bucket['cost'] is not None and tk.get('api_equiv_usd') is not None else None)
        else:
            tk = {}
        cost = for_run(row)
        key = (day, str(row.get('model') or '').strip(), tk.get('total') is None, cost is None)
        usage = index['usage'].setdefault(key, dict(ts=day, model=key[1], _count=0,
                         tokens=dict(total=None if key[2] else 0, api_equiv_usd=None if key[3] else 0.)))
        usage['_count'] += 1
        if not key[2]:
            usage['tokens']['total'] += int(tk['total'])
        if not key[3]:
            usage['tokens']['api_equiv_usd'] += cost
    thread = row.get('thread') or 'main'
    if (row.get('kind') == 'job' and not thread.startswith(JOB_PREFIX)
            and not str(task or '').startswith('inbox:') and task != 'adhoc' and row.get('ts')):
        index['legacy'].setdefault(thread, set()).add(row['ts'])


def _build(path, ad, previous, before, annotations):
    from .job_history import apply_annotation
    index = _empty()
    index.update(stamp=before, annotations=annotations)
    if before is None:
        return index
    with util.file_lock(path, validate_state=False), path.open('rb') as source:
        digest = hashlib.sha256()
        append = (previous is not None and previous['complete'] and previous['annotations'] == annotations
                  and previous['stamp'] is not None and before[:2] == previous['stamp'][:2]
                  and before[2] > previous['size'])
        if append:
            remaining = previous['size']
            while remaining:
                part = source.read(min(remaining, 1024 * 1024))
                if not part:
                    break
                digest.update(part)
                remaining -= len(part)
            append = remaining == 0 and digest.hexdigest() == previous['digest']
        if append:
            index = previous
            index.update(stamp=before, annotations=annotations)
        else:
            source.seek(0)
            digest = hashlib.sha256()
        names = frozenset(name for name, _ in annotations)
        while True:
            offset = source.tell()
            line = source.readline()
            if not line:
                break
            digest.update(line)
            text = line.decode('utf-8-sig' if offset == 0 else 'utf-8')
            rows, errors = records.history_lines(path, [text], start_line=index['lines'])
            index['lines'] += 1
            index['errors'].extend(errors)
            index['complete'] = line.endswith(b'\n')
            for row in rows:
                if ad is not None:
                    row = apply_annotation(ad, row, names=names)
                _add(index, row, offset, len(line))
        index.update(size=source.tell(), digest=digest.hexdigest())
        index['legacy_view'] = {thread: frozenset(timestamps) for thread, timestamps in index['legacy'].items()}
    return index


def _read(path, ad, project):
    """Project under a bounded per-key lock; callers never receive mutable index internals."""
    global _bytes
    # Lexical normalization avoids resolving every Windows ancestor for each preview.
    # Alias paths may have separate disposable entries; no access decision uses this key.
    path = Path(os.path.abspath(path))
    key = os.path.normcase(str(path))
    with _builders[hash(key) % len(_builders)]:
        for _ in range(2):
            try:
                before, annotations = file_stamp(path), _annotations(ad)
                cached = None
                with _lock:
                    entry = _values.get(key)
                    if (entry and entry[0]['stamp'] == before and entry[0]['annotations'] == annotations
                            and time.monotonic() - entry[0]['checked'] < MAX_AGE):
                        _values.move_to_end(key)
                        cached = entry[0]
                    elif entry:
                        _bytes -= _values.pop(key)[1]
                if cached is not None:
                    return project(cached)
                previous = entry[0] if entry else None
                index = _build(path, ad, previous, before, annotations)
                if before != file_stamp(path) or annotations != _annotations(ad):
                    continue
                index['checked'] = time.monotonic()
                # Offsets are compact; no prompt/output/transcript is retained in this cache.
                size = index['entries'] * 32 + len(repr({k: v for k, v in index.items() if k != 'offsets'}).encode('utf-8'))
                with _lock:
                    if size <= MAX_BYTES:
                        _values[key] = (index, size)
                        _bytes += size
                    while len(_values) > MAX_FILES or _bytes > MAX_BYTES:
                        _bytes -= _values.popitem(last=False)[1][1]
                return project(index)
            except _Changed:
                continue
            except (OSError, UnicodeError) as exc:
                index = _empty()
                index['errors'] = [f'{path.name}: cannot read history; totals are incomplete ({type(exc).__name__}).']
                return project(index)
        index = _empty()
        index['errors'] = [f'{path.name}: history changed while reading; totals are incomplete. Retry the view.']
        return project(index)


def totals(agent_dir, since):
    def project(index):
        days = [d for day, d in index['days'].items() if day >= since]
        cost = None if any(d['cost'] is None for d in days) else sum(d['cost'] for d in days)
        return (dict(index['latest']), sum(d['count'] for d in days),
                sum(d['tokens'] for d in days), cost, list(index['errors']))
    return _read(_path(agent_dir), agent_dir, project)


def usage(agent_dir=None, *, system_root=None):
    path = Path(system_root) / 'system_runs.jsonl' if system_root is not None else _path(agent_dir)
    return _read(path, agent_dir, lambda index: [dict(row, tokens=dict(row['tokens'])) for row in index['usage'].values()])


def legacy_stamp(agent_dir, thread):
    return _read(_path(agent_dir), agent_dir,
                 lambda index: (index['legacy_view'].get(thread, frozenset()), tuple(index['errors'])))


def recent(agent_dir, since):
    path = _path(agent_dir)
    def project(index):
        from .job_history import apply_annotation
        offsets = sorted(item for day, items in index['offsets'].items() if day >= since for item in items)
        if not offsets:
            return []
        # Recheck under the writer's lock before trusting offsets from another generation.
        with util.file_lock(path, validate_state=False):
            if file_stamp(path) != index['stamp'] or _annotations(agent_dir) != index['annotations']:
                raise _Changed()
            names = frozenset(name for name, _ in index['annotations'])
            result = []
            with path.open('rb') as source:
                for offset, length in offsets:
                    source.seek(offset)
                    rows, _ = records.history_lines(path, [source.read(length).decode('utf-8-sig' if offset == 0 else 'utf-8')])
                    result.extend(apply_annotation(agent_dir, row, names=names) for row in rows)
            return result
    return _read(path, agent_dir, project)
