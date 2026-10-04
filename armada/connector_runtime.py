"""Provider-specific MCP connections for realm capabilities.

A realm grant is permission, not a provider login. Claude's MCP inventory and Codex's
MCP inventory are separate; never infer one provider's authentication from the other.
"""
from __future__ import annotations
from .background import process_options
import logging

import json
import re
import subprocess
from concurrent.futures import Future, wait
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from .engine.codex import CodexEngine, _NO_WINDOW, _feature_args


_SERVER_ID = re.compile(r"[A-Za-z0-9_-]+\Z")
_IBKR_KEY = "mcp-registry/connectors/com.ibkr/interactive-brokers-ibkr"
_IBKR_PUBLIC_URL = "https://api.ibkr.com/v1/api/mcp-public"
_connection_checks = {}
_checks_lock = threading.Lock()
_CHECK_DEADLINE = 90
_CHECK_CACHE_TTL = 60


def codex_endpoint(cap: dict) -> str:
    """Return a direct HTTPS MCP endpoint, never a Claude-only proxy or local command."""
    if str(cap.get("catalogue_key") or "").lower() == _IBKR_KEY:
        return _IBKR_PUBLIC_URL
    # Claude-managed connector URLs can be account-specific. Only registry entries
    # with a direct URL are portable without a provider-specific setup flow.
    if str(cap.get("id") or "").lower().startswith("claude_ai_"):
        return ""
    candidate = str(cap.get("command") or "").strip()
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    if any(c.isspace() for c in candidate) or any(ord(c) < 32 for c in candidate):
        return ""
    return candidate


def codex_inventory(engine: CodexEngine | None = None) -> dict[str, dict] | None:
    """Read the effective Codex server inventory; None means it could not be verified."""
    engine = engine or CodexEngine()
    try:
        result = engine._probe(_feature_args() + ["mcp", "list", "--json"])
        rows = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if not isinstance(rows, list) or any(not isinstance(row, dict) or
                                         not isinstance(row.get("name"), str) for row in rows):
        return None
    return {row["name"]: row for row in rows}


def codex_connection(cap: dict, inventory: dict[str, dict] | None) -> str:
    """Connection state for a *particular* provider, not the realm's generic status."""
    sid = str(cap.get("id") or "")
    if not _SERVER_ID.fullmatch(sid) or not codex_endpoint(cap):
        return "unsupported"
    if inventory is None:
        return "unknown"
    row = inventory.get(sid)
    if not row:
        return "missing"
    if row.get("runtime_state"):
        return row["runtime_state"]
    if row.get("enabled") is False:
        return "disabled"
    transport = row.get("transport") or {}
    if not isinstance(transport, dict) or transport.get("url") != codex_endpoint(cap):
        return "different"
    auth = str(row.get("auth_status") or "").lower()
    if auth in ("not_logged_in", "unauthenticated", "login_required", "not_authenticated"):
        return "sign_in"
    if auth in ("authenticated", "logged_in", "o_auth"):
        return "ready"
    # 'unsupported' can mean a public server with no OAuth support. Do not call
    # a private brokerage connector authenticated on that evidence alone.
    return "configured"


