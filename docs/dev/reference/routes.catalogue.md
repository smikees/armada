# `armada/routes/catalogue.py`

The Catalogue tab: search results, refresh, reveal, add, and the bring-a-link review
flow (ADR-004).

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.

### class `CatalogueRoutes`

—

- `CatalogueRoutes._get_capabilities_content(self)` — —
- `CatalogueRoutes._capability_review_start(self, body)` — —
- `CatalogueRoutes._get_capability_reviews(self)` — —
- `CatalogueRoutes._get_catalogue(self)` — Re-render the Catalogue's results area for one set of filters.
- `CatalogueRoutes._catalogue_refresh(self, body: dict)` — Re-read the mirrored sources now, rather than waiting for the daily job.
- `CatalogueRoutes._catalogue_reveal(self, body: dict)` — Open the file manager at a skill the owner wrote, from its catalogue card.
- `CatalogueRoutes._catalogue_add(self, body: dict)` — —
- `CatalogueRoutes._catalogue_review(self, body: dict)` — —
- `CatalogueRoutes._render_capability_review(self, result, url)` — —
- `CatalogueRoutes._catalogue_add_link(self, body: dict)` — —
- `CatalogueRoutes._smart_search(self, body: dict)` — —
- `CatalogueRoutes._get_smart_search(self)` — —
- `CatalogueRoutes._smart_search_check(self, body: dict)` — Review a catalogue entry already on this computer (one of your skills) by its files.
- `CatalogueRoutes._smart_search_warm(self, body: dict)` — —
- `CatalogueRoutes._smart_search_add(self, body: dict)` — Add a ChatGPT plugin found by smart search as its own Codex row.

### `_looks_like_mcp(url: str)`

An address a service publishes for its MCP server, rather than a page or a repository.

### `_add_mcp_address(realm_root, url: str, review: dict)`

—
