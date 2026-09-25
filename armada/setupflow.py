"""The setup wizard's server side (launch plan 6.4; the page is webui/setup_wizard.py).

The wizard runs in two halves because a realm doesn't exist until halfway through:

* **Before the realm** (the server's welcome mode, no realm open): welcome, checks, folder, team.
  "Appoint the team" creates the realm and switches the server into it.
* **In the realm** (`/setup`): capabilities, first job, tour, done.

Progress is kept in the realm's own `realm.json` under `setup` — `{"step": …, "started": …}` while
it's under way and `{"done": …}` once finished — so closing the window halfway and opening ARMADA
again lands back on the step you were on, instead of on an Overview with half a setup behind it.
Realms made any other way (the New realm dialog, adopting a folder) never get the key and never see
the wizard.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from . import clock, recommended, util
from .alexander import wizard_script
from .util import swallowed

log = logging.getLogger(__name__)

KEY = "setup"
# The half of the wizard that runs inside a realm, in order.
REALM_STEPS = ("capabilities", "first-job", "tour", "done")
BRIEF_THREAD = "first-brief"
BRIEF_TITLE = "First brief"


def _now() -> str:
    return clock.now().replace(microsecond=0).isoformat()


def _rj(realm_root) -> Path:
    return Path(realm_root) / "realm.json"


def state(realm_root) -> dict:
    try:
        d = json.loads(_rj(realm_root).read_text(encoding="utf-8-sig")).get(KEY)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def needs_setup(realm_root) -> bool:
    """True while a wizard-made realm hasn't finished its setup."""
    st = state(realm_root)
    return bool(st) and not st.get("done")


def current_step(realm_root) -> str:
    step = str(state(realm_root).get("step") or "")
    return step if step in REALM_STEPS else REALM_STEPS[0]


