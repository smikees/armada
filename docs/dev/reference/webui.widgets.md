# `armada/webui/widgets.py`

Dashboard widget renderers (Layer 2, carved from _core.py in Phase 3).

The Register, Usage and Job-calendar widgets (+ their shared widget header/menu chrome and
health-legend styling). Import lower layers + the agent-rendering primitives (agentbits), never
_core, so _core imports these back without a cycle.

### `_reg_row(a, realm_root: Path, today: datetime.date, coord: bool=False, realm=None)`

—

### `_widget_menu(widget_id: str)`

The ⋮ options menu on a single-instance widget (Register / Usage / Job calendar), top-right. 'Add as section' promotes the widget to its own nav page; 'Remove widget' hides it (client handlers).

### `_wid_header(title: str, meta: str='', right: str='', widget_id: str='', chrome: bool=True)`

—

### `_register(realm, realm_root, today, section: bool=False)`

—

### `_usage(realm, realm_root, today, section: bool=False)`

—

### `_jobcal(realm, realm_root, today, legend: bool=True, widget: bool=True, scope: str='', fpfx: str='', title: str='Job calendar')`

The job calendar. `scope` selects which events it loads ('' = the realm's agent jobs, 'system' = ARMADA's own upkeep) and `fpfx` names the filter bar it should obey — empty on the dashboard widget, which has no filters.
