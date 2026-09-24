# `armada/webui/catalogue.py`

Catalogue tab rendering: search results, filters, the bring-a-link review report, and the
info box (ADR-004) — everything that renders from CATALOGUE/registry data rather than the realm's
own toolkit.

Split out of capabilities.py (Phase 2, 2.4) — a pure move, no behaviour change. capabilities.py
keeps the User tab, System tab, and the cross-cutting trust-model helpers every capability card
(there or here) is built from; this module imports the few of those it needs
(_KIND_SINGULAR, _cap_iconcluster, _cap_tier_why). _realm_skills, the page that stitches User +
System + this tab together, stays in capabilities.py and imports _catalogue_pane/_CAT_JS from here
locally — the same way this module already reached back into armada.catalogue (the data layer)
before the split, avoiding a module-level import cycle between the two.

### `_cat_pill(text: str, col: str='var(--text-muted)')`

—

### `_cat_card(e: dict, publisher: str, where: list, labels: dict, here: bool=False)`

One catalogue entry.

### `_cat_results(realm, realm_root, q: str='', source: str='', kind: str='', author: str='', category: str='', page: int=0)`

The results area — re-rendered on its own whenever a filter changes.

### `_cat_empty_options(entries: list, reg_all: list, *, q='', source='', kind='', author='', category='')`

({facet: [values that would return nothing]}, [facets with nothing left to offer]).

### `_cat_installed(realm_root, entries: list | None=None, only_here: bool=False)`

{catalogue key: [realm names]} across every realm ARMADA knows about.

### `_catalogue_pane(realm, realm_root)`

—

### `_cat_final_risk(review: dict)`

The one risk word the card commits to.

### `_paragraph_break_before_labels(text: str)`

Insert a blank line before each "LABEL — " run, so _md() renders what was one dense block as separate paragraphs — one per section of the report.

### `_cat_review_card(review: dict)`

The report a bring-a-link review renders as — server-side, so it can reuse the exact Runs/Can-touch iconography (_cap_iconcluster) and per-ability colours the User tab's declared-vs-observed panel uses. One visual language for "what can this touch", not a second one invented in JS for this one screen.

### `_cat_bring_link()`

Paste a link, an agent reviews it, the report is what decides whether to add it.

### `_cat_placeholder()`

What sits where the results will go, until they arrive.

### `_cat_source_notes(idx: dict)`

(label, what it is) for each source, so "where did this come from" has a real answer.

### `_cat_infobox(realm, idx: dict)`

The Catalogue's explainer: one line closed, the whole picture open.
