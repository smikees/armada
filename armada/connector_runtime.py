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
from .engine.mcp import registration_id, server_id
from .connector_registry import provider_cap

_DRIVE_URL = 'https://drivemcp.googleapis.com/mcp/v1'
_GOOGLE_URLS = {_DRIVE_URL, 'https://docsmcp.googleapis.com/mcp/v1', 'https://gmailmcp.googleapis.com/mcp/v1',
                'https://sheetsmcp.googleapis.com/mcp/v1', 'https://slidesmcp.googleapis.com/mcp/v1',
                'https://calendarmcp.googleapis.com/mcp/v1', 'https://chatmcp.googleapis.com/mcp/v1'}


def _login_key(realm_root, cap, provider):
    return (str(Path(realm_root or Path.cwd()).resolve()), provider, str(cap.get('id') or ''),
            str(cap.get('command') or ''))


def _codex_drive_client(cap):
    """Read only the presence of Codex's own pre-registered OAuth client ID."""
    import os
    import tomllib
    if codex_endpoint(cap) not in _GOOGLE_URLS:
        return True
    try:
        root = Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
        data = tomllib.loads((root/'config.toml').read_text(encoding='utf-8-sig'))
        row = data.get('mcp_servers', {}).get(registration_id(cap.get('id')), {})
        client = row.get('oauth', {}).get('client_id')
        return isinstance(client, str) and bool(client.strip()) and client.strip() != 'YOUR_GOOGLE_OAUTH_CLIENT_ID'
    except (OSError, ValueError, AttributeError, TypeError):
        return False


_SERVER_ID = re.compile(r"[A-Za-z0-9_-]+\Z")
_IBKR_KEY = "mcp-registry/connectors/com.ibkr/interactive-brokers-ibkr"
_IBKR_PUBLIC_URL = "https://api.ibkr.com/v1/api/mcp-public"
_connection_checks = {}
_checks_lock = threading.Lock()
_CHECK_DEADLINE = 90
_CHECK_CACHE_TTL = 60


def _login_finished(realm_root, provider):
    """Discard earlier health checks; completed login alone never means Connected."""
    root = str(Path(realm_root or Path.cwd()).resolve())
    with _checks_lock:
        for key in list(_connection_checks):
            if key[:2] == (root, provider):
                del _connection_checks[key]


