# `armada/routes/realm.py`

Realm lifecycle: switch/new/archive/export/delete, preflight, workspace/approot, icon,
settings, covenant.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.

### class `RealmRoutes`

—

- `RealmRoutes._get_index(self)` — —
- `RealmRoutes._get_realm_page(self, page)` — —
- `RealmRoutes._get_new_realm(self)` — —
- `RealmRoutes._get_switch(self)` — —
- `RealmRoutes._get_pick_folder(self)` — —
- `RealmRoutes._get_check_update(self)` — —
- `RealmRoutes._get_realms(self)` — —
- `RealmRoutes._get_realm_icon(self)` — —
- `RealmRoutes._get_realm(self)` — —
- `RealmRoutes._pick_folder(self)` — Open a native folder picker on the user's machine (local app).
- `RealmRoutes._new_realm(self, body: dict)` — —
- `RealmRoutes._save_realm_settings(self, body: dict)` — —
- `RealmRoutes._upload_realm_icon(self, body: dict)` — —
- `RealmRoutes._realm_archive(self, body: dict)` — Drop a realm from ARMADA's list. Touches no files — the folder stays where it is and can be added back with the realm picker.
- `RealmRoutes._adopt_release(self, body: dict)` — The owner has read what an adopted realm will run and allows it (5.8c).
- `RealmRoutes._realm_preflight(self, body: dict)` — Can this realm run here? Holds or releases its scheduler as a side effect, so the answer and the consequence can't disagree.
- `RealmRoutes._save_covenant(self, body: dict)` — Write the realm's Covenant (tenets.md). Loaded into every agent's context, so this is the highest-leverage text in the realm — and the owner's to write, unlike System memory.
- `RealmRoutes._set_approot(self, body: dict)` — Set the one folder on this machine ARMADA works in. Re-checks the current realm after, since moving the root can put the realm you're looking at outside it.
- `RealmRoutes._first_realm(self, body: dict)` — The first-run page's Create: a realm named `name`, in a folder of that name inside the app root. The page never asks for a path — choosing where the first realm lives is a question a new user can't answer yet, and the root already answers it.
- `RealmRoutes._set_workspace(self, body: dict)` — Point the realm at its workspace folder on this machine, then re-check.
- `RealmRoutes._workspace_migrate(self, body: dict)` — Rewrite literal workspace paths in this realm's jobs as {workspace}.
- `RealmRoutes._realm_export(self, body: dict)` — —
- `RealmRoutes._realm_delete(self, body: dict)` — Delete a realm's files. Requires the realm's folder name typed back as confirmation — this is the most destructive thing ARMADA can do, so a mis-click can't reach it.
