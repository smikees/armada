# `armada/webui/pages.py`

ARMADA page entrypoints (render_*), carved out of _core.py in Phase 3.

These are the top-of-stack renderers called by serve.py. They are pure leaves — nothing in
_core calls them — so they live here and pull every helper/constant they need from _core via
the namespace mirror below (so call sites like _nav(...) / _page_shell(...) are unchanged).

### `render_thread_rail(realm, realm_root, agent_id: str, thread: str)`

Entry point for the post-reply rail refresh: render one thread's right rail (or '').

### `render_thread_turns(realm, realm_root, agent_id: str, thread: str)`

Entry point for the post-reply transcript refresh: render one thread's turns (or '').

### `render_catalogue_results(realm, realm_root, **kw)`

The Catalogue's results area on its own, for the filter/search/page refresh.

### `render_thread_embed(realm, realm_root, agent_id: str, thread: str='main', dark: bool=False)`

Minimal standalone chat pane for embedding a single thread as a dashboard widget (iframe).

### `render_agent(realm, realm_root, agent_id: str, subtab: str='threads', dark: bool=False, query=None)`

—

### `render_job(realm, realm_root, agent_id: str, job_id: str, dark: bool=False)`

—

### `render_new_agent(realm, realm_root, dark: bool=False)`

—

### `render_new_job(realm, realm_root, agent_id: str, dark: bool=False)`

—

### `_telegram_box()`

Connect Telegram: one screen, three states, nothing to configure again afterwards.

### `_a2a_defaults_box(realm_root)`

The realm-wide agent-to-agent switch and the two defaults every agent inherits.

### `_approot_box()`

The app root — one folder per machine, the outer boundary for the whole install.

### `_workspace_box(realm, cfg)`

The realm's workspace root, and the state of its portability.

### `render_settings(realm, realm_root, engine_ok, engine_detail, realms, dark=False)`

—

### `_font_picker()`

Appearance → Fonts (temporary, v0.99.62; becomes part of themes/skins). A face applies the moment it's picked — loaded first, then swapped, so nothing flashes — and is saved per machine.

### `render_new_realm(realm, dark=False, embed=False)`

—

### `render_add_section(realm, dark=False)`

—

### `render_edit_section(realm, idx: int, dark=False)`

—

### `render_section(realm, idx: int, dark=False)`

—

### `render_approvals(realm, realm_root, dark=False)`

—

### `_doc_toc()`

[(slug, title, blurb)] from the index page's table, in its order.

### `_doc_html(md_text: str)`

_md() plus what in-app docs need: page links stay in the app (and in this window), and headings get ids so `page#section` links land.

### `render_docs(realm, realm_root, dark=False, slug: str='')`

Help: the index (searchable across every page's text) or one page of docs/user/.

### `_realm_inbox(realm, realm_root)`

—

### `inbox_view(realm, realm_root, agent_id: str=None)`

Tasks agents have handed each other. Waiting and recently-handled are what you care about; everything older is folded into an archive.

### `_sec_head(title, note='')`

—

### `render_realm_page(realm, realm_root, page: str, dark: bool=False)`

—

### `_addon_widgets(realm_root)`

—

### `_addon_widget(w: dict)`

One add-on widget: a markdown body or a list of links, in the dashboard's widget chrome.

### `render_dashboard(realm, realm_root, dark: bool=False)`

—

### `_app_advanced(updater)`

Settings → App → Advanced: the automatic-updates switch (5.4, decided in ADR-005).