def codex_live_inventory(realm_root, engine: CodexEngine | None = None) -> dict[str, dict] | None:
    """Verify startup in a gated, ephemeral thread without making a model request."""
    from pathlib import Path
    from . import capabilities
    from .engine.codex import _feature_args
    from .engine.contracts import ExecutionPolicy
    from .engine.mcp_runtime import status as live_status, startup_lock
    from .engine.process import supervise_rpc
    engine = engine or CodexEngine()
    inventory = codex_inventory(engine)
    if inventory is None:
        return None
    caps = capabilities.catalogue(realm_root)["connectors"]
    ids = {str(c["id"]) for c in caps if c.get("id") and codex_endpoint(c)
           and codex_connection(c, inventory) in ("ready", "configured", "sign_in")}
    if not ids:
        return inventory
    engine = engine.configure(ExecutionPolicy(frozenset(ids), (str(Path(realm_root).resolve()),), False))
    cwd = str(Path(realm_root).resolve())
    args = _feature_args() + engine._mcp_args(True, (), cwd=cwd)
    pending = list(engine._turn_mcp_ids)
    checked = {}
    thread_id = ""
    def start(send):
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "armada", "title": "Armada", "version": "1.0"}}})
    def next_server(send):
        if not pending:
            return True
        send({"id": 4, "method": "mcpServerStatus/list", "params": {
            "threadId": thread_id, "serverName": pending[0], "detail": "toolsAndAuthOnly"}})
        return False
    def accept(message, send):
        nonlocal thread_id
        rid = message.get("id")
        if "method" in message and rid is not None:
            send({"id": rid, "error": {"code": -32601, "message": "Connection checks do not grant interactive approvals."}})
            return False
        if rid == 4:
            sid = pending.pop(0)
            checked[sid] = live_status(sid, message)
            return next_server(send)
        if rid in (1, 2) and message.get("error"):
            raise ValueError("Codex could not initialize the connector check.")
        if rid == 1:
            send({"method": "initialized", "params": {}})
            send({"id": 2, "method": "thread/start", "params": {
                "cwd": cwd, "approvalPolicy": "never", "sandbox": "read-only", "ephemeral": True, "serviceName": "armada"}})
        elif rid == 2:
            thread_id = message["result"]["thread"]["id"]
            return next_server(send)
        return False
    with startup_lock():
        process = supervise_rpc(engine._launcher() + ["app-server"] + args, start=start,
                                on_message=accept, timeout=35, cwd=cwd)
    for sid in ids:
        row = checked.get(sid) or {"state": "unknown", "error": process.error or "Live connector startup was not verified."}
        inventory[sid] = {**inventory[sid], "runtime_state": row["state"], "runtime_error": row["error"]}
    return inventory


def _identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def claude_inventory() -> dict[str, bool] | None:
    """Read Claude's current MCP health, without returning URLs or credentials."""
    from .engine.claude import ClaudeEngine
    from .engine.mcp import connected_names
    engine = ClaudeEngine()
    launcher = engine._launcher()
    if not launcher:
        return None
    try:
        result = subprocess.run(launcher + ["mcp", "list"], capture_output=True, text=True,
                                timeout=25, encoding="utf-8", errors="replace",
                                env=engine._env(), **process_options())
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    connected = connected_names(result.stdout)
    found = {}
    for line in re.sub(r'\x1b\[[0-9;]*m', '', result.stdout).splitlines():
        if ":" not in line or " - " not in line:
            continue
        name, detail = line.split(":", 1)
        key = _identity(name)
        if key:
            found[key] = name.strip() in connected
    return found


def claude_connection(cap: dict, inventory: dict[str, bool] | None) -> str:
    if inventory is None:
        return "unknown"
    for name in (cap.get("id"), cap.get("name")):
        key = _identity(name)
        if key in inventory:
            return "ready" if inventory[key] else "failed"
    return "missing"