def codex_endpoint(cap: dict) -> str:
    """Return a direct HTTPS MCP endpoint, never a Claude-only proxy or local command."""
    if 'mcp_url' in cap:
        from .connector_registry import endpoint
        return endpoint(cap['mcp_url'])
    if str(cap.get("catalogue_key") or "").lower() == _IBKR_KEY:
        return _IBKR_PUBLIC_URL
    # Claude-managed connector URLs can be account-specific. Only registry entries
    # with a direct URL are portable without a provider-specific setup flow.
    if str(cap.get("id") or "").lower().startswith(("claude_ai_", "claude.ai ")):
        # Google's published MCP endpoint is portable; a Claude proxy is not.
        if str(cap.get("command") or "").strip() == "https://drivemcp.googleapis.com/mcp/v1":
            return "https://drivemcp.googleapis.com/mcp/v1"
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
    cap = provider_cap(cap, 'codex')
    if cap.get('_native_app'):
        if inventory is None or (inventory.get(cap['id']) or {}).get('runtime_state') == 'unknown':
            return 'unknown'
        row = inventory.get(cap['id'])
        return ('ready' if row.get('callable') else 'disabled' if row.get('enabled') is False else 'sign_in') if row else 'missing'
    sid = registration_id(cap.get("id"))
    if cap.get('_unbound') or not cap.get("id") or (not codex_endpoint(cap) and not cap.get('_bound_registration')):
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
    if not isinstance(transport, dict) or (codex_endpoint(cap) and transport.get("url") != codex_endpoint(cap)):
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
    caps = [provider_cap(c, 'codex') for c in capabilities.catalogue(realm_root)["connectors"]]
    if any(c.get('_native_app') for c in caps):
        from . import codex_apps
        try:
            inventory.update({r['id']: r for r in codex_apps.inventory(force=True, cwd=realm_root)})
        except (OSError, ValueError):
            inventory.update({c['id']: {'runtime_state': 'unknown'} for c in caps if c.get('_native_app')})
    ids = {registration_id(c["id"]) for c in caps if c.get("id") and not c.get('_native_app') and (codex_endpoint(c) or c.get('_bound_registration'))
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
        inventory[sid] = {**inventory[sid], "runtime_state": row["state"], "runtime_error": row["error"],
                          'tool_names': row.get('tool_names', [])}
    return inventory


def _identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _claude_rows(realm_root=None) -> list[dict] | None:
    """Read Claude's current MCP health, without returning URLs or credentials."""
    from .engine.claude import ClaudeEngine
    from .engine.mcp import connected_names
    engine = ClaudeEngine()
    launcher = engine._launcher()
    if not launcher:
        return None
    try:
        result = subprocess.run(launcher + ["mcp", "list"], capture_output=True, text=True,
                                timeout=45, encoding="utf-8", errors="replace",
                                env=engine._env(), cwd=realm_root, **process_options())
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    connected = connected_names(result.stdout)
    found = []
    for line in re.sub(r'\x1b\[[0-9;]*m', '', result.stdout).splitlines():
        if ":" not in line or " - " not in line:
            continue
        name, detail = line.split(":", 1)
        key = _identity(name)
        if key:
            address = detail.rsplit(' - ', 1)[0].strip()
            found.append({"name": name.strip(), "ready": name.strip() in connected,
                          'endpoint': address, 'remote': address.startswith(('https://', 'http://'))})
    return found


class _ClaudeInventory(dict):
    """Compatibility boolean inventory with endpoint evidence retained only in memory."""
    def __init__(self):
        super().__init__()
        self.endpoints = {}


def claude_inventory() -> dict[str, bool | None] | None:
    rows = _claude_rows()
    if rows is None:
        return None
    found = _ClaudeInventory()
    for row in rows:
        key = _identity(row["name"])
        found[key] = None if key in found else row["ready"]
        found.endpoints[key] = row.get('endpoint', '')
    return found


def claude_connection(cap: dict, inventory: dict[str, bool | None] | None) -> str:
    cap = provider_cap(cap, 'claude')
    if cap.get('_unbound'):
        return 'unsupported'
    if inventory is None:
        return "unknown"
    for name in (cap.get("id"), cap.get("name"), registration_id(cap.get("id"))):
        key = _identity(name)
        if key in inventory:
            if inventory[key] is None:
                return "different"
            actual = getattr(inventory, 'endpoints', {}).get(key)
            if cap.get('_bound_registration') and actual and codex_endpoint(cap) and actual != codex_endpoint(cap):
                return 'different'
            return "ready" if inventory[key] else "failed"
    return "missing"


def gemini_inventory() -> dict | None:
    """The same global inventory admitted by GeminiEngine; no credential transfer."""
    try:
        value = json.loads((Path.home()/'.gemini/config/mcp_config.json').read_text(encoding='utf-8-sig'))
        servers = value.get('mcpServers', {})
        return servers if isinstance(servers, dict) else None
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, AttributeError):
        return None


def gemini_connection(cap, inventory):
    cap = provider_cap(cap, 'gemini')
    if cap.get('_unbound'):
        return 'unsupported'
    if inventory is None:
        return "unknown"
    sid = registration_id(cap.get("id"))
    if sid not in inventory:
        return "missing" if codex_endpoint(cap) else "unsupported"
    row = inventory[sid]
    if not isinstance(row, dict):
        return "unknown"
    if row.get('disabled'):
        return "disabled"
    endpoint = codex_endpoint(cap)
    if endpoint and row.get('serverUrl') != endpoint:
        return "different"
    return "configured"  # saved configuration does not prove authentication or tool health


