# `armada/catalogue/__init__.py`

The capability catalogue — everything you could add, from every source we know about.

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
