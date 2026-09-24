# `armada/webui/memoryview.py`

Memory rendering (realm + agent memory pages) (Layer 2, Phase 3).

Imports lower layers (never _core); _core re-imports these names.

### `_agent_memory(realm_root: Path, agent_id: str)`

—

### `_tab_memory(realm, realm_root, a, focus: str='')`

—

### `_list_mem(mem_dir: Path)`

(stem, title, body, modified, kind, by) per memory file. `kind` marks the managed system memory; `by` is who last updated it (owner | system | an agent id), `modified` the update date (from frontmatter `updated`, else file mtime), both used for the 'updated by … on …' line.

### `_updater_label(by: str, realm=None, agent_display: str='')`

Human label for who last updated a memory: 'owner', 'system', or an agent's display name.

### `_mem_cards(items, scope: str, agent_id: str='', realm=None, agent_display: str='')`

—

### `_mem_add_button()`

—

### `_mem_search()`

—

### `_mem_modals(scope: str, agent_id: str='', agent_disp: str='')`

—

### `_covenant_updated(realm_root)`

When the Covenant was last changed, dd-mm-yy — or "" if it has never been written.

### `_covenant_block(realm, realm_root)`

The Covenant — realm tenets.md, pinned above the memories.

### `_covenant_modal(realm_root=None)`

App-native reader/editor for the Covenant (no browser dialogs — house rule).

### `_realm_memory(realm, realm_root)`

—
