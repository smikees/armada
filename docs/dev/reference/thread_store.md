# `armada/thread_store.py`

Recoverable thread history mutations, serialized on the existing messages-file lock.

A prepared journal is the commit decision. Every participating read/write finishes it before
touching history, so a process crash between summary and log replacement cannot mix generations.
The model call is deliberately outside this module and outside the lock.

### class `CompactionConflict`

History was rewritten while a summary was being generated; retry from a fresh snapshot.


### `entries(raw: str, *, strict=True)`

Keep original lines for rewriting; tolerant display never becomes compaction input.

### class `HistorySnapshot`

—


### class `HistoryStore`

—

- `HistoryStore.__init__(self, directory)` — —
- `HistoryStore._read(path)` — —
- `HistoryStore._current(self)` — —
- `HistoryStore._checksum(payload)` — —
- `HistoryStore._recover(self)` — Roll forward only recognized before/after states, while the messages lock is held.
- `HistoryStore.read(self)` — Read one coherent summary/log generation, recovering an interrupted commit first.
- `HistoryStore.append(self, records)` — —
- `HistoryStore._commit(self, before, messages, summary, operation)` — —
- `HistoryStore.compact(self, snapshot, kept, summary)` — Commit only an unchanged prefix/revision; append-only tail growth is always retained.
- `HistoryStore.truncate(self, keep)` — Owner-requested truncation shares the compaction lock and advances its revision.
