# `armada/webui/goalsview.py`

Goals rendering (realm goals page + agent goals tab) (Layer 2, Phase 3).

Imports lower layers (never _core); _core re-imports these names.

### `_goal_status_badge(status: str)`

—

### `_goal_owner_chips(realm, realm_root, goal: dict)`

Owners of a goal: coordinator pinned (non-removable) + mapped members (removable ×).

### `_goal_cards(realm, realm_root, items)`

—

### `_goal_roster(realm, realm_root)`

Right-hand roster of draggable agents; drop one onto a goal to make it an owner.

### `_goal_status_options(sel: str='')`

—

### `_goal_modals(realm, add_title: str='Add a goal', owner_id: str='')`

Add / edit / delete goal modals. When owner_id is set (agent Goals page), the new goal is auto-owned by that agent and the title reads 'Add goal for …'.

### `_realm_goals(realm, realm_root)`

—

### `_tab_goals(realm, realm_root, a)`

Per-agent Goals tab: the goals this agent advances, with an add-goal modal that auto-maps the agent as an owner.
