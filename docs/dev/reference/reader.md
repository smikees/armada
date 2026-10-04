# `armada/reader.py`

Realm readers for the native schema and legacy schedule-folder imports.

Missing or unsupported legacy fields are reported as gaps rather than silently inferred.

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

Resolve template labels and compatibility overrides for existing realms.

### `read_native(root: Path)`

Read a ARMADA-native realm (realm.json + theme.json + agents/*) — the greenfield format.

### `order_agents(realm: Realm)`

Coordinators first, then everyone else; alphabetical by display name within each group.

### `read(root: str | Path)`

—
