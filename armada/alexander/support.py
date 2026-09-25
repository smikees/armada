"""Alexander in the app: support conversations (launch plan 6.2, 6.3, 6.6; docs/dev/ALEXANDER.md).

One turn is: assemble what he's allowed to know (the sections PROMPT.md names), run one sealed
engine turn with no tools (Opus 5.5 at High, fixed), then take his reply apart — the prose is
shown, the fenced proposal blocks become cards only if they validate. Nothing he writes acts on its
own; a card acts when the owner presses its button, through the app's own endpoint.

Conversations are this machine's, not a realm's: `~/.armada/alexander/<id>.jsonl`, one line per
message. His tokens are recorded as System usage in the realm he was asked from (sysusage).
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import secrets
import tempfile
from pathlib import Path

from .. import util
from ..util import swallowed
from . import EFFORT, MODEL, prompt as system_prompt, remedies

log = logging.getLogger(__name__)

HISTORY_TURNS = 12              # earlier messages sent back to him, newest last
MAX_MESSAGE = 6000
LOG_WINDOW_MIN = 10             # minutes either side of a failure whose log lines he sees
LOG_MAX_LINES = 80
_ID_RE = re.compile(r"^[a-z0-9]{8,32}$")
_BLOCK_RE = re.compile(r"```(remedy|addon|report)[ \t]*\n(.*?)```", re.S)
DOCS = Path(__file__).resolve().parents[1] / "docs" / "user"
CONTRACT_FILE = Path(__file__).resolve().parent / "ADDON_CONTRACT.md"


# --- conversations ---------------------------------------------------------------------------------

def _dir() -> Path:
    d = util.data_dir() / "alexander"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_id() -> str:
    return secrets.token_hex(8)


def valid_id(cid: str) -> bool:
    return bool(_ID_RE.match(str(cid or "")))


def history(cid: str) -> list[dict]:
    if not valid_id(cid):
        return []
    p = _dir() / f"{cid}.jsonl"
    out = []
    try:
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("role") in ("owner", "alexander"):
                out.append(rec)
    except OSError:
        return []
    return out


def _append(cid: str, rec: dict) -> None:
    try:
        with (_dir() / f"{cid}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        swallowed(log, '_append: failed; the conversation continues unsaved')


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


# --- what he's allowed to know ---------------------------------------------------------------------

_WORD = re.compile(r"[a-z]{3,}")


def help_section(question: str, page: str = "") -> str:
    """Every help page — they're small, and a page he can't see is a question he can't answer —
    with the ones that share the most words with the question and the page first."""
    want = set(_WORD.findall((question + " " + page).lower()))
    pages = []
    for p in sorted(DOCS.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        score = len(want & set(_WORD.findall(text.lower()))) + (5 if p.stem in page else 0)
        pages.append((score, p.stem, text.strip()))
    pages.sort(key=lambda t: (-t[0], t[1]))
    return "\n\n".join(f'<page name="{stem}">\n{text}\n</page>' for _s, stem, text in pages)


def _json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def realm_section(realm_root) -> str:
    """A compact, credential-free picture of the realm: what the owner could see on its pages."""
    from .. import __version__, reader, auth, schedsvc
    from ..webui.agentbits import _runs
    root = Path(realm_root)
    lines = [f"ARMADA version: {__version__}"]
    try:
        realm = reader.read(str(root))
    except (SystemExit, Exception):  # noqa — an unreadable realm is itself worth telling him
        swallowed(log, 'realm_section: realm unreadable; said so')
        return "\n".join(lines + ["The realm could not be read."])
    cfg = _json(root / "realm.json")
    owner = str((cfg.get("user") or {}).get("name") or "")
    lines += [f"Realm: {realm.name} (template {cfg.get('template') or 'unknown'}; "
              f"a {realm.theme_collective} led by its {realm.theme_coordinator})",
              f"Owner's name: {owner or 'not set'}"]
    try:
        st = schedsvc.status(str(root))
        lines.append(f"Scheduler: {'running' if st['running'] else 'NOT running'}; "
                     f"{st['scheduled']} scheduled job(s) depend on it")
    except Exception:  # noqa
        swallowed(log, 'realm_section: scheduler state unknown')
    try:
        a = auth.status()
        lines.append("Claude sign-in: " + ("signed in" if a.get("logged_in") else
                                           "Claude Code not installed" if a.get("reason") == "cli-missing"
                                           else "SIGNED OUT"))
    except Exception:  # noqa
        swallowed(log, 'realm_section: sign-in state unknown')
    lines.append("")
    lines.append("Agents:")
    week = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
    failures = []
    for ag in ([realm.coordinator] if realm.coordinator else []) + list(realm.members):
        aj = _json(root / "agents" / ag.id / "agent.json")
        lines.append(f"- {ag.display} (id {ag.id}; {ag.theme_role}{'; coordinator' if ag.is_coordinator else ''}; "
                     f"model {aj.get('model') or 'realm default'}, effort {aj.get('effort') or 'default'})")
        for j in ag.jobs:
            lines.append(f"  - job {ag.id}/{j.id} \"{j.name}\": {j.cadence or 'manual'}, "
                         f"{'on' if j.enabled else 'OFF'}, {j.kind}, last {j.last_status or 'never run'}")
        for r in _runs(root, ag.id)[-40:]:
            if str(r.get("ts", ""))[:10] >= week and str(r.get("status", "")).lower() in ("error", "failed"):
                failures.append(f"- {r.get('ts')} {ag.id}/{r.get('task')}: {str(r.get('summary') or '')[:200]}")
    caps = []
    for kind, items in (cfg.get("toolkit") or {}).items():
        for it in items if isinstance(items, list) else []:
            if isinstance(it, dict):
                caps.append(f"- {it.get('name') or it.get('id')} ({kind}, {'on' if it.get('enabled', True) else 'off'})")
    lines += ["", "Capabilities in the realm:"] + (caps or ["- none"])
    lines += ["", "Failed runs in the last 7 days:"] + (failures[-15:] or ["- none"])
    from ..support import redact
    return redact("\n".join(lines))


def logs_section(item: dict | None) -> str:
    """For a failure: ARMADA's own log lines around it, secrets removed (the 5.6 redactor)."""
    from ..support import redact
    ts = str((item or {}).get("ts") or "")
    try:
        at = _dt.datetime.fromisoformat(ts).replace(tzinfo=None) if ts else None
    except ValueError:
        at = None
    out = []
    for name in ("armada.log", "scheduler.log"):
        p = util.data_dir() / "logs" / name
        try:
            text = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        keep = []
        for ln in text[-4000:]:
            if at is None:
                continue
            try:
                t = _dt.datetime.fromisoformat(ln[:19])
            except ValueError:
                continue
            if abs((t - at).total_seconds()) <= LOG_WINDOW_MIN * 60:
                keep.append(ln)
        if at is None:
            keep = text[-20:]
        if keep:
            out.append(f"--- {name} ---\n" + "\n".join(redact(l) for l in keep[-LOG_MAX_LINES:]))
    return "\n".join(out) or "(no log lines)"