def connection_detail(cap, provider, state, error=""):
    """Owner-facing state and recovery action; unsupported is never called disconnected."""
    if (cap.get('provider_bindings') or {}).get(provider) == {'disabled': True}:
        return {'state': 'missing', 'reason': 'Unlinked in this realm. Use Setup details → Link existing connection to restore access.',
                'action': 'setup', 'server_id': ''}
    cap = provider_cap(cap, provider)
    title = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini"}[provider]
    if cap.get('_native_app'):
        reason = {'ready': 'Codex reports this native connector enabled with callable tools.',
                  'missing': 'Connect this app using your Codex account, then recheck here.',
                  'disabled': 'Enable this app in Codex, then recheck here.',
                  'sign_in': 'Complete this app’s Codex sign-in, then recheck here.'}.get(state)
        return {'state': state, 'reason': error or reason or 'Native Codex connector status is not verified.',
                'action': 'provider_settings' if state in ('unavailable', 'provider_disabled') else
                    'connect' if state not in ('ready', 'checking', 'realm_disabled') else '', 'server_id': cap['id']}
    if cap.get('native_service') and cap.get('_unbound') and state not in ('checking', 'realm_disabled', 'provider_disabled', 'unavailable'):
        return {'state': 'missing' if provider in ('claude', 'codex') else 'unsupported',
                'reason': 'Connect the native app using your Codex account, then recheck here.' if provider == 'codex' else
                    'Connect in Claude, then use Link connection to select its registration.' if provider == 'claude' else
                    'This provider does not expose the same native app. Link an existing compatible MCP connection if available.',
                'action': 'connect' if provider in ('claude', 'codex') else 'setup', 'server_id': ''}
    if (provider == 'codex' and state in ('missing', 'sign_in', 'configured', 'failed')
            and not _codex_drive_client(cap)):
        return {"state": "setup_required", "reason": "This Google integration requires a pre-registered Google OAuth client in Codex. Use its advanced setup guide or link an existing compatible integration; automatic registration cannot open a sign-in page.",
                "action": "setup", "server_id": registration_id(cap.get('id'))}
    reasons = {
        "missing": f"This connector has no registration in {title}.",
        "checking": f"Checking {title}'s own connection; other providers finish independently.",
        "starting": "Preparing connector sign-in…",
        "unknown": "The connection could not be verified. Recheck to try again.",
        "sign_in": f"Complete this connector's {title} sign-in, then recheck.",
        "failed": f"{title} could not connect. Check its authorization and service availability.",
        "configured": "Registered in this provider; authentication and live tools are not verified.",
        "different": "This server name has different settings. Review the provider configuration; ARMADA will not replace it.",
        "disabled": "The connector is disabled in this provider's configuration.",
        "unavailable": f"Connect {title} in Settings → App before connecting its tools.",
        "provider_disabled": f"{title} is disconnected in Settings → App.",
        "realm_disabled": "Enable this connector in the realm before connecting a provider.",
        "unsupported": "This integration has no reviewed direct MCP endpoint for this provider. Use a compatible integration to this service.",
        "ready": "This provider's live connection check passed.",
    }
    action = ""
    if state in ("unavailable", "provider_disabled"):
        action = "provider_settings"
    elif state not in ("checking", "starting", "realm_disabled"):
        if provider == "codex" and (codex_endpoint(cap) or cap.get('_bound_registration')) and state in ("missing", "sign_in", "configured", "failed"):
            action = "connect"
        elif provider == "claude" and (state in ("sign_in", "failed") or state == 'missing' and codex_endpoint(cap)):
            action = "connect"
        elif provider == 'gemini' and state == 'missing' and codex_endpoint(cap):
            action = 'connect'
        elif provider == 'gemini' and state == 'configured':
            action = 'authenticate'
        elif state != "ready":
            action = "setup"
    return {"state": state, "reason": error or reasons.get(state, reasons["unknown"]),
            "action": action, "server_id": str(cap.get("id") or "") if provider == "claude" else registration_id(cap.get("id"))}


