# `armada/catalogue/realm.py`

What a realm owns: adding a catalogue entry to it, adopting what discovery already found there,
inspecting what a capability can reach, fetching a skill onto this machine, and the bring-a-link
review flow (ADR-004). Everything here writes into or reads out of a specific realm folder; the
mirrored/queried sources it matches against live in catalogue.sources.

Split out of catalogue.py (Phase 2, 2.4/2.9) — a pure move, no behaviour change. Imports from
.sources (load, search_registry, _marketplaces_dir) at module level — safe, since sources.py never
imports anything from here, so the dependency only runs one way.

### `_adopt_queries(cap: dict)`

Search strings to look a discovered capability up by, best first.

### `adopt(realm_root, entries: list | None=None, search: bool=True)`

Give discovered capabilities the catalogue's name and provenance where they are the same thing.

### `is_identified(cap: dict)`

Do we already KNOW what this realm capability is?

### `installed_keys(realm_roots, entries: list | None=None)`

{catalogue key: [realm name, ...]} — what is already in each of your realms.

### `realms_with_capability(name: str, url: str='')`

[{"name": realm name, "path": realm path}, ...] for every realm ARMADA knows about that already holds something matching this bring-a-link candidate.

### `_plugin_dir(e: dict)`

Where a marketplace plugin's files are, if they're on this machine.

### `inspect(e: dict)`

{runs, touch, inspected, detail} — what this capability can do.

### `_skills_archive()`

The repository zip as bytes, from memory if recent. None if it can't be had.

### `_extract_from_archive(data: bytes, path: str, dest: Path)`

Write `skills/<path>/…` out of the repository zip into `dest`. False if it isn't there or any member name could escape `dest` (every part must pass _safe_name).

### `_get_bytes(url: str)`

One HTTP GET returning raw bytes, or None. Never raises.

### `_safe_name(name: str)`

A filename from a remote listing, or "" if it could escape the folder we chose.

### `_download_tree(api_url: str, dest: Path, budget: list)`

Copy one GitHub directory to `dest`, recursively. False if anything was missed.

### `fetch_skill(e: dict, dest: Path)`

Bring an Anthropic skill onto this machine, into `dest`.

### `lookup_registry(cid: str)`

Fetch one registry server by name, normalised.

### `find(key: str)`

One entry by key — from the mirrored index, or fetched from the registry if it lives there.

### `add_to_realm(realm_root, key: str, entry: dict | None=None)`

Put a catalogue entry into this realm's capability list.

### `_extract_json(text: str)`

Find the first balanced {...} object in free text and parse it.

### `review_url(url: str, engine: str='claude', timeout: int=300)`

Ask an agent to run the capability-review protocol (system_skills/capability-review) against a link, and come back with a report the owner can read before deciding to add it.

### `add_link_to_realm(realm_root, url: str, review: dict)`

Record a bring-a-link capability the owner has read the review for and chosen to add.