def page_section(page: str, item: dict | None) -> str:
    lines = [f"The owner is on: {page or 'unknown'}"]
    if item:
        lines.append("They asked about this item: " + json.dumps(item, ensure_ascii=False)[:1500])
    return "\n".join(lines)


def build(realm_root, cid: str, message: str, page: str = "", item: dict | None = None) -> str:
    """The user message for one turn: the context sections, the conversation so far, the question."""
    earlier = history(cid)[-HISTORY_TURNS:]
    convo = "\n\n".join(f"{'Owner' if r['role'] == 'owner' else 'Alexander'}: {r.get('text', '')}"
                        for r in earlier)
    try:
        contract = CONTRACT_FILE.read_text(encoding="utf-8")
    except OSError:
        contract = ""
    parts = [f"<help>\n{help_section(message, page)}\n</help>",
             f"<realm>\n{realm_section(realm_root)}\n</realm>",
             f"<page>\n{page_section(page, item)}\n</page>",
             f"<logs>\n{logs_section(item) if item else '(none: this question is not about a failure)'}\n</logs>",
             f"<addon_contract>\n{contract}\n</addon_contract>",
             f"<remedies>\n{remedies.context()}\n</remedies>"]
    if convo:
        parts.append(f"<conversation>\n{convo}\n</conversation>")
    parts.append(f"The owner asks:\n{message}")
    return "\n\n".join(parts)


# --- taking his reply apart ------------------------------------------------------------------------

def _addon_card(m) -> dict | None:
    """Validate a proposed add-on exactly as the loader will, in a scratch folder."""
    from .. import addons
    if not isinstance(m, dict) or not isinstance(m.get("id"), str):
        return None
    aid = m["id"]
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,63}$", aid):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / aid
        folder.mkdir()
        (folder / addons.MANIFEST).write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        reg = addons.Registry()
        got = addons._load_one(folder, "app", reg)
    widgets = (got or {}).get("items", {}).get("widgets") or []
    if not got or reg.problems or not widgets:
        return None
    other = [k for k, v in got["items"].items() if v and k != "widgets"]
    if other:
        return None                                   # kinds the app doesn't show: not offered
    names = ", ".join(f"“{w['title']}”" for w in widgets)
    return {"type": "addon", "id": aid, "name": got["meta"]["name"], "manifest": m,
            "what": f"Add {'a widget' if len(widgets) == 1 else f'{len(widgets)} widgets'} to your "
                    f"dashboard: {names}. You can remove {'it' if len(widgets) == 1 else 'them'} "
                    "like any other widget.",
            "button": "Add to dashboard"}