def connection_snapshot(realm_root, *, force=False, provider=None) -> dict:
    """Nonblocking, independent provider checks; pending checks have a fixed deadline."""
    from . import capabilities, providers
    requested = (provider,) if provider else ('claude', 'codex', 'gemini')

    def probe(provider):
        try:
            state = providers.status(provider, force=True)
            connected = state.get("connected") is True
            detail = "ready" if connected else ("provider_disabled" if not state.get("enabled", True) else "unavailable")
        except Exception:
            logging.getLogger(__name__).exception('Provider availability check failed')
            connected, detail = False, "unknown"
        inventory = None
        if connected:
            try:
                if provider == 'gemini':
                    inventory = gemini_inventory()
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
        for target in ('claude', 'codex', 'gemini'):
            key = (str(Path(realm_root).resolve()), target, signature)
            check = _connection_checks.get(key)
            if provider is not None and target != provider:
                if check is None:
                    # A targeted recheck must not launch another provider, even
                    # when its cache is empty or expired.
                    future = Future()
                    future.set_result(('unknown', None, 'Recheck this provider to verify its connection.'))
                    check = {'future': future, 'started': now, 'finished': now}
                checks[target] = check
                continue
            refresh = force and (provider is None or target == provider)
            expired = check is not None and now-check['started'] >= _CHECK_DEADLINE
            if (check is None or (check['future'].done() and (refresh or now-check['finished'] >= _CHECK_CACHE_TTL))
                    or (refresh and expired)):
                check = {'future': Future(), 'started': now, 'finished': now}
                _connection_checks[key] = check
                def worker(provider=target, check=check):
                    try:
                        state, inventory = probe(provider)
                        result = (state, inventory, '')
                    except Exception as exc:
                        logging.getLogger(__name__).exception('Connector inventory check failed')
                        result = ('unknown', None, f'{type(exc).__name__}: {exc}')
                    check['finished'] = time.monotonic()
                    check['future'].set_result(result)
                threading.Thread(target=worker, daemon=True).start()
            checks[target] = check
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
            "codex_supported": bool(cap.get("id") and codex_endpoint(cap)),
            # Registration does not prove the Google connector's own authorization.
            "gemini": gemini_connection(cap, gemini_servers) if gemini_state == 'ready' else gemini_state,
            "errors": {**errors, "codex": errors['codex'] or (codex_servers or {}).get(registration_id(provider_cap(cap, 'codex')['id']), {}).get("runtime_error", "")},
        }
        if not capabilities.realm_enabled(cap):
            rows[sid].update({p: "realm_disabled" for p in states})
        from . import connector_login
        rows[sid]["details"] = {}
        for p in states:
            attempt = connector_login.state(_login_key(realm_root, provider_cap(cap, p), p))
            detail = connection_detail(cap, p, rows[sid][p], rows[sid]["errors"].get(p, ""))
            if (attempt and attempt['state'] != 'configured'
                    and rows[sid][p] not in ('ready', 'realm_disabled', 'provider_disabled', 'unavailable', 'different', 'disabled')):
                detail = connection_detail(cap, p, attempt['state'], attempt['reason'])
                if attempt.get('login_url'):
                    detail['login_url'] = attempt['login_url']
            rows[sid][p] = detail['state']
            detail['tool_names'] = ((codex_servers or {}).get(registration_id(provider_cap(cap, p)['id']), {}).get('tool_names', [])
                                    if p == 'codex' and detail['state'] == 'ready' else [])
            rows[sid]["details"][p] = detail
    pending = any(states[p] == 'checking' or any(r[p] == 'starting' for r in rows.values()) for p in requested)
    return {"providers": states, "connectors": rows, "pending": pending}


def is_provider_placeholder(cap: dict) -> bool:
    """Old auto-discovery filed the model app itself as a user MCP connector."""
    return (str(cap.get("id") or "").lower() in ("claude", "codex", "gemini")
            and cap.get("discovered") is True and not cap.get("command")
            and str(cap.get("scope") or "").lower() == "mcp server (claude)")


