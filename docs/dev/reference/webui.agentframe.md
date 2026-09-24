# `armada/webui/agentframe.py`

Agent frame (Phase 3 split of agentpages): agent header/body + the Jobs/Inbox/Configure sub-tabs, avatar + appoint modals.

### `_agent_default_color(realm, agent_id: str)`

The palette colour an agent falls back to (stable by its position in the realm).

### `_read_md(realm_root: Path, agent_id: str, fname: str)`

—

### `_agent_header(realm, realm_root, a)`

—

### `_agent_body(realm, realm_root, a, subtab, query=None)`

—

### `_tab_jobs(realm, realm_root, a, today, open_job: str='')`

—

### `_inbox_msgs(realm_root, agent_id: str)`

Messages to this agent: agents/<id>/inbox/*.md files and/or inbox.md, newest first.

### `_tab_inbox(realm, realm_root, a)`

This agent's slice of the realm inbox — what it's been asked to do and what it has asked of others. Renders through the same view as the realm page (scoped by agent) rather than a second implementation, so the two can't drift apart.

### `_a2a_box(on: bool, freq_opts: str, accepts_opts: str, field: str, lbl: str)`

Agent-to-agent communication: one master switch with the two settings it governs beneath it.

### `_agent_manage_box(realm, a)`

Retire and Delete, ordered harmless-to-irreversible and described that way — the same shape as Manage this realm in Settings, because it is the same decision one level down.

### `_agent_advanced_box(fallback_opts: str, maxbudget: str, field: str, lbl: str, manage: str='')`

Advanced, last on the page and with a heading you can actually see. It used to be a small uppercase line wedged between two field groups, which read as a label rather than a section.

### `_md_field(fid: str, label: str, raw: str, lbl: str, ta: str, min_h: int)`

A markdown field that reads as prose and edits as source.

### `_tab_configure(realm, realm_root, a)`

—

### `_configure_actions(a)`

Save / Cancel, pinned to the right of the form.

### `_avatar_count()`

—

### `_avatar_modal(agent_id: str)`

—
