# `armada/routes/dashboard.py`

The Overview dashboard's sections/widgets, usage, memory, goals, and inbox.

These don't map onto one of the plan's six named areas on their own, but they're
cohesive as "the realm-content tabs", and none is big enough alone to warrant its own
module.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.

### class `DashboardRoutes`

—

- `DashboardRoutes._get_add_section(self)` — —
- `DashboardRoutes._get_edit_section(self, path)` — —
- `DashboardRoutes._get_section(self, path)` — —
- `DashboardRoutes._get_usage(self)` — —
- `DashboardRoutes._get_usage_limits(self)` — —
- `DashboardRoutes._delete_memory(self, body: dict)` — —
- `DashboardRoutes._add_memory(self, body: dict)` — —
- `DashboardRoutes._add_goal(self, body: dict)` — —
- `DashboardRoutes._delete_goal(self, body: dict)` — —
- `DashboardRoutes._set_goal_agents(self, body: dict)` — Add/remove/toggle one owner on a goal. action: 'add' (drag), 'remove' (chip ×), or 'toggle' (default). The coordinator is always an owner and isn't stored here.
- `DashboardRoutes._add_section(self, body: dict)` — —
- `DashboardRoutes._add_widget_section(self, body: dict)` — Promote a dashboard widget to its own nav section. De-dupes: one section per widget id.
- `DashboardRoutes._sections_rw(self)` — —
- `DashboardRoutes._update_section(self, body: dict)` — —
- `DashboardRoutes._delete_section(self, body: dict)` — —
- `DashboardRoutes._rename_section(self, body: dict)` — Rename in place — change only the display name, preserving url/path/widget/snapshot.
- `DashboardRoutes._reorder_sections(self, body: dict)` — Reorder to the given index permutation (list of original indices, new order).
- `DashboardRoutes._snapshot_refresh(self, section: dict, force: bool=False)` — Keep a section's local snapshot (inside the realm) fresh from its `source`. source = a local file/glob (newest wins) or an http(s) URL. Serving the local copy means external firewalls / cross-origin iframe 'verifying…' challenges never bite.
- `DashboardRoutes._section_snapshot(self, body: dict)` — —
- `DashboardRoutes._section_asset(self, path: str)` — Serve a file from an 'app section's local asset directory (sandboxed to that dir), so a mini-site (shell + css + js + data) renders same-origin — its own header, edition picker and theme toggle all work, with no external firewall in the way.
- `DashboardRoutes._section_raw(self, path: str)` — —
- `DashboardRoutes._inbox_unread(self, body: dict)` — Put a handled message back in the waiting pile so it runs again on the next pass.
- `DashboardRoutes._inbox_process(self, body: dict)` — Run a waiting message now instead of waiting for the agent's cadence.
- `DashboardRoutes._inbox_delete(self, body: dict)` — —
- `DashboardRoutes._save_dashboard(self, body: dict)` — —
- `DashboardRoutes._usage_api(self, mode: str, window: str, by: str='agents')` — —