def connect_codex(cap: dict, realm_root=None) -> dict:
    """Register a reviewed realm endpoint and start Codex's own browser OAuth flow."""
    if cap.get('native_service') and provider_cap(cap, 'codex').get('_unbound'):
        from . import connector_registry, capabilities
        try:
            connector_registry.save(realm_root, capability=cap['id'], service=cap['native_service'])
            cap = capabilities.find(realm_root, cap['id'])[1]
        except (OSError, ValueError) as exc:
            return {'ok': False, 'error': str(exc)}
    cap = provider_cap(cap, 'codex')
    if cap.get('_native_app'):
        return open_native_setup(cap, 'codex')
    sid = registration_id(cap.get("id"))
    endpoint = codex_endpoint(cap)
    if cap.get('_unbound') or not cap.get("id") or (not endpoint and not cap.get('_bound_registration')):
        return {"ok": False, "error": "This connector has no supported Codex endpoint."}
    engine = CodexEngine()
    inventory = codex_live_inventory(realm_root, engine) if realm_root else codex_inventory(engine)
    if inventory is None:
        return {"ok": False, "error": "Could not inspect Codex MCP connections."}
    state = codex_connection(cap, inventory)
    if state in ("different", "disabled"):
        return {"ok": False, "error": "A Codex MCP server with this name already has different settings. Review it in Codex first."}
    if state == 'ready':
        return {"ok": True, "state": "ready"}
    if not _codex_drive_client(cap):
        return {"ok": False, "state": "setup_required", "error": connection_detail(cap, 'codex', state)['reason']}
    launcher = engine._launcher()
    if not launcher:
        return {"ok": False, "error": "Codex CLI is not installed."}
    if state == "missing":
        if not endpoint:
            return {'ok': False, 'error': 'The linked registration was removed from Codex. Import it again after configuring it there.'}
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
    from . import connector_login
    return connector_login.begin(_login_key(realm_root, cap, 'codex'),
                                 launcher + _feature_args() + ["mcp", "login", sid], cwd=realm_root,
                                 on_finish=lambda: _login_finished(realm_root, 'codex'))


def connect_claude(cap: dict, realm_root=None) -> dict:
    """Authenticate the existing Claude registration; never clone a cloud proxy."""
    from .engine.claude import ClaudeEngine
    cap = provider_cap(cap, 'claude')
    if cap.get('native_service') and cap.get('_unbound'):
        return open_native_setup(cap, 'claude')
    if cap.get('_unbound'):
        return {'ok': False, 'error': 'Link an existing Claude registration or choose a portable MCP integration.'}
    rows = _claude_rows(realm_root)
    if rows is None:
        return {"ok": False, "error": "Could not inspect Claude's connectors. Recheck Claude in App settings."}
    keys = {_identity(v) for v in (cap.get("id"), cap.get("name"), registration_id(cap.get("id")))}
    matches = [row for row in rows if _identity(row["name"]) in keys or
               _identity(server_id(row["name"])) in keys]
    engine = ClaudeEngine()
    launcher = engine._launcher()
    if not launcher:
        return {"ok": False, "error": "Claude Code CLI is not installed."}
    endpoint = codex_endpoint(cap)
    if not matches and endpoint:
        sid = registration_id(cap.get('id'))
        try:
            result = subprocess.run(launcher + ['mcp', 'add', '--scope', 'user', '--transport', 'http', sid, endpoint],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25,
                                    cwd=realm_root, env=engine._env(), **process_options())
        except (OSError, subprocess.SubprocessError):
            return {'ok': False, 'error': 'Claude could not register this endpoint. Recheck before retrying.'}
        if result.returncode:
            from .connector_login import _error
            return {'ok': False, 'error': _error(result.stderr) or 'Claude could not register this endpoint.'}
        _login_finished(realm_root, 'claude')
        # A public server needs no OAuth; ask the CLI rather than assuming it does.
        fresh = _claude_rows(realm_root) or []
        matches = [r for r in fresh if r['name'] == sid]
    if len(matches) != 1:
        return {"ok": False, "error": "Claude has no unique registration for this connector. Use Set up to review its configuration."}
    if endpoint and matches[0].get('endpoint') and matches[0]['endpoint'] != endpoint:
        return {'ok': False, 'error': 'Claude has different settings for this registration. ARMADA will not replace it.'}
    if matches[0]["ready"]:
        return {"ok": True, "state": "ready"}
    engine = ClaudeEngine()
    launcher = engine._launcher()
    if not launcher:
        return {"ok": False, "error": "Claude Code CLI is not installed."}
    from . import connector_login
    return connector_login.begin(_login_key(realm_root, cap, 'claude'),
                                 launcher + ["mcp", "login", matches[0]["name"]], cwd=realm_root, env=engine._env(),
                                 on_finish=lambda: _login_finished(realm_root, 'claude'))


