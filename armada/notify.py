"""Desktop notifications — native Windows toasts, best-effort.

ARMADA already knows when things happen (the runner writes run markers and reports; the approvals
inbox knows what's waiting). This module is only the delivery layer: turn an event into a toast.

Design rules, in order of importance:

1. **A notification must never affect a run.** Every entry point swallows its own errors and the
   send happens on a daemon thread, so a missing PowerShell, a locked desktop or a slow COM call
   can't delay or fail a job. Notifying is the least important thing ARMADA does.
2. **No new dependencies.** Toasts go through PowerShell's WinRT bridge, which is present on every
   Windows 10/11 box. ARMADA stays stdlib-only.
3. **Quiet by construction.** Identical events collapse inside a short window (see _DEDUPE_SEC) on
   every channel that interrupts you — desktop and Telegram — so a job retrying in a loop can't
   carpet either. The in-app feed is never collapsed: it is the record, not an interruption.

Attribution comes from the AppUserModelID that app.py already sets on the process, so toasts show
as "ARMADA" with its icon rather than as pythonw or PowerShell.
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path  # noqa: F401 — used by the feed helpers below
from .util import swallowed

log = logging.getLogger("armada.notify")

# Must match app.py's _APP_ID — that's what makes Windows label the toast "ARMADA".
APP_ID = "Stamih.ARMADA.App"

# Where a notification can go. In-app is the bell's archive, desktop is a Windows toast, Telegram
# reaches you away from this machine. Order here is the column order in Settings.
CHANNELS = {
    "inapp": "In-app",
    "desktop": "Desktop",
    "telegram": "Telegram",
}

# Event kinds, grouped the way the rest of the app splits things: work your agents do, versus
# ARMADA keeping itself running. Keys are stable — they're persisted in realm.json.
#
# `default` is a per-channel starting point rather than a hard rule. There's no longer a category of
# event that *can't* reach the desktop; there are events that don't by default, and you can say
# otherwise. The defaults encode one judgement: interrupt only for things that need a person.
AGENTS, SYSTEM = "agents", "system"
EVENTS = {
    "job_started": {
        "label": "A job starts", "group": AGENTS,
        # the bulk of the traffic in any real realm, and nothing to act on — off everywhere
        "default": {"inapp": False, "desktop": False, "telegram": False}},
    "job_finished": {
        "label": "An agent finishes a task", "group": AGENTS,
        "default": {"inapp": True, "desktop": True, "telegram": False}},
    "job_failed": {
        "label": "A job fails", "group": AGENTS,
        "default": {"inapp": True, "desktop": True, "telegram": True}},
    "approval_needed": {
        "label": "Something needs my approval", "group": AGENTS,
        "default": {"inapp": True, "desktop": True, "telegram": True}},
    "inbox_task": {
        "label": "An agent takes on a task from another agent", "group": AGENTS,
        # work happening without you asking for it — worth recording, not worth interrupting
        "default": {"inapp": True, "desktop": False, "telegram": False}},
    "inbox_failed": {
        "label": "An agent can't complete a delegated task", "group": AGENTS,
        "default": {"inapp": True, "desktop": True, "telegram": False}},
    "signed_out": {
        # engine-neutral wording: this will cover whichever engine a realm runs on
        "label": "Engine sign-in required (everything stops)", "group": SYSTEM,
        # this one halts every agent you have; it earns an interruption wherever you are
        "default": {"inapp": True, "desktop": True, "telegram": True}},
    "update_available": {
        "label": "A capability has an update", "group": SYSTEM,
        "default": {"inapp": True, "desktop": False, "telegram": False}},
    "capability_found": {
        "label": "A new capability is discovered", "group": SYSTEM,
        "default": {"inapp": True, "desktop": False, "telegram": False}},
    "system_job_failed": {
        "label": "A system job fails", "group": SYSTEM,
        "default": {"inapp": True, "desktop": False, "telegram": False}},
}
ALL_EVENTS = {k: v["label"] for k, v in EVENTS.items()}

# The in-app archive. Append-only JSONL beside the realm, trimmed to _FEED_MAX so it can't grow
# without bound; the bell shows the tail of it.
_FEED_NAME = "notifications.jsonl"
_STATE_NAME = "notifications.state.json"
_FEED_MAX = 300

_DEDUPE_SEC = 20.0
_recent: dict = {}
_lock = threading.Lock()
_feed_lock = threading.Lock()

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# PowerShell reads the toast text from stdin as JSON, so no user text is ever interpolated into the
# script source — titles containing quotes, $, or backticks can't break or inject into it.
_PS = r"""
$ErrorActionPreference='Stop'
$raw = [Console]::In.ReadToEnd()
$o = $raw | ConvertFrom-Json
$null=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]
$null=[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime]
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml('<toast><visual><binding template="ToastGeneric"><text id="1"></text><text id="2"></text></binding></visual></toast>')
$t = $doc.GetElementsByTagName('text')
$t.Item(0).AppendChild($doc.CreateTextNode([string]$o.title)) | Out-Null
$t.Item(1).AppendChild($doc.CreateTextNode([string]$o.body))  | Out-Null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier([string]$o.appid).Show(
    [Windows.UI.Notifications.ToastNotification]::new($doc))
