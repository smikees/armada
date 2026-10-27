"""Bounded, disposable presentation caches. Never used for authorization or execution."""
from collections import OrderedDict
from pathlib import Path
import threading
import time


def file_stamp(path):
    try:
        s = Path(path).stat()
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    except FileNotFoundError:
        return None


def history_stamp(thread, *, progress=False):
    """Observe appends, replacements and interrupted transactions across processes."""
    paths = [thread.msgs, thread.summary_f, thread.dir / '.history-revision',
             thread.dir.parent.parent / 'runs' / (thread.dir.parent.parent.name + '.jsonl')]
    if progress and thread.dir.is_dir():
        paths.extend(sorted(thread.dir.glob('.progress-*.json')))
    # A pending transaction must go through HistoryStore recovery, never a cached view.
    if (thread.dir / '.history-transaction.json').exists():
        return object()
    return tuple((str(p), file_stamp(p)) for p in paths)


class ViewCache:
    def __init__(self, limit=128, bytes_limit=8 * 1024 * 1024):
        self.limit, self.bytes_limit = limit, bytes_limit
        self.lock = threading.Lock()
        self.values = OrderedDict()
        self.bytes = 0

    def read(self, key, stamp, build):
        before = stamp()
        now = time.monotonic()
        with self.lock:
            cached = self.values.get(key)
            if cached and cached[0] == before and now - cached[1] < 30:
                self.values.move_to_end(key)
                return cached[2]
        value = build()
        # Do not retain a render assembled while its source was being changed.
        if before != stamp():
            return value
        size = len(repr(value).encode('utf-8'))
        with self.lock:
            old = self.values.pop(key, None)
            if old:
                self.bytes -= old[3]
            if size <= self.bytes_limit:
                self.values[key] = (before, now, value, size)
                self.bytes += size
            while len(self.values) > self.limit or self.bytes > self.bytes_limit:
                self.bytes -= self.values.popitem(last=False)[1][3]
        return value
