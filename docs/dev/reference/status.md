# `armada/status.py`

Canonical run-status vocabulary — one place that knows the statuses a job/run can be in, how to
normalise the many raw spellings into them, and their colours. Imported by reader/webui so status
handling isn't re-derived (and allowed to drift) in each module.

### `normalize(raw)`

Map a raw status string to its canonical form ('' if unrecognised/empty).

### `is_bad(raw)`

True for statuses that should draw attention (a warning or an outright failure).

### `color(raw)`

CSS colour for a raw status (idle grey when unknown).
