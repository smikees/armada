"""Read the real Claude subscription usage (session + weekly) that powers the Claude app's Usage view.

ARMADA runs agents through Claude Code on the owner's Max/Pro subscription, so the OAuth token Claude
Code stores locally is enough to query Anthropic's (undocumented) usage endpoint — the same one the
`/usage` view uses. We show the current 5-hour session and 7-day weekly utilisation as % of limit,
with reset times. Anthropic publishes no token-denominated limits, so these percentages ARE the limit
comparison; the widget's per-agent/per-model token tally (from local run telemetry) is separate.

Deliberately READ-ONLY and best-effort: we read the credentials file but never write it, never refresh
the token, and never raise. Undocumented endpoint; may change without notice.

**Why we never refresh the token ourselves.** The credentials file holds a refresh token, so minting
a fresh access token would be easy — and is a trap. If Anthropic rotates refresh tokens on use (the
usual practice), consuming one without writing the replacement back would invalidate Claude Code's
stored credential and break the owner's sign-in; writing it back means this app mutating another
application's credential store. Instead the `usage-keepalive` system job makes a trivial Claude Code
call every few hours, and Claude Code refreshes its own token as a side effect. Measured: one 5-second
call extended expiry by ~18 hours.

**Why the last reading is kept on disk.** An access token lives ~12-18 hours. Before, an expired one
meant the bars vanished entirely — not stale, *gone* — which is a worse answer than a slightly old
number, because a blank header tells the owner nothing at all. We now persist each successful reading
and serve it with its age when the live call fails, so the figures are always on screen. `age_sec`
and `stale` are on every served payload; the UI decides how loudly to caveat.
"""
from __future__ import annotations
import json
import time
import urllib.request
from pathlib import Path
import logging
from .util import swallowed
log = logging.getLogger(__name__)

_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
_UA = "claude-code/2.0.32 (ARMADA)"
_BETA = "oauth-2025-04-20"
_CREDS = Path.home() / ".claude" / ".credentials.json"

_CACHE: dict = {"at": 0.0, "data": None}
_TTL = 60.0   # seconds — one live subscription; don't hammer the endpoint on every widget load

_DISK = "usage-last.json"      # in the realm, beside the other system-job state
_KEEP_FOR = 7 * 24 * 3600.0    # older than a week is history, not a reading


def _read_token() -> tuple[str, int] | None:
    """(access_token, expires_at_ms) from Claude Code's credentials, or None if unreadable."""
    try:
        raw = json.loads(_CREDS.read_text("utf-8"))
        o = raw.get("claudeAiOauth") or {}
        tok = o.get("accessToken")
        exp = int(o.get("expiresAt") or 0)
        if tok:
            return tok, exp
    except Exception:  # noqa — missing/locked/malformed all mean "no usable token"
        log.debug('_read_token: failed; ignored', exc_info=True)
    return None


