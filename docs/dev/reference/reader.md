# `armada/reader.py`

ARMADA realm reader — adopts a realm folder into the model.

v0.1 speaks two dialects:
  * ARMADA-native (the neutral schema in SPEC.md §4) — future.
  * The reference cabinet (D:\Work\Hand) — the brownfield test fixture: it maps
    schedule.json + <minister>.md bulletins + runs/*.jsonl into the ARMADA model.

Reading a realth this way is exactly the "Adopt an existing setup" path from the
setup flow, and it doubles as a schema-validation exercise: whatever the cabinet
does NOT yet declare (skills, token usage) surfaces as a Gap, not a silent blank.

### `_read(p: Path)`

—

### `_frontmatter(text: str)`

—

### `_first_headline(body: str, limit: int=220)`

—

### `is_cabinet(root: Path)`

—

### `read_cabinet(root: Path)`

—

### `_resolve_theme(cfg: dict, theme: dict)`

Coordinator / agent / collective display labels for a realm.

### `read_native(root: Path)`

Read a ARMADA-native realm (realm.json + theme.json + agents/*) — the greenfield format.

### `order_agents(realm: Realm)`

Coordinators first, then everyone else; alphabetical by display name within each group.

### `read(root: str | Path)`

—
