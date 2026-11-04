# Limit tools and file writes

Open an agent's **Capabilities** page to see which connector tools it can and
cannot call, its allowed write paths, and the realm's read-only paths. Expand
**Edit access (owner only)** to change them. Every saved change is logged.

For each connector, enable **Limit this connector's tools** and enter the allowed
names or patterns, one per line. `get_*` matches names beginning with `get_`.
An empty allow list allows no tools. **Always deny** wins even if the same tool
matches an allow pattern. The connector must also be granted to that agent.

**Realm defaults** can deny tool patterns for everyone. A matching explicit agent
allow overrides a realm default denial; the agent's own deny still wins. A realm
coordinator follows these limits too.

Use **Refresh tool names** after connecting a service. If your engine cannot
return its tool list, use **Record tool names** and copy the exact names from the
connector's own list. Known names are filtered by the saved policy. New names
stay unavailable until refreshed; missing inventory never grants unrestricted
access. Malformed policies stop the run with an explanation.

Enable **Limit file writes** and enter paths relative to your realm, such as:

```text
Finance/data/**
agents/analyst/**
```

Both `\` and `/` work. `**` includes subfolders. With the limit enabled, an empty
list permits no writes. Reads remain available. Realm **Read-only paths**, such
as `skills/**`, take priority over every agent write scope. The designated builder
(default agent ID `builder`) and owner actions in ARMADA are unaffected by file
restrictions. The builder still follows connector tool limits.

Scoped agents write through ARMADA's guarded file tool. Native file writes and
shell commands are disabled because the Windows engines cannot safely restrict
arbitrary commands to path patterns. Command jobs are also refused for scoped
agents. Agent/realm control files cannot be overwritten through a broad folder
grant. External connectors need their own tool rules; a file scope governs local
files, not a service's remote data.

Denied calls and file writes appear as operational warnings in the run result.
The tools and access audit shows offered tools and refusal details. Your first
refusal notification for an agent each day uses **Agent attempts denied access**
in notification settings; later attempts stay in the audit without repeating the
notification. Limits on connector tools apply to new runs; file checks also pick
up changes during a run.
