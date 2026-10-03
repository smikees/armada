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


def prompt(rows) -> str:
    lines = ["\n\n# Verified connector startup for this turn",
             "These are actual runtime checks, not stored sign-in labels. Use callable MCP tools directly or discover deferred tools if tool search is available. Do not require tool search when it is absent."]
    for row in rows:
        if row["state"] == "ready":
            lines.append(f"{row['server']}: ready. Tool names: " + ", ".join(row["tool_names"]))
        else:
            lines.append(f"{row['server']}: {row['state']}. Exact startup error: {row['error']}")
    lines.append("If a required connector is unavailable, report this recorded error; do not call it a broker outage or invent a successful read. Preserve incomplete evidence and risk gates.")
    return "\n".join(lines)