def _countdown(resets_at: str) -> str:
    """'2h 10m' / '3d 4h' until an ISO reset time (best-effort; '' if unparseable)."""
    import datetime as _dt
    try:
        s = resets_at.replace("Z", "+00:00")
        when = _dt.datetime.fromisoformat(s)
        now = _dt.datetime.now(when.tzinfo)
        secs = int((when - now).total_seconds())
        if secs <= 0:
            return "now"
        d, rem = divmod(secs, 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        if d:
            return f"{d}d {h}h"
        if h:
            return f"{h}h {m}m"
        return f"{m}m"
    except Exception:  # noqa
        log.debug('_countdown: failed; returning a fallback', exc_info=True)
        return ""


def _window(d: dict) -> dict | None:
    if not isinstance(d, dict):
        return None
    resets = d.get("resets_at") or ""
    return {"pct": round(float(d.get("utilization") or 0)),
            "resets_at": resets, "resets_in": _countdown(resets)}


def _fetch_live() -> dict:
    tok = _read_token()
    if not tok:
        return {"available": False, "reason": "no-credentials"}
    access, exp_ms = tok
    if exp_ms and exp_ms <= int(time.time() * 1000) + 30_000:
        # Claude Code refreshes this on the next agent run; we never write it ourselves.
        return {"available": False, "reason": "token-expired"}
    req = urllib.request.Request(_ENDPOINT, headers={
        "Authorization": f"Bearer {access}", "anthropic-beta": _BETA, "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=4.0) as r:
            body = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa — network/auth/parse: report unavailable, never crash the page
        log.debug('_fetch_live: failed; error returned to the caller', exc_info=True)
        return {"available": False, "reason": "fetch-failed", "detail": str(e)[:120]}
    if isinstance(body, dict) and body.get("error"):
        return {"available": False, "reason": "api-error"}
    session, weekly = _window(body.get("five_hour")), _window(body.get("seven_day"))
    if not session and not weekly:
        return {"available": False, "reason": "unexpected-shape"}
    return {"available": True, "session": session, "weekly": weekly}


# Why the bars aren't showing, in the owner's words. The UI renders whatever `message` we send, so
# every unavailable reason MUST appear here — a reason with no message is how the header silently
# went blank (no bars, no explanation) when the stored OAuth token was emptied.
_REASONS = {
    "no-credentials": "Claude Code is signed out, so usage can’t be read — use the Sign in "
                      "button at the top of the window.",
    "token-expired": "Claude Code's sign-in needs renewing — the keepalive job does that every few "
                     "hours, or any agent run will.",
    "fetch-failed": "Couldn’t reach Anthropic for usage just now — it’ll retry shortly.",
    "api-error": "Anthropic declined the usage request. If agent runs are failing too, sign in "
                 "again from the banner at the top of the window.",
    "unexpected-shape": "Anthropic returned usage in a shape ARMADA doesn’t recognise — this "
                        "endpoint is undocumented and may have changed.",
    "error": "Usage is temporarily unavailable.",
}
_FALLBACK_MESSAGE = "Claude usage is unavailable right now."


def message_for(reason: str) -> str:
    """The owner-facing line for an unavailable reason. Never empty, even for a reason we've not
    seen before — silence is the one outcome that leaves someone staring at a blank header."""
    return _REASONS.get(str(reason or ""), _FALLBACK_MESSAGE)


def _normalise(d: dict) -> dict:
    """Guarantee the contract the UI relies on: unavailable results always carry a `message`."""
    if not isinstance(d, dict):
        return {"available": False, "reason": "error", "message": message_for("error")}
    if not d.get("available"):
        d["available"] = False               # state it outright; absent ≠ False for a caller
        d.setdefault("reason", "error")
        d["message"] = message_for(d.get("reason"))
    return d


def _disk_path(realm_root) -> Path | None:
    try:
        return Path(realm_root) / _DISK if realm_root else None
    except Exception:  # noqa
        log.debug('_disk_path: failed; returning a fallback', exc_info=True)
        return None


def _remember(realm_root, data: dict) -> None:
    """Persist a good reading so an expired token doesn't blank the header."""
    p = _disk_path(realm_root)
    if p is None or not data.get("available"):
        return
    try:
        from . import util
        util.write_json_atomic(p, {"at": time.time(), "data": data})
    except Exception:  # noqa — a cache that can't be written is not an error worth surfacing
        swallowed(log, '_remember: failed; ignored')


def _recall(realm_root) -> tuple[dict, float] | None:
    """(data, age_seconds) from the last good reading, or None if absent/stale/unreadable."""
    p = _disk_path(realm_root)
    if p is None:
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
        at, data = float(raw.get("at") or 0), raw.get("data")
        age = time.time() - at
        if at and isinstance(data, dict) and data.get("available") and 0 <= age <= _KEEP_FOR:
            return data, age
    except Exception:  # noqa
        log.debug('_recall: failed; ignored', exc_info=True)
    return None


def _as_of(data: dict, age: float, reason: str) -> dict:
    """A remembered reading, labelled honestly. The percentages are real but old, and the reset
    countdowns are NOT recomputed — a countdown from a stale reading would be actively wrong."""
    out = dict(data)
    out["age_sec"] = int(age)
    out["stale"] = True
    out["stale_reason"] = reason
    for k in ("session", "weekly"):
        w = out.get(k)
        if isinstance(w, dict):
            w = dict(w)
            w.pop("resets_in", None)     # recomputing this from an old reading would mislead
            out[k] = w
    out["message"] = ("Showing the last reading — " + _AGE_NOTE(age) + ". " +
                      message_for(reason))
    return out


def _AGE_NOTE(age: float) -> str:  # noqa: N802 — small formatter, kept beside its only caller
    m = int(age // 60)
    if m < 60:
        return f"{max(m, 1)} min old"
    h = m // 60
    return f"{h}h old" if h < 48 else f"{h // 24}d old"


def fetch(realm_root=None) -> dict:
    """Cached (60s) real usage: {available, session:{pct,...}, weekly:{...}, age_sec, stale} or
    {available:False, reason, message}.

    A live reading always wins. When the live call fails — almost always an expired token between
    agent runs — the last good reading is served with its age rather than nothing at all.
    """
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL:
        return _CACHE["data"]
    data = _normalise(_fetch_live())
    if data.get("available"):
        data["age_sec"] = 0
        data["stale"] = False
        _remember(realm_root, data)
    else:
        prev = _recall(realm_root)
        if prev:
            data = _as_of(prev[0], prev[1], data.get("reason") or "error")
    # cache positive results for the full TTL; cache "unavailable" briefly so an expired token that
    # a run is about to refresh gets retried soon rather than staying dark for a full minute.
    _CACHE["data"] = data
    _CACHE["at"] = now if not data.get("stale") else now - (_TTL - 10)
    return data
