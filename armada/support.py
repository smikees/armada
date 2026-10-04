"""Send exactly the approved, redacted report through ARMADA's public relay.

Only the server holds the mail credential. A failed or uncertain send retains the preview
and saves a local copy; retries use one stable idempotency ID.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import platform
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import brand, util
from .util import swallowed

log = logging.getLogger(__name__)

TO = "armada@stamih.com"
ENDPOINT = "https://armada.stamih.com/api/report.php"

MAX_MESSAGE = 8000
LOG_LINES = 40                 # per log file
_PREVIEW_TTL = 30 * 60

_previews: dict = {}           # token -> {"text", "subject", "reply_to", "at"}
_lock = threading.Lock()


# --- redaction ---------------------------------------------------------------------------------

_SECRETS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "[anthropic-key]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "[api-key]"),
    (re.compile(r"\bre_[A-Za-z0-9_]{16,}"), "[resend-key]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[github-token]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[slack-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[aws-key]"),
    (re.compile(r"\b\d{6,12}:AA[A-Za-z0-9_\-]{20,}"), "[telegram-token]"),
    (re.compile(r"(?i)\b(bearer|token|apikey|api_key|access_token|refresh_token|password|secret)"
                r"(\s*[:=]\s*|\s+)[\"']?[A-Za-z0-9_\-\.~+/=]{8,}[\"']?"), r"\1\2[redacted]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}"), "[jwt]"),
    (re.compile(r"\b[A-Za-z0-9+/_\-]{40,}={0,2}"), "[long-string]"),
]
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_WINUSER = re.compile(r"(?i)([A-Z]:\\+Users\\+)([^\\/:*?\"<>|\s]+)")


def redact(text: str, keep_email: str = "") -> str:
    """Strip what shouldn't leave the machine from log text. Conservative on purpose: a report with a
    few too many [redacted] marks is still useful; one with a key in it is an incident."""
    out = str(text or "")
    for rx, rep in _SECRETS:
        out = rx.sub(rep, out)
    keep = (keep_email or "").strip().lower()
    out = _EMAIL.sub(lambda m: m.group(0) if keep and m.group(0).lower() == keep else "[email]", out)
    out = _WINUSER.sub(lambda m: m.group(1) + "<user>", out)
    return out


def _tail(path: Path, n: int) -> list:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []


# --- the report --------------------------------------------------------------------------------

def _facts(realm_root: str) -> list:
    from . import __version__, realmformat
    fmt = "none open"
    if realm_root:
        try:
            cfg = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
            fmt = f"v{realmformat.version_of(cfg)}"
        except (OSError, ValueError):
            fmt = "unreadable"
    return [
        ("App", f"{brand.NAME} {__version__}" + (f" ({brand.CHANNEL})" if brand.CHANNEL else "")),
        ("Realm format", fmt),
        ("Platform", f"{platform.system()} {platform.release()} ({platform.version()})"),
        ("Python", sys.version.split()[0]),
    ]


def build(realm_root: str, message: str, page: str = "", title: str = "", email: str = "",
          include_logs: bool = True) -> dict:
    """The report as it will be sent: {subject, text}. Pure — it reads, it sends nothing."""
    message = str(message or "").strip()[:MAX_MESSAGE]
    email = str(email or "").strip()[:200]
    if email and not _EMAIL.fullmatch(email):
        email = ""
    now = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [f"{brand.NAME} issue report — {now}", "",
             "What happened (in their words):", message or "(no description)", ""]
    where = (title or "").strip()
    page = (page or "").strip()
    lines += [f"Page: {redact(where)} — {redact(page)}" if where else f"Page: {redact(page) or 'unknown'}"]
    lines += [f"{k}: {v}" for k, v in _facts(realm_root)]
    lines += [f"Reply to: {email}" if email else "Reply to: (none given)"]
    if include_logs:
        logdir = util.data_dir() / "logs"
        for name in ("armada.log", "scheduler.log"):
            tail = _tail(logdir / name, LOG_LINES)
            lines += ["", f"--- last {len(tail)} lines of {name} (secrets removed) ---"]
            lines += [redact(l, keep_email=email) for l in tail] or ["(empty)"]
    else:
        lines += ["", "(Logs not included — the person chose not to send them.)"]
    first = next((l for l in message.splitlines() if l.strip()), "no description")
    subject = f"[{brand.NAME} beta] {first[:80]}"
    return {"subject": subject, "text": "\n".join(lines), "reply_to": email}


def preview(realm_root: str, **kw) -> dict:
    """Build the report and keep it under a token, so Send sends exactly this text."""
    rep = build(realm_root, **kw)
    token = secrets.token_urlsafe(16)
    with _lock:
        now = time.time()
        for t in [t for t, v in _previews.items() if now - v["at"] > _PREVIEW_TTL]:
            _previews.pop(t, None)
        _previews[token] = {**rep, "id": secrets.token_hex(16), "at": now}
    return {"ok": True, "token": token, "subject": rep["subject"], "text": rep["text"]}


# --- sending ---------------------------------------------------------------------------------

def _save_unsent(rep: dict) -> Path | None:
    """Keep a report that couldn't be sent, so nothing the person wrote is lost."""
    try:
        d = util.data_dir() / "reports"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"report-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}.txt"
        util.write_text_atomic(p, f"Subject: {rep['subject']}\n\n{rep['text']}\n")
        return p
    except OSError:
        swallowed(log, "_save_unsent: could not save the report")
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Report relay redirect refused", headers, fp)


def _post(payload: dict) -> bool:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(body) > 65536:
        raise ValueError("Report too large for the relay")
    request = urllib.request.Request(ENDPOINT, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": f"{brand.NAME}-support"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=20) as response:
        return 200 <= response.status < 300 and json.loads(response.read(4096)).get("ok") is True


def send(token: str) -> dict:
    """Send the approved snapshot, preserving the same ID across uncertain-delivery retries."""
    with _lock:
        rep = _previews.get(str(token or ""))
        if not rep or time.time() - rep["at"] > _PREVIEW_TTL:
            return {"ok": False, "error": "That preview has expired — review the report again."}
        if rep.get("sending"):
            return {"ok": False, "error": "This report is already being sent."}
        rep["sending"] = True
    ok = False
    try:
        ok = _post({name: rep[name] for name in ("id", "subject", "text", "reply_to")})
    except (OSError, ValueError, TypeError, AttributeError):
        ok = False
    finally:
        with _lock:
            rep["sending"] = False
            if ok:
                _previews.pop(token, None)
    if ok:
        return {"ok": True}
    saved = _save_unsent(rep)
    return {"ok": False, "saved": str(saved or ""),
            "error": "Couldn't confirm delivery. You can retry this report safely. "
                     + (f"A copy is saved at {saved}; you can also email it to {TO}." if saved else
                        "Your preview is still available; try again.")}
