# `armada/catalogue/_shared.py`

Constants and cross-cutting matching/identity helpers shared by both catalogue.sources and
catalogue.realm — every source label, the file-storage paths, the generic HTTP-JSON fetch, and the
name/id matching (_tokens/_same_capability*) that both "is this already in the mirrored index" and
"is this already in the realm" checks are built from.

Split out of catalogue.py (Phase 2, 2.4/2.9) — a pure move, no behaviour change. This is the base
layer: it imports nothing from .sources or .realm at module level (one exception, source_label's
own call to sources.load(), is a local import to avoid a cycle — sources.py needs the constants
and helpers defined here, so the dependency can only run one way at module scope).

### `marketplace_source(name: str)`

—

### `is_marketplace(source: str)`

—

### `source_label(source: str, labels: dict | None=None)`

The human name for a source id, including per-marketplace ones.

### `_dir()`

—

### `_index_path()`

—

### `_now()`

—

### `_get_json(url: str)`

One HTTP GET returning parsed JSON, or None. Never raises.

### `_entry(source: str, kind: str, cid: str, name: str, description: str='', *, author: str='', category: str='', homepage: str='', curated: str='', install: dict | None=None, version: str='')`

One catalogue record. `key` is what the UI and the realm both refer to it by.

### `_known_realms()`

Realm folders from ARMADA's own registry. Read directly rather than through serve, which would drag the whole web layer into a module the daily job imports.

### `_norm_id(s)`

—

### `_tokens(e: dict)`

The forms of a capability's identity worth matching on.

### `_same_capability(cat_tokens: set, realm_tokens: set)`

Do these name the same thing? Exact on any token, else containment above a length floor.

### `_looks_like_id(s: str)`

A reverse-DNS or slug-shaped string, as opposed to something written for a reader.

### `_same_capability_exact(cat_tokens: set, realm_tokens: set)`

Same thing, on a name both sides actually share — no containment.

### `_command_matches(cap: dict, entry: dict)`

Does the command this server actually runs match what the catalogue entry declares?

### `_url_host(s: str)`

—
