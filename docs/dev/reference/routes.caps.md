# `armada/routes/caps.py`

Capabilities/skills.

save/delete/toggle/permission, scan-updates, version update, skill content, connectors
refresh, grant/revoke/request approve-reject, open/reveal/delete an artefact.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.

### class `CapabilityRoutes`

—

- `CapabilityRoutes._read_claude_mcp(self)` — Best-effort: enumerate MCP servers Claude Code can see (~/.claude.json + project scopes + .mcp.json).
- `CapabilityRoutes._refresh_connectors(self, body: dict)` — Pull the MCP servers the CLI knows about into this scope's catalogue.
- `CapabilityRoutes._dedupe_toolkit(tk: dict)` — Drop entries that name a capability already listed under another kind. Returns what went.
- `CapabilityRoutes._cap_target(self, scope: str)` — Return (json_path) for a capability scope: 'realm' -> realm.json, else agent.json.
- `CapabilityRoutes._save_capability(self, body: dict)` — —
- `CapabilityRoutes._toggle_capability(self, body: dict)` — —
- `CapabilityRoutes._set_cap_permission(self, body: dict)` — —
- `CapabilityRoutes._scan_updates(self, body: dict)` — Scan CLI-known capabilities for real installed/latest versions (read-only).
- `CapabilityRoutes._update_capability_version(self, body: dict)` — Apply an available update. Plugins are updated for real via `claude plugin update`; other types are managed by the Claude app, not the CLI, so ARMADA can't fetch/install them here.
- `CapabilityRoutes._skill_md_path(self, sid: str)` — Best-effort locate a skill's SKILL.md across the realm and the usual skill roots.
- `CapabilityRoutes._get_skill_content(self)` — —
- `CapabilityRoutes._artefact_roots(self)` — Where an artefact the app may open or delete can live: this realm, its workspace root, and the app root every realm sits in. Nothing outside them (THREAT_MODEL T6).
- `CapabilityRoutes._within_artefact_roots(self, p: Path)` — —
- `CapabilityRoutes._open_file(self, body: dict)` — Open an artifact with its default application (local, single-user app).
- `CapabilityRoutes._delete_artefact(self, body: dict)` — Delete an artifact file from disk. The thread's record of it is left alone — history shouldn't silently rewrite itself; the row simply stops offering actions.
- `CapabilityRoutes._cap_grant(self, body: dict)` — Map a realm capability to an agent — the owner doing it deliberately, from the Capabilities page. Recorded as via='user' so the thread rail won't call it new.
- `CapabilityRoutes._cap_revoke(self, body: dict)` — —
- `CapabilityRoutes._cap_request_approve(self, body: dict)` — Approve what an agent asked for in a thread. The grant remembers that thread, which is what makes it show as new there.
- `CapabilityRoutes._cap_request_reject(self, body: dict)` — —
- `CapabilityRoutes._reveal_skill(self, body: dict)` — Open the OS file manager with a skill's SKILL.md selected.
- `CapabilityRoutes._delete_capability(self, body: dict)` — —
- `CapabilityRoutes._reveal(self, body: dict)` — Open the OS file explorer at an OUTPUT artifact (selecting the file). ARMADA is a local, single-user app, so revealing a path the agent itself wrote on this machine is safe; we still require the path to exist and be a real file before handing it to the shell.
