"""Claude Code sign-in state, and a way to fix it without leaving ARMADA.

When Claude Code's OAuth session lapses, *everything* stops: every agent run fails with
"Failed to authenticate", and usage reporting goes dark. The owner shouldn't have to discover that
from a log and then drop into a terminal — so ARMADA detects the state and can start the official
sign-in for them.

The boundary matters: ARMADA never sees, stores, or transports a credential. `claude auth login`
runs Claude Code's own flow in its own console window; the owner signs in through their browser and
Claude Code writes its own credentials file, exactly as if they'd typed the command themselves.
ARMADA only asks "are you signed in?" afterwards.

`claude auth status --json` is the authoritative answer — better than reading the credentials file,
because it also covers API-key and enterprise auth paths that never touch that file.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import time

from .engine.claude import ClaudeEngine, _NO_WINDOW
import logging
from .util import swallowed
log = logging.getLogger(__name__)

# A new visible console for the interactive login (Windows). The owner needs to SEE this one: it
# prints the verification URL and waits for the browser round-trip.
_NEW_CONSOLE = 0x00000010 if os.name == "nt" else 0

_CACHE: dict = {"at": 0.0, "data": None}
_TTL = 15.0          # short: the whole point is noticing a sign-in promptly


def _launcher():
    try:
        return ClaudeEngine()._launcher()
    except Exception:  # noqa — CLI missing/unresolvable
        log.debug('_launcher: failed; returning a fallback', exc_info=True)
        return None


def status(force: bool = False) -> dict:
    """{'ok': bool, 'logged_in': bool, 'method': str, 'reason': str}. Never raises."""
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL:
        return _CACHE["data"]
    out = _status_live()
    _CACHE["data"], _CACHE["at"] = out, now
    return out


def _status_live() -> dict:
    lp = _launcher()
    if not lp:
        return {"ok": False, "logged_in": False, "method": "", "reason": "cli-missing"}
    try:
        r = subprocess.run(lp + ["auth", "status", "--json"], capture_output=True, text=True,
                           timeout=25, encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    except Exception as e:  # noqa
        swallowed(log, '_status_live: failed; error returned to the caller')
        return {"ok": False, "logged_in": False, "method": "", "reason": f"probe-failed: {e}"[:120]}
    # Exit code is non-zero when signed out, so parse the payload rather than trusting returncode.
    try:
        d = json.loads((r.stdout or "").strip() or "{}")
    except Exception:  # noqa
        swallowed(log, '_status_live: failed; using a default')
        d = None
    if not isinstance(d, dict):      # valid JSON that isn't an object ("null", a list, a number)
        return {"ok": False, "logged_in": False, "method": "", "reason": "unreadable-status"}
    # `plan` (Claude Code's subscriptionType: pro, max, team, enterprise…) lets the setup wizard say
    # whether agents can run on this account; the free plan has no Claude Code access.
    return {"ok": True, "logged_in": bool(d.get("loggedIn")),
            "method": str(d.get("authMethod") or ""), "reason": "",
            "plan": str(d.get("subscriptionType") or ""), "version": _version(lp)}


def _version(lp) -> str:
    """Claude Code's version ("2.1.263"), or "" if it won't say. `claude --version` prints
    "2.1.263 (Claude Code)"."""
    try:
        r = subprocess.run(lp + ["--version"], capture_output=True, text=True, timeout=20,
                           encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"\d+\.\d+\.\d+", r.stdout or "")
    return m.group(0) if m else ""


def version_ok(version: str, minimum: str) -> bool:
    """Is `version` at least `minimum`? An unknown version is given the benefit of the doubt."""
    def parts(v):
        return tuple(int(x) for x in re.findall(r"\d+", v)[:3])
    return not version or parts(version) >= parts(minimum)


def start_login(console: bool = True) -> dict:
    """Launch Claude Code's own sign-in. Returns once it's STARTED, not once it's finished — the
    owner completes it in their browser, then ARMADA re-checks status."""
    lp = _launcher()
    if not lp:
        return {"ok": False, "error": "The Claude CLI isn't available on this machine."}
    try:
        # A visible console on purpose: the flow prints a URL and waits. Hiding it would strand the
        # owner with a browser page and no way to see what the CLI is asking for.
        flags = (_NEW_CONSOLE if console else _NO_WINDOW) if os.name == "nt" else 0
        subprocess.Popen(lp + ["auth", "login", "--claudeai"], creationflags=flags)
        _CACHE["data"] = None          # force a fresh read on the next poll
        return {"ok": True}
    except Exception as e:  # noqa
        swallowed(log, 'start_login: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:200]}
