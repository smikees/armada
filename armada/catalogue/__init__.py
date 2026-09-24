"""The capability catalogue — everything you could add, from every source we know about.

Three sources, one record shape, one file on disk:

* **Claude plugin marketplaces** — every marketplace the CLI has configured, read from its own
  local clone (`~/.claude/plugins/marketplaces/*/.claude-plugin/marketplace.json`). Anthropic's
  `claude-plugins-official` is there by default; anything the owner adds appears too, for free.
* **The official MCP registry** — `registry.modelcontextprotocol.io`, an open index anyone can
  publish to. That difference is carried on every record as `curated`, because "listed in
  Anthropic's directory" and "self-published to an open registry" are not the same claim. This
  one is **searched live, not mirrored**: it holds tens of thousands of servers and grows, which
  is not a thing anyone browses and not a thing worth copying onto this machine every night. You
  can't scroll your way to the right one out of tens of thousands; you can search for it.
* **`anthropics/skills`** — Anthropic's public Agent Skills repository.

Why normalise at all, when only two sources are mirrored: because all three arrive in different
shapes and the page shouldn't care. The marketplace is a local file with categories and authors;
the registry is an HTTP API with neither; the skills repo is a directory listing. One record shape
means the browse list, the filters and the add button are written once. The mirrored pair is
refreshed daily into a flat file, so browsing is a local read that works offline; the registry
joins the results only when you type something, and says so when it can't be reached.

It lives at `~/.armada/catalogue/`, beside the app root and the theme, because the catalogue is a
property of this computer and not of any realm — every realm would otherwise keep its own copy,
going stale independently. What a realm owns is which entries it has chosen to ADD; see
`armada.capabilities` for that.

Everything here is best-effort and never raises: a source that fails keeps its last good data,
with its own timestamp, and the others carry on. A catalogue that can't refresh is out of date,
which is a thing we can say on screen. A catalogue that throws takes the Capabilities page down.

A package since Phase 2 (2.4/2.9) — was one 1,578-line module, now three, by concern:

* `_shared.py` — constants, source labels, file storage paths, the generic HTTP-JSON fetch, and
  the name/id matching (`_tokens`/`_same_capability*`) both other files are built from.
* `sources.py` — the fetch/search side: the three mirrored/queried sources, the daily index, and
  search/facets over it. Nothing here writes to a realm.
* `realm.py` — the realm-writing side: `add_to_realm`, `adopt`, provenance/inspection, fetching a
  skill onto this machine, and the bring-a-link review flow (ADR-004). Everything here reads from
  or writes into a specific realm folder.

This file re-exports every public and private name the three used to share one namespace for, so
every existing `from . import catalogue as cat; cat.whatever(...)` call — inside this codebase and
in tests — keeps resolving exactly where it always did. A test that monkeypatches one of these
names to sandbox a realm folder or keep the network out during a test run must patch the actual
submodule the code calls it from (`_shared`, `sources`, or `realm`), not this re-export — the same
rule 2.3 established for `armada.routes._shared._reg_path`: a function's globals are fixed at its
own definition site, not at whatever re-imports its name afterwards.
"""
from __future__ import annotations

from ._shared import (
    MARKETPLACE, REGISTRY, SKILLS, MINE, INSTALLED, SOURCE_LABEL, _MARKETPLACE_NAMES,
    marketplace_source, is_marketplace, source_label, CURATED_OFFICIAL,
    CURATED_REGISTRY, _REGISTRY_URL, _SKILLS_API, _UA, _REGISTRY_LIMIT, _TIMEOUT,
    _REG_TTL, _dir, _index_path, _now, _get_json, _entry, _known_realms, _norm_id,
    _MATCH_MIN, _tokens, _same_capability, _looks_like_id, _same_capability_exact,
    _command_matches, _url_host, PROVENANCE_FILE, ORIGIN_AUTHORED, ORIGIN_INSTALLED,
    _reg_cache,
)
from .sources import (
    _marketplaces_dir, from_marketplaces, _registry_kind, _registry_entry,
    search_registry, REGISTRY_ONLY_KINDS, registry_wanted, from_skills, _skill_roots,
    _imported_skill_ids, read_provenance, _match_known, from_mine, _FETCHERS,
    _fetcher_key, _fetcher_for, load, refresh, age_hours, facets, search, _COUNT_PAGE,
    _COUNT_MAX_PAGES, _COUNT_PACE, _COUNT_RETRIES, _COUNT_BACKOFF, count_registry,
    _counting, refresh_registry_count, _refresh_registry_count, registry_count_label,
)
from .realm import (
    _adopt_queries, _ADOPT_FIELDS, adopt, is_identified, installed_keys,
    realms_with_capability, _plugin_dir, inspect, _SKILLS_REPO_API, _FETCH_MAX_FILES,
    _get_bytes, _NAME_RE, _safe_name, _download_tree, fetch_skill, lookup_registry,
    find, add_to_realm, _REVIEW_JSON_SHAPE, _RISK_TIER, _extract_json, review_url,
    add_link_to_realm,
)
