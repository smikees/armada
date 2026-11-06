# `armada/run_summary.py`

Disposable presentation summaries and date indexes; never execution or policy evidence.

Canonical JSONL stays authoritative. Warm reads use file identities; growth is incremental
only after hashing the complete old prefix. Edits, truncation, replacement, annotations
and a 30-second revalidation interval cause a rebuild. Indexes are never persisted;
reads may create the existing protocol's sibling lock file.

### class `_Changed`

A projection observed another source generation; retry with fresh offsets.


### `_path(agent_dir)`

—

### `_annotations(ad)`

—

### `_empty()`

—

### `_add(index, row, offset, length)`

—

### `_build(path, ad, previous, before, annotations)`

—

### `_read(path, ad, project)`

Project under a bounded per-key lock; callers never receive mutable index internals.

### `totals(agent_dir, since)`

—

### `usage(agent_dir=None, *, system_root=None)`

—

### `legacy_stamp(agent_dir, thread)`

—

### `recent(agent_dir, since)`

—
