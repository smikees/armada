# `armada/model.py`

ARMADA domain model (neutral ontology).

The realm is the files; these dataclasses are the in-memory view a reader
produces and a renderer consumes. Nothing here is engine- or theme-specific.

### `context_window_tokens(model_label: str)`

—

### `compaction_threshold_chars(model_label: str)`

Char budget for a thread's history before ARMADA compacts it — derived from the model's real context window, not an arbitrary constant.

### class `Skill`

A capability enabled for an agent — pinned by source+version, gated by permission scopes. SPEC §6: scopes are drawn from files | network | connectors | shell.

- `Skill.ref(self)` — —

### class `Job`

—


### class `Agent`

—


### class `Gap`

—


### class `Realm`

—

- `Realm.coordinator(self)` — —
- `Realm.members(self)` — —
- `Realm.tokens_30d(self)` — —
- `Realm.cost_30d(self)` — —
