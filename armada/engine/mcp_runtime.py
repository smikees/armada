"""Live MCP startup evidence; saved OAuth credentials are not a connection test."""
from __future__ import annotations


def startup_lock():
    """One Armada startup/refresh at a time across app, scheduler and status probes."""
    from .. import appconfig, util
    return util.file_lock(appconfig._path().parent / "mcp-startup", timeout=40, validate_state=False)


def status(server: str, reply: dict) -> dict:
    """Keep tool names and exact startup errors, never transport config or credentials."""
    error = reply.get("error")
    if error:
        reason = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        return {"server": server, "state": "unknown", "tool_names": [], "error": str(reason)}
    result = reply.get("result")
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, list):
        return {"server": server, "state": "unknown", "tool_names": [], "error": "Invalid live MCP status response."}
    rows = [r for r in data if isinstance(r, dict) and r.get("name") == server]
    if len(rows) != 1:
        return {"server": server, "state": "missing", "tool_names": [], "error": "Connector is absent from the current Codex thread."}
    row = rows[0]
    tools = row.get("tools")
    names = sorted(tools) if isinstance(tools, dict) and all(isinstance(k, str) for k in tools) else []
    runtime, auth = row.get("runtimeStatus"), row.get("authStatus")
    reason = row.get("toolsError") or ""
    if not isinstance(reason, str):
        reason = str(reason)
    if runtime == "authenticationRequired" or auth == "notLoggedIn" or "invalid_grant" in reason:
        state = "sign_in"
        reason = reason or "Connector authorization is required."
    elif runtime == "disabled":
        state, reason = "disabled", reason or "Connector is disabled in Codex."
    elif reason or runtime in ("failed", "cancelled"):
        state, reason = "failed", reason or f"Connector startup {runtime}."
    elif names and runtime in (None, "connected"):
        state = "ready"
    else:
        state, reason = "unknown", reason or "Connector did not expose callable tools in this thread."
    return {"server": server, "state": state, "tool_names": names if state == "ready" else [],
            "error": reason, "runtime_status": runtime, "auth_status": auth}


def prompt(rows, *, preflight=False) -> str:
    lines = ["\n\n# Connector preflight for this turn" if preflight else "\n\n# Verified connector startup for this turn",
             "These connection checks ran before the turn. The engine's actual callable tools take precedence if a connection recovered during startup." if preflight else
             "These are actual runtime checks, not stored sign-in labels.",
             "Use callable MCP tools directly or discover deferred tools if tool search is available. Do not require tool search when it is absent."]
    for row in rows:
        if row["state"] == "ready":
            lines.append(f"{row['server']}: ready. Tool names: " + ", ".join(row["tool_names"]))
        else:
            lines.append(f"{row['server']}: {row['state']}. Exact startup error: {row['error']}")
    lines.append("Unavailable connectors do not prevent unrelated conversation or fail unrelated jobs. Do not put unused optional connector failures in the job's missing inputs, operational errors or risk gates. Their tools are withheld; use ARMADA's connect_connector tool to prepare setup when asked, and let the owner complete sign-in. Newly connected tools load on the next turn. If this task requires an unavailable connector, report the recorded error and the incomplete task; never invent a successful read or publication. Preserve incomplete evidence and risk gates.")
    return "\n".join(lines)


def claude_startup(event):
    """Actual per-turn init evidence, using the same namespaces as admission."""
    from .mcp import server_id
    from ..connector_health import public_error
    rows = []
    tools = event.get('tools', [])
    servers = event.get('mcp_servers', [])
    if not isinstance(tools, list) or not isinstance(servers, list):
        return rows
    for server in servers:
        if not isinstance(server, dict) or not isinstance(server.get('name'), str):
            continue
        sid = server_id(server['name'])
        prefix = f'mcp__{sid}__'
        names = sorted(t for t in tools if isinstance(t, str) and t.startswith(prefix))
        state = server.get('status')
        if state == 'connected' and names:
            rows.append({'server':sid, 'state':'ready', 'tool_names':names, 'error':''})
        elif state in ('failed', 'needs-auth', 'disabled'):
            rows.append({'server':sid, 'state':'sign_in' if state == 'needs-auth' else state,
                         'tool_names':[], 'error':public_error(str(server.get('error') or f'Claude startup status: {state}'))})
    return rows


def job_errors(rows, required, attempted_tools, *, root, provider):
    """Optional startup failures remain diagnostics, not evidence of a failed task.

    Keep failures for owner-required registrations and any connector actually
    attempted during the run. The model's own missing-input claims remain intact.
    """
    if not rows:
        return []  # Admission may have failed before any engine/catalogue was available.
    from .mcp import server_id, registration_id, claude_aliases
    from .. import capabilities
    from ..connector_registry import provider_cap
    normalize = server_id if provider == 'claude' else registration_id
    def identities(name):
        return {server_id(s) for s in claude_aliases(name)} if provider == 'claude' else {registration_id(name)}
    needed = set().union(*(identities(s) for s in required))
    for kind, cap in capabilities.catalogue_flat(root) if required else ():
        if kind in capabilities.MCP_KINDS and cap.get('id') in required:
            needed.update(identities(provider_cap(cap, provider)['id']))
    needed.update(name[5:].split('__', 1)[0] for name in attempted_tools
                  if name.startswith('mcp__') and '__' in name[5:])
    return [f"Connector {row['server']}: {row['error']}" for row in rows
            if row.get('state') != 'ready' and normalize(row['server']) in needed]
