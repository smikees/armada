"""Durable, realm-scoped reviews. Navigation never owns a review's lifetime.

Only a verified source fingerprint can reuse a report. Restoring a report does not
run the reviewer; explicitly reviewing again verifies the version first.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from . import catalogue, sysskills, util

_lock = threading.RLock()
_active: set[tuple[str, str]] = set()
log = logging.getLogger(__name__)


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _directory(root):
    return util.data_dir() / 'capability-reviews' / _hash(os.path.normcase(str(Path(root).resolve())))


def github_repo(url):
    """Recognize a repository link, never a lookalike host or arbitrary search prose."""
    try:
        p = urlsplit(url)
        parts = p.path.strip('/').split('/')
        return (p.scheme in ('http', 'https') and p.netloc.lower() == 'github.com'
                and len(parts) >= 2 and all(re.fullmatch(r'[\w.-]+', s) for s in parts[:2])
                and (len(parts) == 2 or (len(parts) >= 4 and parts[2] in ('tree', 'blob'))))
    except ValueError:
        return False


def _version(url, key):
    if not url and key:
        entry = catalogue.find(key)
        if not entry:
            raise ValueError('That skill is no longer in the catalogue.')
        folder = Path(str((entry.get('install') or {}).get('path') or ''))
        if folder.is_symlink() or (hasattr(folder, 'is_junction') and folder.is_junction()):
            return '', url
        if not (folder / 'SKILL.md').is_file():
            raise ValueError('That skill is no longer on this computer.')
        digest = hashlib.sha256(json.dumps(entry, sort_keys=True).encode())
        total = 0
        for path in sorted(folder.rglob('*')):
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                return '', url
            if path.is_file():
                total += path.stat().st_size
                if total > 20 * 1024 * 1024:
                    return '', url
                digest.update(path.relative_to(folder).as_posix().encode())
                digest.update(b'\0' + path.read_bytes() + b'\0')
        return digest.hexdigest(), url
    if not github_repo(url):
        return '', url
    parts = urlsplit(url).path.strip('/').split('/')
    owner, repo = parts[:2]
    repo = repo.removesuffix('.git')
    if len(parts) > 12:
        return '', url
    # Try the longest ref first, so a branch named feature/review cannot be
    # mistaken for a folder on a branch named feature. Pin the exact commit read.
    refs = [(3, 'HEAD')] if len(parts) == 2 else [
        (end, '/'.join(parts[3:end])) for end in range(len(parts), 3, -1)]
    try:
        for end, ref in refs:
            api = f'https://api.github.com/repos/{quote(owner)}/{quote(repo)}/commits/{quote(ref, safe="")}'
            try:
                with urlopen(Request(api, headers={'User-Agent': 'ARMADA', 'Accept': 'application/vnd.github+json'}), timeout=8) as response:
                    sha = json.load(response).get('sha', '')
            except HTTPError as exc:
                if exc.code in (404, 422):
                    continue
                raise
            if not re.fullmatch(r'[a-fA-F0-9]{40}', sha):
                return '', url
            suffix = '/'.join(parts[end:]) if len(parts) > 2 else ''
            pinned = f'https://github.com/{owner}/{repo}/{parts[2] if len(parts)>2 else "tree"}/{sha}'
            return sha, pinned + ('/' + suffix if suffix else '')
    except (OSError, ValueError):
        pass
    return '', url


def local_review(key):
    entry = catalogue.find(key)
    if not entry:
        return {'ok': False, 'error': 'That skill is no longer in the catalogue.'}
    look = catalogue.inspect(entry)
    detail = str(look.get('detail') or '')
    return {'ok': True, 'name': entry.get('name') or entry.get('id'),
            'kind': entry.get('kind') or 'skills', 'publisher': entry.get('author') or '',
            'runs': look.get('runs') or '', 'touch': look.get('touch') or [], 'risk': '',
            'recommendation': 'Checked from its local files. ' + detail,
            'summary': detail, 'warn': '', 'confidence': 'files read locally'}


def start(root, url='', key=''):
    url, key = str(url).strip(), str(key).strip()
    if url:
        p = urlsplit(url)
        if p.scheme not in ('http', 'https') or not p.netloc or p.username or p.password:
            raise ValueError('Paste an http or https link without credentials.')
    elif not key:
        raise ValueError('Paste a link first.')
    if len(url) > 4096 or len(key) > 512:
        raise ValueError('That link is too long.')
    root = Path(root).resolve()
    directory = _directory(root)
    rid = _hash(url + '\n' + key)[:24]
    task = (str(directory), rid)
    with _lock:
        if task in _active:
            return rid
        if sum(t[0] == task[0] for t in _active) >= 3:
            raise ValueError('Three reviews are already running. Wait for one to finish.')
        directory.mkdir(parents=True, exist_ok=True)
        row = dict(id=rid, url=url, key=key, state='running', stage='Checking version…',
                   updated=time.time(), started=time.time(), result=None, cached=False, revision='')
        util.write_json_atomic(directory / (rid + '.json'), row)
        _active.add(task)
        threading.Thread(target=_run, args=(directory, row, task), daemon=True).start()
    return rid


def _run(directory, row, task):
    path = directory / (row['id'] + '.json')
    try:
        revision, target = _version(row['url'], row['key'])
        policy = json.dumps(sysskills.get_system_skill('capability-review') or {}, sort_keys=True)
        cache_id = _hash('v1\n' + row['id'] + '\n' + revision + '\n' + policy)
        cached = directory / 'cache' / (cache_id + '.json')
        result = None
        if revision and cached.is_file():
            try:
                result = json.loads(cached.read_text(encoding='utf-8'))
                row['cached'] = bool(result.get('ok'))
            except (ValueError, OSError):
                result = None
        if not result or not result.get('ok'):
            row['stage'] = 'Reading capability…'
            util.write_json_atomic(path, row)
            result = catalogue.review_url(target) if row['url'] else local_review(row['key'])
            if not row['url'] and revision != _version('', row['key'])[0]:
                result = {'ok': False, 'error': 'The skill changed during review. Review it again.'}
            if revision and result.get('ok'):
                cached.parent.mkdir(parents=True, exist_ok=True)
                util.write_json_atomic(cached, result)
        row.update(result=result, revision=revision, state='done' if result.get('ok') else 'error',
                   stage='Review ready' if result.get('ok') else 'Review failed', updated=time.time())
    except Exception:
        log.exception('Capability review failed')
        row.update(state='error', stage='Review failed', updated=time.time(),
                   result={'ok': False, 'error': 'The review could not finish. Please try again.'})
    finally:
        try:
            util.write_json_atomic(path, row)
        finally:
            with _lock:
                _active.discard(task)


def recent(root):
    directory = _directory(root)
    rows = []
    with _lock:
        for path in directory.glob('*.json'):
            try:
                row = json.loads(path.read_text(encoding='utf-8'))
                if row['state'] == 'running' and (str(directory), row['id']) not in _active:
                    row.update(state='error', stage='Review interrupted',
                               result={'ok': False, 'error': 'ARMADA closed before this review finished. Retry when ready.'})
                rows.append(row)
            except (ValueError, OSError, KeyError):
                continue
    return sorted(rows, key=lambda r: r.get('started', 0), reverse=True)[:20]