def _report_card(r) -> dict | None:
    if not isinstance(r, dict) or not str(r.get("summary") or "").strip():
        return None
    parts = [str(r.get("summary")).strip()]
    for k, title in (("what_happened", "What happened"), ("expected", "What I expected"),
                     ("steps", "Steps"), ("context", "What Alexander saw")):
        v = str(r.get(k) or "").strip()
        if v:
            parts.append(f"{title}:\n{v}")
    from ..support import redact
    return {"type": "report", "message": redact("\n\n".join(parts))[:7500],
            "what": "Send this to the ARMADA team. You'll see the whole report, and can change it, "
                    "before anything is sent.",
            "button": "Review the report"}


def parse(text: str, realm_root) -> tuple[str, list]:
    """(the prose, [cards]). At most one card of each kind; anything invalid is dropped silently."""
    cards, seen = [], set()
    for kind, body in _BLOCK_RE.findall(text or ""):
        if kind in seen:
            continue
        try:
            obj = json.loads(body.strip())
        except ValueError:
            continue
        card = None
        if kind == "remedy":
            c = remedies.card(realm_root, obj)
            card = {"type": "remedy", **c} if c else None
        elif kind == "addon":
            card = _addon_card(obj)
        elif kind == "report":
            card = _report_card(obj)
        if card:
            cards.append(card)
            seen.add(kind)
    prose = _BLOCK_RE.sub("", text or "").strip()
    prose = re.sub(r"\n{3,}", "\n\n", prose)
    return prose, cards


# --- one turn ------------------------------------------------------------------------------------

def ask(realm_root, cid: str, message: str, page: str = "", item: dict | None = None,
        engine=None, on_event=None) -> dict:
    message = str(message or "").strip()[:MAX_MESSAGE]
    if not message:
        return {"ok": False, "error": "Ask me something first."}
    if not valid_id(cid):
        cid = new_id()
    user = build(realm_root, cid, message, page, item)
    _append(cid, {"role": "owner", "text": message, "ts": _now(), "page": page,
                  **({"item": item} if item else {})})
    if engine is None:
        from ..engine.claude import ClaudeEngine
        engine = ClaudeEngine()
    kw = dict(system=system_prompt(), prompt=user, model=MODEL, effort=EFFORT,
              cwd=str(_dir()), allow_tools=False, timeout=600)
    if on_event and hasattr(engine, "run_stream"):
        res = engine.run_stream(on_event=on_event, **kw)
    else:
        res = engine.run(**kw)
    try:
        from .. import sysusage
        sysusage.record(realm_root, "alexander", res.model or MODEL, res.usage.as_dict(), res.ok)
    except Exception:  # noqa — accounting never fails the answer
        swallowed(log, 'ask: usage not recorded')
    if not res.ok or not (res.output or "").strip():
        # Claude Code puts some refusals in the output rather than the error ("API Error: 400 …
        # version 2.1.280 or newer is required"); either way the owner should read the real reason.
        why = (res.error or (res.output if not res.ok else "") or "no reply came back").strip()[:300]
        return {"ok": False, "id": cid, "error": why}
    prose, cards = parse(res.output, realm_root)
    _append(cid, {"role": "alexander", "text": prose, "ts": _now(), "cards": cards})
    return {"ok": True, "id": cid, "text": prose, "cards": cards}


def install_addon(realm_root, manifest: dict, scope: str = "realm") -> dict:
    """Install an add-on he proposed, after validating it again (the card could be stale or
    edited). Refuses to overwrite an add-on of the same id."""
    from .. import addons
    card = _addon_card(manifest)
    if not card:
        return {"ok": False, "error": "That add-on doesn't pass ARMADA's checks, so it wasn't installed."}
    base = addons.realm_dir(realm_root) if scope == "realm" else addons.app_dir()
    folder = base / card["id"]
    if folder.exists():
        return {"ok": False, "error": f"An add-on called {card['id']} is already installed. "
                                      "Remove it first, or ask Alexander for a different name."}
    try:
        folder.mkdir(parents=True)
        util.write_json_atomic(folder / addons.MANIFEST, manifest)
    except OSError as e:
        return {"ok": False, "error": f"Couldn't write the add-on: {str(e)[:120]}"}
    reg = addons.load(realm_root)
    qids = [w["qid"] for w in reg.get("widgets") if w["addon"] == card["id"]]
    return {"ok": True, "id": card["id"], "widgets": qids, "path": str(folder)}