def connection_snapshot(realm_root, *, force=False) -> dict:
    """Nonblocking, independent provider checks; pending checks have a fixed deadline."""
    from . import capabilities, providers

    def probe(provider):
        try:
            state = providers.status(provider, force=True)
            connected = state.get("connected") is True
            detail = "ready" if connected else ("disabled" if not state.get("enabled", True) else "unavailable")
        except Exception:
            logging.getLogger(__name__).exception('Provider availability check failed')
            connected, detail = False, "unknown"
        inventory = None
        if connected:
            try:
                if provider == 'gemini':
                    from pathlib import Path
                    try:
                        inventory = json.loads((Path.home()/'.gemini/config/mcp_config.json').read_text(encoding='utf-8-sig')).get('mcpServers',{})
                        if not isinstance(inventory,dict): inventory = None
                    except FileNotFoundError: inventory = {}
                else:
                    inventory = claude_inventory() if provider == "claude" else codex_live_inventory(realm_root)
            except (OSError, ValueError, subprocess.SubprocessError):
                inventory = None
        return detail, inventory

    caps = capabilities.catalogue(realm_root)["connectors"]
    signature = json.dumps(caps, sort_keys=True, default=str)
    checks = {}
    now = time.monotonic()
    with _checks_lock:
        for provider in ('claude', 'codex', 'gemini'):
            key = (str(Path(realm_root).resolve()), provider, signature)
            check = _connection_checks.get(key)
            if check is None or (check['future'].done() and (force or now-check['finished'] >= _CHECK_CACHE_TTL)):
                check = {'future': Future(), 'started': now, 'finished': now}
                _connection_checks[key] = check
                def worker(provider=provider, check=check):
                    try:
                        state, inventory = probe(provider)
                        result = (state, inventory, '')
                    except Exception as exc:
                        logging.getLogger(__name__).exception('Connector inventory check failed')
                        result = ('unknown', None, f'{type(exc).__name__}: {exc}')
                    check['finished'] = time.monotonic()
                    check['future'].set_result(result)
                threading.Thread(target=worker, daemon=True).start()
            checks[provider] = check
    # Let inexpensive local checks finish, without waiting for a slow CLI or startup lock.
    wait([c['future'] for c in checks.values()], timeout=.02)
    states, errors = {}, {}
    for provider, check in checks.items():
        if check['future'].done():
            states[provider], inventory, errors[provider] = check['future'].result()
        else:
            elapsed = time.monotonic()-check['started']
            states[provider], inventory = ('checking' if elapsed < _CHECK_DEADLINE else 'unknown'), None
            errors[provider] = '' if states[provider] == 'checking' else 'Connector check timed out. Recheck to try again.'
        checks[provider] = inventory
    claude_state, claude_servers = states['claude'], checks['claude']
    codex_state, codex_servers = states['codex'], checks['codex']
    gemini_state, gemini_servers = states['gemini'], checks['gemini']
    rows = {}
    for cap in caps:
        sid = str(cap.get("id") or cap.get("name") or "")
        if not sid or is_provider_placeholder(cap):
            continue
        rows[sid] = {
            "claude": claude_connection(cap, claude_servers) if claude_state == "ready" else claude_state,
            "codex": codex_connection(cap, codex_servers) if codex_state == "ready" else codex_state,
            "codex_supported": bool(codex_endpoint(cap)),
            # Registration does not prove the Google connector's own authorization.
            "gemini": (gemini_state if gemini_state != 'ready' else 'unknown' if gemini_servers is None else
                       'missing' if sid not in gemini_servers else 'unknown' if not isinstance(gemini_servers[sid],dict) else
                       'disabled' if gemini_servers[sid].get('disabled') else 'configured'),
            "errors": {**errors, "codex": errors['codex'] or (codex_servers or {}).get(sid, {}).get("runtime_error", "")},
        }
    return {"providers": states, "connectors": rows, "pending": 'checking' in states.values()}


def is_provider_placeholder(cap: dict) -> bool:
    """Old auto-discovery filed the model app itself as a user MCP connector."""
    return (str(cap.get("id") or "").lower() in ("claude", "codex", "gemini")
            and cap.get("discovered") is True and not cap.get("command")
            and str(cap.get("scope") or "").lower() == "mcp server (claude)")


def connect_codex(cap: dict, realm_root=None) -> dict:
    """Register a reviewed realm endpoint and start Codex's own browser OAuth flow."""
    sid = str(cap.get("id") or "")
    endpoint = codex_endpoint(cap)
    if not _SERVER_ID.fullmatch(sid) or not endpoint:
        return {"ok": False, "error": "This connector has no supported Codex endpoint."}
    engine = CodexEngine()
    inventory = codex_live_inventory(realm_root, engine) if realm_root else codex_inventory(engine)
    if inventory is None:
        return {"ok": False, "error": "Could not inspect Codex MCP connections."}
    state = codex_connection(cap, inventory)
    if state in ("different", "disabled"):
        return {"ok": False, "error": "A Codex MCP server with this name already has different settings. Review it in Codex first."}
    launcher = engine._launcher()
    if not launcher:
        return {"ok": False, "error": "Codex CLI is not installed."}
    if state == "missing":
        try:
            result = engine._probe(["mcp", "add", sid, "--url", endpoint])
        except (OSError, subprocess.SubprocessError):
            result = None
        # `codex mcp add` may enter an immediate OAuth flow after writing its
        # configuration. A timed-out CLI is not proof that registration failed.
        if result is None or result.returncode:
            refreshed = codex_inventory(engine)
            if codex_connection(cap, refreshed) not in ("sign_in", "configured", "ready"):
                return {"ok": False, "error": "Codex could not add this connector. Check its URL and CLI setup."}
    if state == "ready":
        return {"ok": True, "state": "ready"}
    try:
        subprocess.Popen(launcher + _feature_args() + ["mcp", "login", sid], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         **process_options())
    except OSError:
        return {"ok": False, "error": "Codex could not start the connector sign-in."}
    return {"ok": True, "state": "sign_in"}
