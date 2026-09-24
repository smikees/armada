"""Report an issue (launch plan 5.6, ADR-005).

The beta's one feedback path: the support icon beside the settings gear opens a short form; ARMADA
assembles a report — the person's words, the page they were on, the version, and (if they agree) the
last lines of its logs with anything that looks like a secret removed — **shows them the whole
report**, and only when they press Send does it email it to the beta inbox.

Three rules shape this module:

- **What's sent is exactly what was shown.** `preview()` builds the text and hands back a token;
  `send()` sends the text stored under that token, not a rebuild. Logs move on in the seconds between
  the two, and "we showed you one thing and sent another" is the worst thing a report button can do.
- **Nothing secret leaves.** Log lines pass through `redact()`: API keys, bearer and OAuth tokens,
  Telegram bot tokens, long secret-shaped strings, email addresses other than the one the person
  typed, and the Windows user name in paths.
- **The key can only send.** The Resend key is a sending-only key restricted to armada.stamih.com
  (ADR-005: fine for five invited users; a relay before a public release). It lives in
  `armada/support_key.txt`, which is git-ignored and written by the build; it is never in the repo.

Sending is a network call, so it happens only on the POST from the Send button — never while a page
renders.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
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
FROM = f"{brand.NAME} reports <reports@armada.stamih.com>"
ENDPOINT = "https://api.resend.com/emails"
KEY_FILE = Path(__file__).resolve().parent / "support_key.txt"

MAX_MESSAGE = 8000
LOG_LINES = 40                 # per log file
PER_HOUR = 5                   # sends per install per hour — the free tier is 100/day, shared
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
        _previews[token] = {**rep, "at": now}
    return {"ok": True, "token": token, "subject": rep["subject"], "text": rep["text"]}


# --- sending ---------------------------------------------------------------------------------

def key() -> str:
    """The sending key: ARMADA_RESEND_KEY (for a developer), else the file the build writes."""
    k = (os.environ.get("ARMADA_RESEND_KEY") or "").strip()
    if not k:
        try:
            k = KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            k = ""
    return k if k.startswith("re_") else ""


def _sent_log() -> Path:
    return util.data_dir() / "support_sent.json"


def _recent_sends() -> list:
    try:
        stamps = json.loads(_sent_log().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stamps = []
    now = time.time()
    return [t for t in stamps if isinstance(t, (int, float)) and now - t < 3600]


def _save_unsent(rep: dict) -> Path | None:
    """Keep a report that couldn't be sent, so nothing the person wrote is lost."""
    try:
        d = util.data_dir() / "reports"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"report-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        util.write_text_atomic(p, f"Subject: {rep['subject']}\n\n{rep['text']}\n")
        return p
    except OSError:
        swallowed(log, "_save_unsent: could not save the report")
        return None


def _post(payload: dict, k: str, timeout: int = 20) -> tuple:
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {k}",
                                          "Content-Type": "application/json",
                                          "User-Agent": f"{brand.NAME}-support"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def send(token: str) -> dict:
    """Send the previewed report. On any failure the report is saved locally and the person is told
    where, and to email it themselves — the words they took the trouble to write are never lost."""
    with _lock:
        rep = _previews.pop(str(token or ""), None)
    if not rep:
        return {"ok": False, "error": "That preview has expired — review the report again, then send."}
    recent = _recent_sends()
    if len(recent) >= PER_HOUR:
        saved = _save_unsent(rep)
        return {"ok": False, "saved": str(saved or ""),
                "error": f"That's {PER_HOUR} reports in the last hour — thank you. This one is saved"
                         + (f" at {saved}" if saved else "") + f"; send it to {TO} or try again later."}
    k = key()
    if not k:
        saved = _save_unsent(rep)
        return {"ok": False, "saved": str(saved or ""),
                "error": "This build can't send reports (no sending key). Your report is saved"
                         + (f" at {saved}" if saved else "") + f" — please email it to {TO}."}
    payload = {"from": FROM, "to": [TO], "subject": rep["subject"], "text": rep["text"]}
    if rep.get("reply_to"):
        payload["reply_to"] = rep["reply_to"]
    try:
        status, body = _post(payload, k)
    except (OSError, ValueError) as e:
        status, body = 0, str(e)
    if 200 <= status < 300:
        try:
            util.write_json_atomic(_sent_log(), recent + [time.time()])
        except OSError:
            swallowed(log, "send: could not record the send time")
        log.info("support report sent (%s)", rep["subject"][:60])
        return {"ok": True}
    log.error("support report not sent: HTTP %s %s", status, redact(body)[:300])
    saved = _save_unsent(rep)
    return {"ok": False, "saved": str(saved or ""),
            "error": "Couldn't send the report" + (f" (the mail service said {status})" if status else
                                                   " (no connection)")
                     + ". It's saved" + (f" at {saved}" if saved else "") + f" — please email it to {TO}."}