"""


# Channel switches are per MACHINE (App settings) — whether this computer shows toasts at all is a
# property of the computer. Which events matter is per REALM. Telegram starts off because it needs
# credentials before it can do anything.
_CHANNEL_DEFAULT = {"inapp": True, "desktop": True, "telegram": False}


# Setting this in the environment mutes the channels that leave this MACHINE — currently Telegram.
# The in-app feed still records and the desktop still toasts: those reach whoever is already at the
# computer, which is not the same as reaching someone's phone.
#
# It exists because the credentials are global by design. They sit outside every realm so that a
# realm export can't carry a bot token to another machine — and the same property means ANY realm
# can reach the owner's phone, including a throwaway one a test invented in a temp folder. For test
# runs, CI, and dry runs against a scratch realm.
MUTE_ENV = "ARMADA_NO_EXTERNAL_NOTIFY"
_MUTES = ("telegram",)


def muted() -> bool:
    """Are off-machine channels muted for this process?"""
    return str(os.environ.get(MUTE_ENV, "")).strip().lower() not in ("", "0", "false", "no")


def channel_enabled(channel: str) -> bool:
    """Is this delivery channel switched on for this machine?"""
    if channel in _MUTES and muted():
        return False
    try:
        from . import appconfig
        return bool(appconfig.get(f"notify_{channel}", _CHANNEL_DEFAULT.get(channel, True)))
    except Exception:  # noqa — unreadable config must not silence everything
        swallowed(log, 'channel_enabled: failed; returning a fallback')
        return _CHANNEL_DEFAULT.get(channel, True)


def channels_enabled() -> dict:
    return {c: channel_enabled(c) for c in CHANNELS}


def desktop_enabled() -> bool:
    return channel_enabled("desktop")


def telegram_enabled() -> bool:
    return channel_enabled("telegram")


def default_matrix() -> dict:
    return {ev: dict(meta["default"]) for ev, meta in EVENTS.items()}


def matrix(realm_root) -> dict:
    """The event × channel grid for this realm, defaults filled in.

    Understands the older flat shape ({"job_failed": true}), which predated channels: back then one
    switch governed both the bell and the desktop, so that's how it's read forward. Nobody's saved
    preferences get silently reset by the upgrade.
    """
    out = default_matrix()
    try:
        js = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
        cfg = (js.get("notifications") or {})
    except Exception:  # noqa — unreadable realm: defaults, never raise
        swallowed(log, 'matrix: failed; returning a fallback')
        return out
    if cfg.get("enabled") is False:      # legacy realm-wide master switch, kept working
        return {ev: {c: False for c in CHANNELS} for ev in EVENTS}
    grid = cfg.get("matrix")
    if isinstance(grid, dict):
        for ev, row in grid.items():
            if ev in out and isinstance(row, dict):
                for c in CHANNELS:
                    if c in row:
                        out[ev][c] = bool(row[c])
        return out
    for ev in EVENTS:                    # legacy flat booleans
        if ev in cfg and not isinstance(cfg[ev], dict):
            on = bool(cfg[ev])
            out[ev]["inapp"] = on
            out[ev]["desktop"] = on
    return out


# Channels that reach you when you are not looking at the realm that raised them. The in-app feed
# is not one: it lives inside the realm and is only ever read by someone already there, so gating
# it on "are you viewing this realm" would only ever hide history from the person who came looking.
_OFF_REALM = ("desktop", "telegram")
CROSS_REALM_DEFAULT = True


def cross_realm(realm_root) -> bool:
    """May this realm interrupt you while you are viewing a different one?

    Jobs fire in every realm regardless of which one is on screen, so by default their
    notifications follow — a failure at 3am in the realm you are not looking at is exactly the one
    you need to hear about. Switch it off for a realm whose chatter you only want while you are
    actually in it.
    """
    try:
        js = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
        v = (js.get("notifications") or {}).get("cross_realm")
    except Exception:  # noqa — an unreadable realm must not go silent
        swallowed(log, 'cross_realm: failed; returning a fallback')
        return CROSS_REALM_DEFAULT
    return CROSS_REALM_DEFAULT if v is None else bool(v)


def is_active_realm(realm_root) -> bool:
    """Is this the realm the app is currently in?

    "Nothing recorded yet" counts as yes. A machine that has never opened the app would otherwise
    silence every realm on it, which is the opposite of what an unset preference should do.
    """
    try:
        from . import activerealm
        cur = activerealm.remembered()
        return True if not cur else Path(cur).resolve() == Path(realm_root).resolve()
    except Exception:  # noqa
        swallowed(log, 'is_active_realm: failed; returning a fallback')
        return True


def realm_label(realm_root) -> str:
    """The realm's display name, for saying WHICH realm a notification came from."""
    try:
        js = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
        name = str(js.get("name") or "").strip()
    except Exception:  # noqa
        swallowed(log, 'realm_label: failed; using a default')
        name = ""
    return name or Path(str(realm_root)).name


