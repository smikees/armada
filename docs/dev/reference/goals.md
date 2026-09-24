# `armada/goals.py`

Realm goals — the objectives agents actively advance (distinct from passive memory).

A goal is a Markdown file under <realm>/goals/, one per goal, with frontmatter:

    ---
    title: Reach EUR 2.5M net worth
    status: On track
    target: 2026-12-31
    agents: warren,ray
    ---
    Description / what "done" looks like...

`agents` is the explicit list of non-coordinator agents mapped to the goal. The
coordinator is ALWAYS mapped (by default, non-removable) and is handled at read
time via the is_coord flag rather than being stored in every file — so a change of
coordinator never leaves stale mappings behind.

Mapped goals are injected into an agent's always-on core (memory.assemble_core), so
they load into every thread for the agents that advance them.

### `_dir(realm_root)`

—

### `_slug(text: str)`

A safe filename stem from arbitrary text (lowercase alnum + dashes).

### `_agents_list(meta: dict)`

—

### `_fmt_target(target: str)`

ISO date -> a friendlier 'dd Mon yyyy'; pass through anything unparseable.

### `_overdue(target: str)`

—

### `list_goals(realm_root)`

Every goal as a dict. `effective_status` applies the rule 'a goal whose ETA is in the past is At risk' (unless it's Done); `overdue` flags that case for styling.

### `get_goal(realm_root, stem: str)`

—

### `_write(realm_root, stem: str, title: str, status: str, target: str, body: str, agents: list[str])`

—

### `save_goal(realm_root, title: str, body: str, status: str='', target: str='', agents: list[str] | None=None, stem: str | None=None)`

Create a new goal or edit an existing one (when `stem` names an existing file). Returns the goal's stem. Preserves the existing agent mapping on edit unless `agents` is explicitly provided.

### `set_agents(realm_root, stem: str, agents: list[str])`

Replace the mapped (non-coordinator) agents for a goal.

### `delete_goal(realm_root, stem: str)`

—

### `goals_for_agent(realm_root, agent_id: str, is_coord: bool=False)`

Goals this agent advances: all of them if it's the coordinator, else the ones whose agent mapping names it.