def _update(realm_root, fn) -> dict:
    rj = _rj(realm_root)
    try:
        with util.file_lock(rj):
            cfg = json.loads(rj.read_text(encoding="utf-8-sig"))
            st = dict(cfg.get(KEY) or {})
            fn(cfg, st)
            cfg[KEY] = st
            util.write_json_atomic(rj, cfg)
            return {"ok": True, **st}
    except (OSError, ValueError) as e:
        swallowed(log, '_update: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:160]}


def begin(realm_root, owner: str = "") -> dict:
    """Mark a freshly made realm as mid-setup, and record the owner's name where the app keeps it
    (realm.json `user.name`, which Settings → User edits and every agent reads)."""
    def fn(cfg, st):
        st.clear()
        st.update({"step": REALM_STEPS[0], "started": _now()})
        if owner:
            user = dict(cfg.get("user") or {})
            user["name"] = owner
            cfg["user"] = user
    r = _update(realm_root, fn)
    if owner:
        # The system memory carries the owner's name; rebuild it so the first brief already knows.
        try:
            from . import memory
            memory.refresh_system_memory(realm_root, trigger="setup")
        except Exception:  # noqa — the wizard carries on; the next refresh fills it in
            swallowed(log, 'begin: memory refresh failed; ignored')
    return r


def set_step(realm_root, step: str) -> dict:
    if step not in REALM_STEPS:
        return {"ok": False, "error": "unknown step"}
    return _update(realm_root, lambda cfg, st: st.update({"step": step}))


def finish(realm_root) -> dict:
    """Setup is over: record it, and make sure the scheduler is running (the wizard promised)."""
    r = _update(realm_root, lambda cfg, st: (st.pop("step", None), st.update({"done": _now()})))
    try:
        from . import schedsvc
        r["scheduler"] = schedsvc.ensure_running(str(realm_root))
    except Exception:  # noqa
        swallowed(log, 'finish: scheduler start failed; reported')
        r["scheduler"] = {"ok": False}
    return r


# --- capabilities --------------------------------------------------------------------------------

def _entry_for(r: dict) -> dict:
    """A catalogue entry for a recommendation, for when the catalogue hasn't been fetched yet (a
    brand-new install: the daily refresh hasn't run). Same shape the catalogue writes."""
    from .catalogue import SKILLS
    return {"key": r["key"], "id": r["id"], "name": r["name"], "description": r["does"],
            "kind": "skills", "source": SKILLS, "author": "Anthropic", "category": "",
            "homepage": f"https://github.com/anthropics/skills/tree/main/skills/{r['id']}",
            "curated": "official", "version": "",
            "install": {"repo": "anthropics/skills", "path": r["id"]}}


def add_recommended(realm_root, key: str) -> dict:
    """Add one recommended capability and switch it on for the realm. Only keys on the curated list
    are accepted: this endpoint exists for the wizard, not as a second way into the catalogue."""
    r = recommended.by_key(key)
    if not r:
        return {"ok": False, "error": "That isn't one of the recommended capabilities."}
    from . import catalogue
    res = catalogue.add_to_realm(realm_root, key, entry=_entry_for(r))
    if not res.get("ok") and "already in this realm" not in str(res.get("error") or ""):
        return res
    on = _enable(realm_root, r["id"])
    return {"ok": on, "id": r["id"], "name": r["name"],
            **({} if on else {"error": "Added, but couldn't switch it on. Do it on Capabilities."})}


def _enable(realm_root, cid: str) -> bool:
    ok = {"v": False}

    def fn(cfg, _st):
        for it in ((cfg.get("toolkit") or {}).get("skills") or []):
            if it.get("id") == cid:
                it["enabled"] = True
                ok["v"] = True
    rj = _rj(realm_root)
    try:
        with util.file_lock(rj):
            cfg = json.loads(rj.read_text(encoding="utf-8-sig"))
            fn(cfg, None)
            if ok["v"]:
                util.write_json_atomic(rj, cfg)
    except (OSError, ValueError):
        swallowed(log, '_enable: failed; reported as not enabled')
        return False
    return ok["v"]


# --- the first brief -----------------------------------------------------------------------------

def brief_prompt(owner: str = "") -> str:
    """The message the wizard sends to the coordinator on the owner's behalf. Shown to the owner
    before it's sent, as it will appear in the thread."""
    who = f" I'm {owner}." if owner else ""
    return (f"Hello.{who} This is my first time using ARMADA. Please write me a short first brief: "
            "introduce yourself and each member of the team in a line, say what each of you can do "
            "for me, and suggest three things worth asking for first. Keep it under 250 words.")


def script() -> dict:
    """Everything the page needs from Alexander's script, as data."""
    return {"steps": [list(s) for s in wizard_script.STEPS], "lines": wizard_script.SCRIPT}


def recommended_for(template: str) -> list[dict]:
    return recommended.for_template(template)


def template_of(realm_root) -> str:
    try:
        return str(json.loads(_rj(realm_root).read_text(encoding="utf-8-sig")).get("template") or "scratch")
    except (OSError, ValueError):
        return "scratch"


def owner_of(realm_root) -> str:
    try:
        u = json.loads(_rj(realm_root).read_text(encoding="utf-8-sig")).get("user") or {}
        return str(u.get("name") or "")
    except (OSError, ValueError, AttributeError):
        return ""


def caps_on(realm_root) -> int:
    """How many capabilities are switched on in the realm (the done step's summary, after a reload)."""
    try:
        tk = json.loads(_rj(realm_root).read_text(encoding="utf-8-sig")).get("toolkit") or {}
    except (OSError, ValueError, AttributeError):
        return 0
    return sum(1 for kind in tk.values() if isinstance(kind, list)
               for it in kind if isinstance(it, dict) and it.get("enabled"))


def brief_done(realm_root, agent_id: str) -> bool:
    """Did the first brief happen (its thread has turns)? For the summary after a reload."""
    if not agent_id:
        return False
    d = Path(realm_root) / "agents" / agent_id / "threads"
    return any(p.is_dir() and any(p.iterdir()) for p in d.glob(BRIEF_THREAD + "*")) if d.is_dir() else False