def _titled(realm_root, title: str) -> str:
    """Prefix a notification with its realm.

    Once jobs fire in every realm, "Warren: job failed" on a phone raises the question of which
    Warren — and the answer is not recoverable from the message. The prefix is only added on the
    channels that leave the realm; inside the app the feed you are reading IS the realm.
    """
    if realm_root is None:
        return title
    name = realm_label(realm_root)
    t = str(title or "")
    return f"{name} · {t}" if name and not t.startswith(f"{name} ·") else t


def wants(realm_root, event: str, channel: str) -> bool:
    """Should this event reach this channel? Every switch has to agree: the machine has to have the
    channel on, the realm has to want this kind there, and — for channels that reach you outside
    the realm — the realm has to be allowed to interrupt you while you're elsewhere."""
    if not channel_enabled(channel):
        return False
    if realm_root is None:
        return bool(EVENTS.get(event, {}).get("default", {}).get(channel, False))
    if channel in _OFF_REALM and not cross_realm(realm_root) and not is_active_realm(realm_root):
        return False
    return bool(matrix(realm_root).get(event, {}).get(channel, False))


def enabled_events(realm_root) -> dict:
    """Back-compat view: is this event enabled on ANY channel?"""
    m = matrix(realm_root)
    return {ev: any(m.get(ev, {}).values()) for ev in EVENTS}


def _dedupe(key: str) -> bool:
    """True if this exact event fired very recently (so we should stay quiet)."""
    now = time.monotonic()
    with _lock:
        for k, t in list(_recent.items()):        # cheap sweep; this dict stays tiny
            if now - t > _DEDUPE_SEC * 3:
                _recent.pop(k, None)
        if now - _recent.get(key, -1e9) < _DEDUPE_SEC:
            return True
        _recent[key] = now
    return False


