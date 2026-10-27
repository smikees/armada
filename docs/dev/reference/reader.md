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

### `read_native(root: Path, *, details=True)`

Read a ARMADA-native realm (realm.json + theme.json + agents/*) — the greenfield format.

### `order_agents(realm: Realm)`

Coordinators first, then everyone else; alphabetical by display name within each group.

### `name(root: str | Path)`

Startup registration needs metadata, not historical usage or job outcomes.

### `roster(root: str | Path)`

Current identities/configuration only; never use this for usage or job summaries.

### `read(root: str | Path)`

—
