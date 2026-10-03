"""App-wide provider connections. Credentials remain with the official CLIs.

Rendering reads the last observation; explicit status requests probe the CLIs. Disconnecting
blocks new Armada calls without signing other applications out or changing stored agent models.
"""
from __future__ import annotations

import threading

from . import appconfig, util

NAMES = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini"}
_lock = threading.RLock()


def _check(provider):
    if provider not in NAMES:
        raise ValueError("Unknown provider")


def allowed(provider):
    if provider not in NAMES:
        return True
    return appconfig.get("provider_connections", {}).get(provider, {}).get("enabled", True) is True


def require_allowed(provider):
    if not allowed(provider):
        raise ValueError(f"{NAMES[provider]} is disconnected from Armada. Reconnect in Settings → App.")


def _save(provider, **values):
    path = appconfig._path()
    with util.file_lock(path):
        cfg = appconfig.load()
        connections = cfg.setdefault("provider_connections", {})
        connections.setdefault(provider, {}).update(values)
        util.write_json_atomic(path, cfg)


def connected():
    """Last confirmed usable connections, without running a CLI during rendering."""
    states = appconfig.get("provider_connections", {})
    return [p for p in NAMES if states.get(p, {}).get("enabled", True)
            and states.get(p, {}).get("logged_in") is True]


def observed():
    return bool(appconfig.get("provider_connections", {}))


def status(provider, force=False):
    _check(provider)
    from .engine import get_engine
    from . import provider_login, provider_install
    installed = bool(get_engine(provider)._launcher())
    if provider == "claude":
        from . import auth
        from .alexander import MIN_CLAUDE_CODE
        raw = dict(auth.status(force=force))
        raw["version_ok"] = auth.version_ok(raw.get("version", ""), MIN_CLAUDE_CODE)
        raw["min_version"] = MIN_CLAUDE_CODE
    else:
        eng = get_engine(provider)
        raw = (eng.auth_status(force=force) if provider == "gemini" else eng.auth_status()) if eng._launcher() else {
            "ok": True, "logged_in": False, "reason": "cli-missing", "method": ""}
        if installed:
            import subprocess
            try:
                import re
                version = eng._probe(["--version"])
                match = re.search(r"\b\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?", version.stdout)
                raw["version"] = match.group() if version.returncode == 0 and match else ""
            except (OSError, subprocess.SubprocessError):
                raw["version"] = ""
    logged = installed and raw.get("ok") is True and raw.get("logged_in") is True
    usable = logged and raw.get("version_ok", True)
    with _lock:
        # Read enabled inside the update so a late login poll cannot undo Disconnect.
        _save(provider, logged_in=bool(usable), **({"models": raw["models"]} if provider == "gemini" and usable and raw.get("models") else {}))
        enabled = allowed(provider)
    login = provider_login.state(provider)
    installation = provider_install.state(provider)
    return {**raw, **login, "provider": provider, "enabled": enabled, "installed": installed,
            "installing": installation.get("pending", False), "install_error": installation.get("error", ""),
            "pending": login["pending"] and enabled and not logged,
            "connected": bool(enabled and usable)}


def statuses(force=False):
    # A status request is I/O, not a page-render dependency.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(NAMES)) as pool:
        return dict(zip(NAMES, pool.map(lambda p: status(p, force), NAMES)))


def disconnect(provider):
    _check(provider)
    from . import provider_login
    with _lock:
        _save(provider, enabled=False)
        provider_login.cancel(provider)
    return {"ok": True, "provider": provider, "connected": False}


def connect(provider):
    """Use an existing CLI login, or launch the CLI's browser OAuth flow without a console."""
    _check(provider)
    from pathlib import Path
    from . import provider_login
    import os
    # Codex requires an explicitly configured home to exist before any CLI command.
    # Do not change the configured location or touch credential contents.
    if provider == "codex" and os.environ.get("CODEX_HOME"):
        Path(os.environ["CODEX_HOME"]).mkdir(parents=True, exist_ok=True)
    state = status(provider, force=True)
    if not state["installed"]:
        return {"ok": False, "error": f"Install {NAMES[provider]} CLI before signing in.", "reason": "cli-missing"}
    if state.get("version_ok") is False:
        return {"ok": False, "error": f"Update Claude Code to {state['min_version']} or newer before signing in."}
    if state.get("logged_in") and state.get("version_ok", True):
        with _lock:
            _save(provider, enabled=True, logged_in=True)
        return {"ok": True, "connected": True}
    from .engine import get_engine
    engine = get_engine(provider)
    launcher = engine._launcher()
    if not launcher:
        return {"ok": False, "error": f"Install {NAMES[provider]} CLI first.", "reason": "cli-missing"}
    with _lock:
        result = provider_login.begin(provider, launcher)
        if result.get("ok"):
            _save(provider, enabled=True, logged_in=False)
        return result
