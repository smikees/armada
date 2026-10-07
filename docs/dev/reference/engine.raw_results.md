# `armada/engine/raw_results.py`

Keep a CLI JSON value's original spelling across normalized display events.

### class `SourceEvent`

A parsed event carrying its original UTF-8 JSON line, for capture only.

- `SourceEvent.__init__(self, data, source)` — —

### `loads_event(line)`

—

### `result_source(event, path)`

—

### `payload(source)`

Extract a JSON token verbatim; unwrap strings exactly once, without trimming.
