"""Bounded background refreshes of owner-configured section snapshots."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import glob
import hashlib
import json
import logging
from pathlib import Path
import threading
import time
import urllib.request
import uuid

from . import util

log = logging.getLogger(__name__)
MAX_BYTES = 8 * 1024 * 1024
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='section-snapshot')
_slots = threading.BoundedSemaphore(8)
_lock = threading.Lock()
_jobs = OrderedDict()


def _destination(root, section):
    from .routes.dashboard import _section_path
    return _section_path(root, section.get('snapshot'))


def _newest(pattern):
    if not isinstance(pattern, str) or not pattern:
        return None
    candidates = glob.iglob(pattern) if any(c in pattern for c in '*?[') else [pattern]
    latest = None
    for name in candidates:
        path = Path(name)
        if path.is_file() and (latest is None or path.stat().st_mtime > latest.stat().st_mtime):
            latest = path
    return latest


def _local(path):
    with path.open('rb') as source:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Snapshot exceeds the 8 MiB limit.')
    return data.decode('utf-8-sig', 'replace')


def refresh(root, section, *, force=False, index=None):
    """Read the source off the render path; validate current configuration before atomic commit."""
    root = Path(root)
    dest = _destination(root, section)
    source = section.get('source')
    if not isinstance(source, str) or not source:
        raise ValueError('No snapshot source is configured.')
    if source.lower().startswith(('http://', 'https://')):
        if not force and dest.is_file():
            return {'changed': False}
        deadline, chunks, size = time.monotonic() + 20, [], 0
        request = urllib.request.Request(source, headers={'User-Agent': 'ARMADA/1.0'})
        with urllib.request.urlopen(request, timeout=5) as response:
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError('Snapshot source took too long.')
                chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('Snapshot exceeds the 8 MiB limit.')
        content = b''.join(chunks).decode('utf-8', 'replace')
    else:
        path = _newest(source)
        if path is None:
            raise ValueError('Snapshot source is unavailable.')
        if not force and dest.is_file() and path.stat().st_mtime <= dest.stat().st_mtime:
            return {'changed': False}
        content = _local(path)
    if '<html' not in content.lower():
        css_path = _newest(section.get('css'))
        css = _local(css_path) if css_path else ''
        content = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                   '<meta name="viewport" content="width=device-width, initial-scale=1">'
                   + (f'<style>{css}</style>' if css else '') + '</head><body>' + content + '</body></html>')
    if len(content.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Snapshot exceeds the 8 MiB limit.')
    with util.file_lock(root / 'realm.json'):
        if index is not None:
            sections = util.read_json_state(root / 'realm.json').get('sections', [])
            if index >= len(sections) or sections[index] != section:
                raise ValueError('Section changed during refresh. Reload the page and try again.')
        with util.file_lock(dest):
            if _destination(root, section) != dest:
                raise ValueError('Snapshot destination changed during refresh.')
            util.write_text_atomic(dest, content)
    return {'changed': True}


def request(root, index, *, force=False, ticket=''):
    """Coalesce per-section work; at most two workers and eight admitted refreshes."""
    root = Path(root).resolve()
    sections = util.read_json_state(root / 'realm.json').get('sections', [])
    if index < 0 or index >= len(sections) or not isinstance(sections[index], dict):
        raise ValueError('This section is no longer available.')
    section = sections[index]
    _destination(root, section)
    fingerprint = hashlib.sha256(json.dumps(section, sort_keys=True).encode()).hexdigest()
    key = (str(root), index, fingerprint)
    with _lock:
        old = _jobs.get(key)
        if ticket:
            if not old or old['ticket'] != ticket:
                return {'ok': False, 'error': 'Refresh expired or section changed. Try again.'}
            return dict(old)
        if old and old['pending']:
            return dict(old)
        if not _slots.acquire(blocking=False):
            return {'ok': False, 'error': 'Other sections are refreshing. Try again shortly.'}
        state = {'ok': True, 'pending': True, 'ticket': uuid.uuid4().hex}
        _jobs[key] = state
        _jobs.move_to_end(key)
        for stale in list(_jobs):
            if len(_jobs) <= 64:
                break
            if not _jobs[stale]['pending']:
                del _jobs[stale]

        def work():
            try:
                answer = dict(ok=True, **refresh(root, section, force=force, index=index))
            except Exception:
                log.warning('Section snapshot refresh failed; preserving the existing copy', exc_info=True)
                answer = {'ok': False, 'error': 'Could not refresh the local copy. Check its source and try again.'}
            finally:
                _slots.release()
            with _lock:
                state.update(answer, pending=False)
        try:
            _pool.submit(work)
        except RuntimeError:
            _slots.release()
            state.update(ok=False, pending=False, error='Refresh service is stopping. Try again after restart.')
        return dict(state)
