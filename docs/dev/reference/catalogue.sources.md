# `armada/catalogue/sources.py`

The catalogue's three mirrored/queried sources — Claude plugin marketplaces, the MCP registry,
anthropics/skills, and the skills you wrote yourself — normalised into one record shape, indexed,
and searched. Nothing here writes to a realm; that is catalogue.realm.

Split out of catalogue.py (Phase 2, 2.4/2.9) — a pure move, no behaviour change.

### `_marketplaces_dir()`

—

### `from_marketplaces()`

(entries, note, answered). Every plugin listed by every marketplace the CLI has cloned.

### `_registry_kind(srv: dict)`

Connector or Extension — the same rule capscan uses, so a thing doesn't change bucket between the catalogue and the realm it lands in: a URL runs somewhere else, a package runs here.

### `_registry_entry(srv: dict)`

—

### `search_registry(q: str, limit: int=_REGISTRY_LIMIT, sample: bool=False)`

(entries, note) for a live search of the MCP registry.

### `registry_wanted(q: str, source: str, kind: str)`

Should this set of filters reach the live registry?

### `from_skills()`

(entries, note, answered). Anthropic's public Agent Skills, one per folder.

### `_skill_roots()`

Every folder a skill you wrote could be sitting in, with the realm it belongs to.

### `_imported_skill_ids()`

Skills sitting in a realm that the realm got from somewhere else.

### `read_provenance(skill_dir)`

{origin, source, by, at, why} for a skill folder, or {} if nothing was recorded.

### `_match_known(name: str, desc: str, entries: list)`

The mirrored catalogue entry this local folder appears to BE, or None.

### `from_mine(known: list | None=None)`

(entries, note, answered, labels). Skills sitting on this machine, split by where they came from: ones you wrote (source "You") and ones that arrived from elsewhere ("Installed by an agent").

### `_fetcher_key(source: str)`

Which fetcher owns a source id. Marketplace ids carry the marketplace name after a colon, so they all belong to the one fetcher that reads the clones.

### `_fetcher_for(source: str)`

—

### `load()`

The stored index, or an empty one. Never raises.

### `refresh(only: str='')`

Re-fetch the sources and write the index. Returns a per-source report.

### `age_hours()`

How old the index is, in hours. -1 when it has never been fetched.

### `facets(entries: list)`

Which filter values actually exist in a given set of entries.

### `search(entries: list, q: str='', source: str='', kind: str='', author: str='', category: str='')`

Filter the index. Plain substring matching on name + description — the index is a few thousand short records held in memory, so anything cleverer would be cost without benefit.

### `count_registry()`

(count, capped) — latest-version servers in the registry, or (-1, False) if unreachable.

### `refresh_registry_count()`

Count the registry and remember the answer on the index. Best-effort, never raises.

### `_refresh_registry_count()`

—

### `registry_count_label(idx: dict | None=None)`

'12,345' or '25,000+' — or '' before the first count, because a guess is not a count.
