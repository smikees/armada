"""Independent, bounded subscription checks; HTTP requests never wait on a CLI."""
from __future__ import annotations
import logging

import copy
import threading
import time
from dataclasses import dataclass, field

from . import providers

TTL = 300.0
DEADLINE = 55.0
_lock = threading.RLock()
_entries: dict[tuple, '_Entry'] = {}


@dataclass
class _Entry:
    started: float
    finished: float | None = None
    data: dict = field(default_factory=dict)
    good: dict = field(default_factory=dict)
    good_at: float = 0.0
    worker: threading.Thread | None = None


def _probe(provider, realm):
    if provider == 'claude':
        from . import usage_api
        return usage_api.fetch(realm)
    if provider == 'codex':
        from . import codex_usage
        return codex_usage.fetch()
    from .engine.gemini import GeminiEngine
    return GeminiEngine().usage_limits()


def _failure(entry, reason, message, now):
    data = {'available': False, 'reason': reason, 'message': message}
    if entry.good:
        data.update(copy.deepcopy(entry.good))
        data.update(stale=True, age_sec=max(0, int(now-entry.good_at)), reason=reason, message=message)
    entry.data, entry.finished = data, now


def _run(key, entry, provider, realm):
    try:
        data = _probe(provider, realm)
        if not isinstance(data, dict) or not isinstance(data.get('available'), bool):
            raise ValueError('The provider returned malformed usage data.')
    except Exception as exc:
        logging.getLogger(__name__).exception('Provider usage check failed')
        data = {'available': False, 'reason': 'error', 'message': str(exc)[:200] or 'Usage check failed.'}
    with _lock:
        now = time.monotonic()
        # A timed-out generation can never replace its recorded failure or a later reading.
        if _entries.get(key) is not entry or entry.finished is not None:
            return
        if now-entry.started >= DEADLINE:
            _failure(entry, 'timeout', 'Usage check timed out. The next check will retry.', now)
        elif data['available'] and not data.get('stale'):
            entry.data = copy.deepcopy(data)
            entry.good, entry.good_at, entry.finished = copy.deepcopy(data), now, now
        else:
            _failure(entry, data.get('reason', 'unavailable'), data.get('message') or data.get('detail') or 'Usage is unavailable.', now)
            if data.get('stale') and not entry.good:
                entry.data = data


def read(provider: str, realm=None, force: bool = False) -> dict:
    """Return a cached reading or pending state, without blocking other provider checks."""
    if provider not in providers.NAMES:
        raise ValueError('Unknown provider')
    connected = provider in providers.connected()
    if not providers.allowed(provider):
        return {'available': False, 'connected': False, 'reason': 'disconnected', 'message': 'Disconnected from Armada.'}
    key = (provider, str(getattr(realm, 'root', realm)) if provider == 'claude' else '')
    with _lock:
        now = time.monotonic()
        entry = _entries.get(key)
        if entry and entry.finished is None and now-entry.started >= DEADLINE:
            _failure(entry, 'timeout', 'Usage check timed out. The next check will retry.', now)
        busy = bool(entry and entry.worker and entry.worker.is_alive())
        if not entry or (entry.finished is not None and (force or now-entry.finished >= TTL) and not busy):
            old = entry
            entry = _Entry(now, good=copy.deepcopy(old.good) if old else {}, good_at=old.good_at if old else 0)
            _entries[key] = entry
            entry.worker = threading.Thread(target=_run, args=(key, entry, provider, realm), daemon=True)
            entry.worker.start()
        if entry.finished is None:
            data = copy.deepcopy(entry.good) or {'available': False, 'loading': True}
            data['pending'] = True
        else:
            data = copy.deepcopy(entry.data)
        data['connected'] = connected or bool(data.get('available') and not data.get('stale'))
        return data
