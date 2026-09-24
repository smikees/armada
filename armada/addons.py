"""Add-ons: the extension surface (Phase 2, 2.7 — ADR-002's homework). Designed and stubbed; nothing
in the app reads it yet.

ADR-002 says Alexander-the-developer, when it comes, changes a user's ARMADA only by writing into a
defined surface — never by patching the app — so the user keeps running the official build plus
their own files, updates keep applying, and undoing a change is deleting a folder. This module is
that surface's contract and loader. The full contract, with examples, is docs/dev/EXTENSION_POINTS.md.

Why "add-on" and not "plugin": the app already has four capability kinds — connectors, extensions,
skills, plugins — and two of them are exactly the words this would otherwise use. A third meaning
of "plugin" on the Capabilities page would be a bug report waiting to happen.

**An add-on is data, never code.** A folder holding one `addon.json`. It can contribute five kinds
of thing, each validated against a closed schema and rendered, when something renders it, by the
app's own code:

  widgets        dashboard cards — static markdown, or a list of links
  filters        saved views over a list (the Jobs list, the Capabilities page)
  themes         a named pair of brand colours (the same shape vtheme.THEMES uses)
  job_templates  a pre-filled *agent* job — never a command job, which would be code by the back door
  layouts        a dashboard arrangement (the same shape dashboard.json uses)

**Where they live.** `<realm>/addons/<id>/addon.json` travels with the realm (export, Git, another
machine); `~/.armada/addons/<id>/addon.json` is this install's, for every realm. Themes are app-scope
only, because the chosen theme is a per-install setting (appconfig). The same add-on id in both
places: the realm's copy wins, and the app's is reported as shadowed.

**Fail safe, always.** `load()` never raises. A malformed add-on is skipped whole; a malformed
contribution inside a good add-on is skipped alone; either way the reason goes into
`Registry.problems` (and the log), which is what a Settings page — or Alexander — shows the user.
Unknown keys are ignored so an add-on written for a later contract still loads what it can; an
add-on that declares a NEWER contract than this build knows is skipped rather than half-read.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

CONTRACT = 1                      # the `armada_addon` value this build understands
MANIFEST = "addon.json"
KINDS = ("widgets", "filters", "themes", "job_templates", "layouts")
APP_ONLY = {"themes"}             # kinds that make sense only per install, not per realm

# Limits: an add-on is a small hand- or agent-written file, and a loader that reads whatever it's
# given is how a 2 GB "addon.json" takes the app down.
MAX_MANIFEST_BYTES = 256 * 1024
MAX_PER_KIND = 50
MAX_TEXT = 20_000                 # markdown widget body, job template prompt
MAX_LABEL = 120

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Closed vocabularies a filter may match on. The job buckets mirror webui/schedfmt.py's
# _STATUS_FILTERS / _CADENCE_FILTERS; tests/test_addons.py fails if the two drift apart.
JOB_STATUS = ("success", "running", "warning", "failed", "none")
JOB_CADENCE = ("daily", "weekly", "monthly", "quarterly", "other")
CAP_KINDS = ("connectors", "extensions", "skills", "plugins")     # == capabilities.KINDS
FILTER_TARGETS = {
    "jobs": {"status": JOB_STATUS, "cadence": JOB_CADENCE, "agent": None, "text": None},
    "capabilities": {"kind": CAP_KINDS, "text": None},
}

BUILTIN_WIDGETS = ("register", "usage", "jobcal")
SPAN_MIN, SPAN_MAX = 4, 20        # the 20-column dashboard grid; same clamps as _save_dashboard
HEIGHT_MIN, HEIGHT_MAX = 120, 3000


def app_dir() -> Path:
    from . import util
    return util.data_dir() / "addons"


def realm_dir(realm_root) -> Path:
    return Path(realm_root) / "addons"


@dataclass
class Registry:
    """Everything loaded, plus why anything wasn't. Contributions carry a qualified id,
    `<addon-id>/<id>`, so two add-ons can never collide."""
    addons: list = field(default_factory=list)       # [{id, name, version, scope, path}]
    items: dict = field(default_factory=lambda: {k: [] for k in KINDS})
    problems: list = field(default_factory=list)     # [{scope, addon, where, reason}]

    def get(self, kind: str) -> list:
        return list(self.items.get(kind, []))

    def find(self, kind: str, qid: str) -> dict | None:
        return next((i for i in self.items.get(kind, []) if i["qid"] == qid), None)


# ---- per-kind validators: (clean dict, None) or (None, reason) ------------------------------------

def _text(v, limit=MAX_LABEL) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() and len(v) <= limit else None


def _widget(d: dict):
    title = _text(d.get("title"))
    if not title:
        return None, "widget needs a title (1–120 chars)"
    kind = d.get("kind")
    out = {"title": title, "kind": kind}
    if kind == "markdown":
        body = d.get("body")
        if not isinstance(body, str) or not body.strip() or len(body) > MAX_TEXT:
            return None, f"markdown widget needs a body (1–{MAX_TEXT} chars)"
        out["body"] = body
    elif kind == "links":
        links = d.get("links")
        if not isinstance(links, list) or not links or len(links) > 50:
            return None, "links widget needs 1–50 links"
        clean = []
        for ln in links:
            label = _text((ln or {}).get("label")) if isinstance(ln, dict) else None
            url = (ln or {}).get("url") if isinstance(ln, dict) else None
            ok_url = isinstance(url, str) and len(url) <= 2000 and (
                url.startswith(("https://", "http://")) or (url.startswith("/") and not url.startswith("//")))
            if not (label and ok_url):
                return None, "each link needs a label and an http(s) or app-local (/…) url"
            clean.append({"label": label, "url": url})
        out["links"] = clean
    else:
        return None, "widget kind must be 'markdown' or 'links'"
    span = d.get("default_span")
    if span is not None:
        if not isinstance(span, int) or isinstance(span, bool) or not SPAN_MIN <= span <= SPAN_MAX:
            return None, f"default_span must be an integer {SPAN_MIN}–{SPAN_MAX}"
        out["default_span"] = span
    return out, None


def _filter(d: dict):
    label = _text(d.get("label"))
    if not label:
        return None, "filter needs a label"
    target = d.get("applies_to")
    if target not in FILTER_TARGETS:
        return None, f"applies_to must be one of {', '.join(FILTER_TARGETS)}"
    match = d.get("match")
    if not isinstance(match, dict) or not match:
        return None, "filter needs a non-empty match"
    allowed = FILTER_TARGETS[target]
    clean = {}
    for k, v in match.items():
        if k not in allowed:
            return None, f"'{k}' is not something a {target} filter can match on"
        if k == "text":
            t = _text(v, 200)
            if not t:
                return None, "text match must be a non-empty string"
            clean[k] = t
            continue
        if not isinstance(v, list) or not v or not all(isinstance(x, str) and x for x in v):
            return None, f"'{k}' must be a non-empty list of strings"
        vocab = allowed[k]
        if vocab is not None and any(x not in vocab for x in v):
            return None, f"'{k}' values must be from: {', '.join(vocab)}"
        clean[k] = list(dict.fromkeys(v))
    return {"label": label, "applies_to": target, "match": clean}, None


def _theme(d: dict):
    name = _text(d.get("name"))
    a, a2 = d.get("accent"), d.get("accent2")
    if not name:
        return None, "theme needs a name"
    if not (isinstance(a, str) and _HEX_RE.match(a) and isinstance(a2, str) and _HEX_RE.match(a2)):
        return None, "theme needs accent and accent2 as #rrggbb"
    return {"name": name, "accent": a.lower(), "accent2": a2.lower()}, None


def _job_template(d: dict):
    name = _text(d.get("name"))
    if not name:
        return None, "job template needs a name"
    if d.get("kind", "agent") != "agent":
        # A command job runs a shell command on the owner's machine on a schedule. An add-on that
        # could ship one would be code by the back door; the contract refuses it outright.
        return None, "job templates can only be agent jobs (a prompt), never command jobs"
    prompt = d.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_TEXT:
        return None, f"job template needs a prompt (1–{MAX_TEXT} chars)"
    out = {"name": name, "kind": "agent", "prompt": prompt}
    cron = d.get("cron")
    if cron not in (None, ""):
        from . import scheduler
        if not isinstance(cron, str) or not scheduler.is_cron(cron):
            return None, "cron must be a 5-field cron expression"
        out["cron"] = cron.strip()
    summary = d.get("summary")
    if summary is not None:
        s = _text(summary, 300)
        if not s:
            return None, "summary must be a non-empty string (≤300 chars)"
        out["summary"] = s
    if "allow_tools" in d:
        if not isinstance(d["allow_tools"], bool):
            return None, "allow_tools must be true or false"
        out["allow_tools"] = d["allow_tools"]
    return out, None


def _widget_ref_ok(wid) -> bool:
    if not isinstance(wid, str):
        return False
    if wid in BUILTIN_WIDGETS:
        return True
    # another add-on's widget, qualified: addon:<addon-id>/<widget-id>
    m = re.match(r"^addon:([a-z0-9][a-z0-9-]*)/([a-z0-9][a-z0-9-]*)$", wid)
    return bool(m)


def _layout(d: dict):
    name = _text(d.get("name"))
    if not name:
        return None, "layout needs a name"
    order = d.get("order")
    if not isinstance(order, list) or not order or len(order) > 50:
        return None, "layout needs an order of 1–50 widget ids"
    if not all(_widget_ref_ok(w) for w in order):
        return None, ("layout widgets must be built-in (register, usage, jobcal) or "
                      "addon:<addon-id>/<widget-id> — thread widgets are realm-specific")
    if len(set(order)) != len(order):
        return None, "layout lists a widget twice"
    out = {"name": name, "order": order, "spans": {}, "heights": {}, "single": {}}
    for key, lo, hi in (("spans", SPAN_MIN, SPAN_MAX), ("heights", HEIGHT_MIN, HEIGHT_MAX)):
        v = d.get(key) or {}
        if not isinstance(v, dict):
            return None, f"{key} must be an object"
        for w, n in v.items():
            if w not in order:
                return None, f"{key} names '{w}', which isn't in order"
            if not isinstance(n, int) or isinstance(n, bool) or not lo <= n <= hi:
                return None, f"{key}['{w}'] must be an integer {lo}–{hi}"
            out[key][w] = n
    single = d.get("single") or {}
    if not isinstance(single, dict) or not all(w in order and isinstance(b, bool) for w, b in single.items()):
        return None, "single must map widgets in order to true/false"
    out["single"] = dict(single)
    return out, None


_VALIDATORS = {"widgets": _widget, "filters": _filter, "themes": _theme,
               "job_templates": _job_template, "layouts": _layout}


# ---- loading --------------------------------------------------------------------------------------

def _read_manifest(folder: Path):
    """(manifest dict, None) or (None, reason)."""
    p = folder / MANIFEST
    if folder.is_symlink() or p.is_symlink():
        return None, "symlinked add-ons are not loaded — copy the folder in"
    if not p.is_file():
        return None, f"no {MANIFEST}"
    try:
        size = p.stat().st_size
    except OSError as e:
        return None, f"unreadable ({e.__class__.__name__})"
    if size > MAX_MANIFEST_BYTES:
        return None, f"{MANIFEST} is {size} bytes; the limit is {MAX_MANIFEST_BYTES}"
    try:
        m = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, f"not valid JSON ({e.__class__.__name__})"
    if not isinstance(m, dict):
        return None, f"{MANIFEST} must be a JSON object"
    return m, None


def _load_one(folder: Path, scope: str, reg: Registry) -> dict | None:
    def problem(reason, where=""):
        reg.problems.append({"scope": scope, "addon": folder.name, "where": where, "reason": reason})

    m, why = _read_manifest(folder)
    if m is None:
        problem(why)
        return None
    ver = m.get("armada_addon")
    if not isinstance(ver, int) or isinstance(ver, bool) or ver < 1:
        problem("missing or invalid 'armada_addon' contract version")
        return None
    if ver > CONTRACT:
        problem(f"written for add-on contract v{ver}; this ARMADA understands v{CONTRACT} — update ARMADA")
        return None
    aid = m.get("id")
    if not isinstance(aid, str) or not _ID_RE.match(aid):
        problem("id must be lowercase letters, digits and dashes (max 64)")
        return None
    if aid != folder.name:
        # "Undo is deleting the folder" only holds if the folder IS the add-on's identity.
        problem(f"id '{aid}' must match its folder name '{folder.name}'")
        return None
    name = _text(m.get("name")) or aid
    provides = m.get("provides")
    if not isinstance(provides, dict):
        problem("'provides' must be an object")
        return None
    staged = {k: [] for k in KINDS}
    for kind, entries in provides.items():
        if kind not in KINDS:
            problem(f"unknown kind '{kind}' ignored", kind)
            continue
        if kind in APP_ONLY and scope != "app":
            problem(f"{kind} are per-install — put this add-on in the app add-ons folder", kind)
            continue
        if not isinstance(entries, list):
            problem("must be a list", kind)
            continue
        if len(entries) > MAX_PER_KIND:
            problem(f"{len(entries)} entries; the limit is {MAX_PER_KIND} — none loaded", kind)
            continue
        seen = set()
        for i, e in enumerate(entries):
            where = f"{kind}[{i}]"
            if not isinstance(e, dict):
                problem("must be an object", where)
                continue
            eid = e.get("id")
            if not isinstance(eid, str) or not _ID_RE.match(eid):
                problem("id must be lowercase letters, digits and dashes", where)
                continue
            if eid in seen:
                problem(f"duplicate id '{eid}'", where)
                continue
            clean, why = _VALIDATORS[kind](e)
            if clean is None:
                problem(why, f"{kind}/{eid}")
                continue
            seen.add(eid)
            staged[kind].append({**clean, "id": eid, "qid": f"{aid}/{eid}", "addon": aid, "scope": scope})
    return {"meta": {"id": aid, "name": name, "version": str(m.get("version") or ""),
                     "description": _text(m.get("description"), 500) or "", "scope": scope,
                     "path": str(folder)},
            "items": staged}


def _scan(root: Path, scope: str, reg: Registry) -> dict:
    out: dict = {}
    try:
        if not root.is_dir():
            return out
        folders = sorted(p for p in root.iterdir() if p.is_dir() or p.is_symlink())
    except OSError as e:
        reg.problems.append({"scope": scope, "addon": "", "where": str(root),
                             "reason": f"add-ons folder unreadable ({e.__class__.__name__})"})
        return out
    for f in folders:
        try:
            got = _load_one(f, scope, reg)
        except Exception as e:  # noqa — a loader bug must cost one add-on, not the app
            log.exception("add-on %s (%s): loader failed", f.name, scope)
            reg.problems.append({"scope": scope, "addon": f.name, "where": "",
                                 "reason": f"could not be loaded ({e.__class__.__name__})"})
            continue
        if got:
            out[got["meta"]["id"]] = got
    return out


def load(realm_root=None) -> Registry:
    """Load the app's add-ons, then the realm's (which win on an id clash). Never raises."""
    reg = Registry()
    try:
        found = _scan(app_dir(), "app", reg)
        if realm_root is not None:
            for aid, got in _scan(realm_dir(realm_root), "realm", reg).items():
                if aid in found:
                    reg.problems.append({"scope": "app", "addon": aid, "where": "",
                                         "reason": "shadowed by the realm's add-on of the same id"})
                found[aid] = got
        for aid in sorted(found):
            reg.addons.append(found[aid]["meta"])
            for kind in KINDS:
                reg.items[kind].extend(found[aid]["items"][kind])
    except Exception:  # noqa — the surface must never be what breaks the app
        log.exception("add-ons: load failed; continuing with none")
        return Registry(problems=[{"scope": "", "addon": "", "where": "", "reason": "add-ons failed to load"}])
    for p in reg.problems:
        log.warning("add-on %s [%s] %s: %s", p["addon"] or "?", p["scope"], p["where"] or "-", p["reason"])
    return reg