_gemini_signins = {}
_gemini_signin_lock = threading.Lock()


def connect_gemini(cap, realm_root=None, *, authenticate=False):
    """Use the installed CLI's registration command and interactive /mcp authentication."""
    import os
    from .engine.gemini import GeminiEngine
    cap = provider_cap(cap, 'gemini')
    state = gemini_connection(cap, gemini_inventory())
    if state not in ('missing', 'configured'):
        return {'ok': False, 'error': connection_detail(cap, 'gemini', state)['reason']}
    engine = GeminiEngine()
    launcher = engine._launcher()
    if not launcher:
        return {'ok': False, 'error': 'Antigravity CLI is not installed.'}
    if state == 'missing':
        endpoint = codex_endpoint(cap)
        if not endpoint:
            return {'ok': False, 'error': 'Choose a portable MCP endpoint or import a Gemini registration.'}
        try:
            result = engine._probe(['mcp', 'add', '--type', 'http', registration_id(cap['id']), endpoint])
        except (OSError, subprocess.SubprocessError):
            return {'ok': False, 'error': 'Gemini registration did not finish. Recheck before retrying.'}
        if result.returncode:
            from .connector_login import _error
            return {'ok': False, 'error': _error(result.stderr) or 'Gemini could not register the connector.'}
        _login_finished(realm_root, 'gemini')
    if authenticate:
        key = _login_key(realm_root, cap, 'gemini')
        with _gemini_signin_lock:
            running = _gemini_signins.get(key)
            if running is None or running.poll() is not None:
                # This console is intentionally visible: the user's action opens the CLI's
                # MCP menu, where they select Authenticate and paste the browser callback.
                _gemini_signins[key] = subprocess.Popen(launcher + ['--prompt-interactive', '/mcp'],
                    cwd=realm_root, creationflags=0x00000010 if os.name == 'nt' else 0)
    return {'ok': True, 'state': 'configured', 'action': 'authenticate',
            'reason': 'Registered in Gemini. Open sign-in controls, select this server in /mcp and choose Authenticate. Registration alone does not verify live tools.'}


def open_native_setup(cap, provider):
    """The provider owns installation consent and OAuth; ARMADA never accepts either."""
    import webbrowser
    data = connector_setup(cap, provider)
    url = data.get('web_url')
    if not url:
        return {'ok': False, 'error': 'No native sign-in page is available for this provider.'}
    opened = webbrowser.open(url)
    return {'ok': True, 'state': 'sign_in', 'login_url': url, 'action': 'connect',
            'reason': data['instructions'] + ('' if opened else ' Use the sign-in link below to open the page.')}