def _send(title: str, body: str) -> None:
    payload = json.dumps({"title": title[:120], "body": body[:250], "appid": APP_ID})
    try:
        p = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", creationflags=_NO_WINDOW)
        _, err = p.communicate(payload, timeout=20)
        if p.returncode != 0:
            log.debug("toast failed: %s", (err or "").strip()[:200])
    except Exception as e:  # noqa — notifications are never worth an exception
        log.debug("toast failed: %s", e)


def _feed_path(realm_root) -> Path:
    return Path(realm_root) / _FEED_NAME


def _state_path(realm_root) -> Path:
    return Path(realm_root) / _STATE_NAME


def _now() -> str:
    """Timestamps carry microseconds on purpose. Read state is 'everything up to this instant', so
    at one-second resolution a notification arriving in the same second you hit Mark all read would
    be counted as already seen — and vanish from the unread badge without you ever seeing it."""
    import datetime as _dt
    return _dt.datetime.now().astimezone().isoformat(timespec="microseconds")


def _safe_href(href: str) -> str:
    """Keep links pointing inside ARMADA.

    Notification text is built from agent and job names, so treat the destination as untrusted:
    only a same-origin absolute path is allowed. That rules out `javascript:` and any off-site URL,
    including protocol-relative ones like `//evil.example`.
    """
    h = str(href or "").strip()
    if not h.startswith("/") or h.startswith("//"):
        return ""
    return h[:300]


def record(realm_root, event: str, title: str, body: str = "", href: str = "") -> dict | None:
    """Append one entry to the in-app feed. Best-effort; returns the entry or None.

    `href` is where the notification leads — the thread that produced the output, the job that
    failed, the approvals queue. Kept as an in-app path so a notification is one click from the
    thing it's about instead of a description of it.
    """
    if realm_root is None:
        return None
    item = {"ts": _now(), "event": str(event or ""),
            "title": str(title or "")[:160], "body": str(body or "")[:400],
            "href": _safe_href(href)}
    try:
        p = _feed_path(realm_root)
        with _feed_lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            _trim(p)
        return item
    except Exception:  # noqa — the feed is a convenience; never break a run over it
        swallowed(log, 'record: failed; returning a fallback')
        return None


def _trim(p: Path) -> None:
    """Keep the file bounded. Cheap: only rewrites once it's meaningfully over the cap."""
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        if len(lines) > _FEED_MAX + 50:
            p.write_text("\n".join(lines[-_FEED_MAX:]) + "\n", encoding="utf-8")
    except Exception:  # noqa
        swallowed(log, '_trim: failed; ignored')


def feed(realm_root, limit: int = 50) -> list:
    """Most recent entries first. Never raises — a missing or corrupt feed reads as empty."""
    try:
        lines = _feed_path(realm_root).read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa
        log.debug('feed: failed; returning a fallback', exc_info=True)
        return []
    out = []
    for ln in reversed(lines):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
            if isinstance(d, dict):
                out.append(d)
        except Exception:  # noqa — skip a torn line rather than losing the whole feed
            log.debug('feed: failed; skipping this one', exc_info=True)
            continue
        if len(out) >= limit:
            break
    return out


RETAIN_DAYS = 7      # a notification is stale within hours; a week is already generous


def prune(realm_root, days: int = RETAIN_DAYS) -> int:
    """Drop entries older than `days`. Returns how many went. Age is the right axis for history —
    a count cap silently loses today's notifications on a busy realm."""
    cutoff = (_dt_now() - _dt_timedelta(days=days)).isoformat()
    try:
        p = _feed_path(realm_root)
        with _feed_lock:
            lines = p.read_text(encoding="utf-8").splitlines()
            kept = []
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    if str(json.loads(ln).get("ts", "")) >= cutoff:
                        kept.append(ln)
                except Exception:  # noqa — drop torn lines while we're here
                    log.debug('prune: failed; skipping this one', exc_info=True)
                    continue
            removed = len(lines) - len(kept)
            if removed > 0:
                p.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
            return max(0, removed)
    except Exception:  # noqa — nothing to prune / unreadable
        log.debug('prune: failed; returning a fallback', exc_info=True)
        return 0


def _dt_now():
    import datetime as _dt
    return _dt.datetime.now().astimezone()


