"""Short-lived presentation fragments; never an authority for permissions or writes."""
from collections import OrderedDict
from pathlib import Path
import os
import threading
import time

TTL = 30
MAX_ENTRIES = 8
MAX_CHARS = 16 * 1024 * 1024
_lock = threading.Lock()
_entries = OrderedDict()
_generation = 0


def _key(root, page):
    return os.path.normcase(str(Path(root).resolve())), page


def get(root, page):
    key = _key(root, page)
    with _lock:
        item = _entries.get(key)
        if item and time.monotonic() - item[0] < TTL:
            _entries.move_to_end(key)
            return item[1]
        _entries.pop(key, None)
    return None


def render(root, page, build):
    with _lock:
        generation = _generation
    cached = get(root, page)
    if cached is not None:
        return cached
    body = build()
    with _lock:
        # A mutation during rendering must not repopulate the cache with old data.
        if generation == _generation and len(body) <= MAX_CHARS:
            _entries[_key(root, page)] = (time.monotonic(), body)
            while len(_entries) > MAX_ENTRIES or sum(len(v[1]) for v in _entries.values()) > MAX_CHARS:
                _entries.popitem(last=False)
    return body


def invalidate():
    """App writes may affect account-wide capabilities as well as the selected realm."""
    global _generation
    with _lock:
        _generation += 1
        _entries.clear()