def connector_setup(cap: dict, provider: str) -> dict:
    """Credential-free setup guidance for an approved connector, never evaluated as code."""
    guides = {"claude": "https://code.claude.com/docs/en/mcp",
              "codex": "https://developers.openai.com/codex/mcp",
              "gemini": "https://antigravity.google/docs/mcp"}
    if provider not in guides:
        return {"ok": False, "error": "Unknown connector provider."}
    cap = provider_cap(cap, provider)
    if cap.get('_native_app'):
        service = cap.get('native_service')
        from .connector_registry import NATIVE_SERVICES
        url = (f'https://chatgpt.com/plugins/{service}?open_in_app' if service in NATIVE_SERVICES else
               'https://chatgpt.com/apps')
        return {'ok': True, 'web_url': url, 'guide_url': 'https://learn.chatgpt.com/docs/plugins',
                'snippet': '', 'instructions': 'Open this native app using the same account as Codex CLI. Review its permissions, install and sign in there, then Recheck in ARMADA. You can also use /plugins in Codex CLI. No separate ARMADA OAuth client is needed.'}
    if cap.get('native_service') and provider == 'claude' and cap.get('_unbound'):
        return {'ok': True, 'web_url': 'https://claude.ai/settings/connectors', 'guide_url': guides['claude'],
                'snippet': '', 'instructions': 'Connect this service in Claude using the same account as Claude Code. Then choose Link connection in this row and select its Claude registration. The operations available depend on Claude’s connector.'}
    endpoint = codex_endpoint(cap)
    sid = registration_id(cap.get("id"))
    data = {"ok": True, "guide_url": guides[provider], "snippet": "", "web_url": "",
            "server_id": sid, "instructions": ""}
    if provider == "claude":
        managed = str(cap.get("id") or "").lower().startswith(("claude.ai ", "claude_ai_"))
        if managed:
            data.update(web_url="https://claude.ai/settings/connectors", instructions=
                "Add or reconnect this connector in Claude → Settings → Connectors using the same account as Claude Code. Then recheck here.")
        elif endpoint:
            quoted = "'" + endpoint.replace("'", "''") + "'"
            data.update(instructions="Add this direct MCP server to Claude Code, then authenticate with /mcp or claude mcp login. Recheck here afterward.",
                        snippet=f"claude mcp add --scope user --transport http {sid} {quoted}\nclaude mcp login {sid}")
        else:
            data["instructions"] = "Configure this connector in Claude using the provider's setup guide, then recheck here. ARMADA does not copy another provider's credentials."
    elif not endpoint:
        data["instructions"] = "This integration has no reviewed portable endpoint. Connect a supported MCP integration to the same service in this provider; an existing Claude sign-in cannot be reused."
    elif provider == "gemini":
        data.update(instructions="In Antigravity, open MCP Servers → Manage MCP Servers → View raw config. Merge this entry into ~/.gemini/config/mcp_config.json without replacing other servers. Complete any service-specific OAuth setup, then use /mcp to check the live connection. ARMADA verifies registration here, but cannot verify authentication or live tools.",
                    snippet=json.dumps({"mcpServers": {sid: {"serverUrl": endpoint}}}, indent=2))
    else:
        data.update(instructions="Merge this server entry into Codex's config.toml without replacing other servers, then use Connect and complete Codex's sign-in. Existing Claude authorization is not transferred.",
                    snippet=f'[mcp_servers.{sid}]\nurl = {json.dumps(endpoint)}')
    if endpoint in _GOOGLE_URLS:
        data["service_guide_url"] = "https://developers.google.com/workspace/guides/configure-mcp-servers"
        if provider == 'codex':
            data.update(instructions="Google Drive rejects automatic OAuth client registration. Create a Google Cloud OAuth client for Codex using the service guide, then configure it with codex mcp add --oauth-client-id (and --oauth-client-secret if required). Register the exact callback URL printed by Codex. This template shows the server entry; replace its placeholder before sign-in. ARMADA does not create OAuth credentials or reuse Claude's authorization.",
                        snippet=data['snippet'] + f'\n\n[mcp_servers.{sid}.oauth]\nclient_id = "YOUR_GOOGLE_OAUTH_CLIENT_ID"',
                        copy_label='Copy setup template')
    return data