def _dt_timedelta(**kw):
    import datetime as _dt
    return _dt.timedelta(**kw)


def last_read(realm_root) -> str:
    try:
        return str(json.loads(_state_path(realm_root).read_text(encoding="utf-8")).get("last_read") or "")
    except Exception:  # noqa
        log.debug('last_read: failed; returning a fallback', exc_info=True)
        return ""


def mark_read(realm_root) -> dict:
    """Mark everything currently in the feed as seen."""
    items = feed(realm_root, limit=1)
    newest = items[0]["ts"] if items else _now()
    try:
        from . import util
        util.write_json_atomic(_state_path(realm_root), {"last_read": newest})
    except Exception:  # noqa
        swallowed(log, 'mark_read: failed; error returned to the caller')
        return {"ok": False}
    return {"ok": True, "last_read": newest}


def unread_count(realm_root, items=None) -> int:
    lr = last_read(realm_root)
    items = feed(realm_root) if items is None else items
    return sum(1 for i in items if str(i.get("ts", "")) > lr)


def emit(realm_root, event: str, title: str, body: str = "", href: str = "") -> dict:
    """The one way ARMADA announces something: archive it in the app, and — for the event kinds
    that warrant interrupting — also raise a desktop notification.

    Every channel is decided independently from the event × channel grid, so "tell me in the app
    but don't interrupt me" and "wake me on Telegram for this one only" are both expressible.
    """
    recorded = toasted = sent = False
    if wants(realm_root, event, "inapp"):
        recorded = record(realm_root, event, title, body, href) is not None
    if wants(realm_root, event, "desktop"):
        toasted = toast(title, body, realm_root=realm_root, event=event)
    if wants(realm_root, event, "telegram"):
        sent = _send_telegram(realm_root, event, title, body, href)
    return {"recorded": recorded, "toasted": toasted, "sent": sent}


def _send_telegram(realm_root, event: str, title: str, body: str, href: str) -> bool:
    """Push a notification to the linked Telegram chat.

    The href is a localhost URL, useless on a phone, so it's dropped rather than sent as a dead
    link. Silent when Telegram isn't set up: an unconfigured channel is not an error."""
    try:
        from . import telegram as _tg
        if not _tg.ready():
            return False
        # The same collapse the desktop channel has always had. It was never applied here, though
        # this is the channel that follows you out of the building: a job retrying in a loop could
        # carpet a phone while being politely quiet on the machine standing next to it. Keys are
        # channel-scoped so one channel's suppression can't silence the other.
        if _dedupe(f"telegram|{event}|{title}|{body}"):
            return False
        title = _titled(realm_root, title)
        text = str(title or "").strip()
        if body:
            text += "\n\n" + str(body).strip()
        return bool(_tg.send(text))      # send() returns a message id; callers here want a bool
    except Exception:  # noqa — a notification must never take down the thing it is describing
        swallowed(log, '_send_telegram: failed; returning a fallback')
        return False


def toast(title: str, body: str = "", *, realm_root=None, event: str = "") -> bool:
    """Show a desktop notification. Returns True if it was dispatched (not that it was displayed).

    Non-blocking and non-throwing by contract: callers can fire this from inside a run without
    guarding it. Returns False when suppressed (wrong platform, event switched off, duplicate).
    """
    if os.name != "nt":
        return False                       # only Windows toasts for now
    if not channel_enabled("desktop"):     # per-machine channel switch (App settings)
        return False
    if event and realm_root is not None and not matrix(realm_root).get(event, {}).get("desktop", True):
        return False
    if realm_root is not None and not cross_realm(realm_root) and not is_active_realm(realm_root):
        return False
    if _dedupe(f"desktop|{event}|{title}|{body}"):
        return False
    title = _titled(realm_root, title)

    def _run():
        # Belt and braces: _send guards itself, but an exception escaping a thread target would
        # still surface as an unhandled-thread-exception in the log. Nothing about notifying is
        # worth a stack trace.
        try:
            _send(title, body)
        except Exception as e:  # noqa
            log.debug("toast thread failed: %s", e)
    threading.Thread(target=_run, daemon=True).start()
    return True
