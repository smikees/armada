# `armada/webui/capabilities.py`

Capabilities / connectors / skills rendering (Layer 2, Phase 3).

Imports lower layers (never _core); _core re-imports these names.

The Catalogue tab's own rendering (search results, the bring-a-link review report, the info box)
moved to catalogue.py in this package (Phase 2, 2.4) — a pure move, no behaviour change. What
stays here is the User tab, the System tab, the cross-cutting trust-model helpers both tabs'
cards are built from, and _realm_skills, the page that stitches all three tabs together.

### `_cap_manage_btn()`

—

### `_tab_skills(realm, realm_root, a)`

One agent's capabilities: what it can use, and what the realm has that it can't.

### `_toolkit_from(js: dict)`

—

### `_realm_toolkit(realm_root)`

—

### `_agent_toolkit(realm_root, aid: str)`

—

### `_cap_iconcluster(it: dict)`

Labelled Runs + Can-touch sections (small caption over its icons, per-ability risk colour), shown inline on the right of the title row.

### `_cap_conn_info(it: dict, kind: str, ok: bool)`

Connection state shown as a plain icon + text (not a pill) next to the name — only for things that actually connect, or when a state needs attention.

### `_cap_made(it: dict)`

(made-key, is-you) — who made it, where that is recorded.

### `_cap_tier(it: dict)`

The risk tier. One implementation — every view reads this, nothing computes its own.

### `_cap_tier_why(it: dict)`

(tier, one-line reason). Derived from checkable facts, never from an opinion.

### `_cap_persist(it: dict, kind: str)`

(is-frozen, note). Explicit 'persist' wins; else derive: remote/service = living, local = frozen.

### `_cap_source_label(it: dict)`

Which Catalogue source this capability came from, as the Catalogue would name it.

### `_cap_source_id(it: dict)`

The filter value for that source — the catalogue source id, or "claude".

### `_cap_source_pill(it: dict)`

The 'from X' source pill shown right after the capability name.

### `_cap_cell(label: str, icons: str)`

One capability-row column: a small caption above its icon(s), on a single line.

### `_cap_runs_cell(it: dict)`

—

### `_cap_touch_cell(it: dict)`

—

### `_cap_badges(it: dict)`

—

### `_cap_has_update(it: dict)`

—

### `_cap_advanced(it: dict, kind: str, manage)`

A collapsible Advanced section (an expansion inside the expansion): granular per-capability settings. For now, the permission stance ARMADA passes to agents for this capability.

### `_cap_agents(realm, realm_root, it: dict)`

(coordinators, granted) — who can use this capability.

### `_cap_availto_label(realm, coords, granted)`

The collapsed-row summary: 'Marcus + 4 agents', or '4 agents' where there's no coordinator.

### `_cap_availto_cell(realm, realm_root, it: dict)`

—

### `_cap_availto_chips(realm, realm_root, it: dict, kind: str)`

The expanded 'Available to' row — the same chip language as goal owners, deliberately: it is the same idea (who is attached to this thing), and a second visual vocabulary for it would make two familiar screens feel unrelated.

### `_cap_prov(it: dict, kind: str, manage=None, realm=None, realm_root=None)`

The expandable provenance panel: where from (+ link), persistence, installs, declared-vs-observed, a skill-contents link, and an Advanced sub-section.

### `_cap_card(it: dict, inherited: bool=False, manage=None, kind: str='', realm=None, realm_root=None)`

—

### `_cap_is_new(it: dict, realm=None, realm_root=None, kind: str='')`

Has this capability been added but not yet put to work?

### `_cap_new_badge()`

—

### `_tool_group(title: str, icon: str, realm_items, agent_items=None, manage=None, compact: bool=False, realm=None, realm_root=None, allow_refresh: bool=False)`

manage: None (read-only) or a scope string ('realm' or an agent id) that owns the *own* items. compact: show the category by its icon only (no title/description) — used for the per-agent grid, where the icon + fixed order already identify each bucket.

### `_cap_legend()`

A compact key for the card labels — same icons the cards use, with a plain-English description.

### `_cap_roster(realm, realm_root)`

Draggable agents, below the legend. Same component as the Goals roster — dragging a person onto a thing to attach them is one idea, and it should feel identical in both places.

### `_sys_card(it: dict)`

One system skill: same visual language as a capability card, but locked — no toggle, no delete, no edit. The lock is the point, so it's stated on the card and explained once above.

### `_system_panel()`

The System tab: what ARMADA runs on your behalf, and why you can't switch it off.

### `_realm_skills(realm, realm_root)`

—
