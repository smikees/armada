"""The realm's workspace root, and the ``{workspace}`` token that makes a realm portable.

A realm is a team, its memory and its jobs — none of which are tied to a machine. What ties them
is the *text* of the jobs: prompts say things like ``D:\\Work\\Development\\feeds.stamih.com``, and
on another computer that folder is somewhere else or spelled differently. In the live realm 191 of
193 absolute references sat in job prompts, and every one of them hung off a single root. That is
the whole problem: one variable, written out 193 times.

So the root becomes a setting (``workspace`` in realm.json) and prompts refer to ``{workspace}``,
which is expanded when a job runs. Move the realm, set the root once, and every job resolves.

Deliberately narrow:

* **One token.** Not a template language. ``{workspace}`` and nothing else, because every extra
  token is another thing that can be wrong in a prompt nobody reads until it fails at 03:00.
* **Expanded at run time, never written back.** The stored prompt keeps the token, so the realm
  stays portable no matter how many times it runs.
* **Unset means unchanged.** A realm with no workspace configured passes text through untouched —
  an old realm keeps working exactly as it did, and the token is opt-in.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import logging
from .util import swallowed
log = logging.getLogger(__name__)

TOKEN = "{workspace}"

# Matches the token tolerantly: {workspace}, {WORKSPACE}, { workspace }. People type it by hand.
_TOKEN_RE = re.compile(r"\{\s*workspace\s*\}", re.IGNORECASE)


def _realm_json(realm_root) -> dict:
    try:
        return json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
    except Exception:  # noqa — a missing or broken realm.json just means "not configured"
        swallowed(log, '_realm_json: failed; returning a fallback')
        return {}


def root(realm_root) -> str:
    """The realm's workspace root, or '' when it has none."""
    return str(_realm_json(realm_root).get("workspace") or "").strip()


def configured(realm_root) -> bool:
    return bool(root(realm_root))


def exists(realm_root) -> bool:
    """Is the configured root actually present on this machine? False when unconfigured."""
    r = root(realm_root)
    try:
        return bool(r) and Path(r).is_dir()
    except OSError:
        return False


def expand(text: str, realm_root) -> str:
    """Replace {workspace} with this machine's root.

    Leaves the text alone when no root is configured: silently expanding to an empty string would
    turn `{workspace}\\Finance` into `\\Finance`, which looks like a real path and is not — far
    worse than a job that plainly says it can't find {workspace}.
    """
    if not text:
        return text
    r = root(realm_root)
    if not r:
        return text
    # A function replacement, not a string: re.sub reads escapes in a string replacement, and a
    # Windows root like D:\Work would be mangled at the \W (or raise on a bad escape).
    clean = r.rstrip("\\/")
    return _TOKEN_RE.sub(lambda _m: clean, text)


def has_token(text: str) -> bool:
    return bool(text) and bool(_TOKEN_RE.search(str(text)))


def tokenize(text: str, old_root: str) -> tuple[str, int]:
    """Rewrite literal references to `old_root` as {workspace}. Returns (text, replacements).

    Job prompts are prose, so the same root appears in several spellings — a backslash path, a
    JSON-escaped one (``D:\\\\Work``), one with forward slashes from a Bash example, one immediately
    followed by markdown bold. Each is matched separately, longest form first, so a shorter variant
    can't eat the front of a longer one and leave a fragment behind.
    """
    if not text or not old_root:
        return text, 0
    base = str(old_root).rstrip("\\/")
    variants = [
        base.replace("\\", "\\\\"),      # JSON-escaped, as it appears inside a .json string
        base,                            # plain Windows
        base.replace("\\", "/"),         # forward slashes
    ]
    seen = set()
    out, n = text, 0
    for v in sorted(variants, key=len, reverse=True):
        if not v or v in seen:
            continue
        seen.add(v)
        # Case-insensitive: Windows paths are, and prompts are written by hand.
        pat = re.compile(re.escape(v), re.IGNORECASE)
        out, k = pat.subn(TOKEN, out)
        n += k
    return out, n


def detect_root(realm_root) -> str:
    """Guess the workspace root of a realm that predates this setting.

    Takes the most common two-segment prefix (``D:\\Work``) across the realm's job files. A guess,
    so it is offered to the owner rather than applied: it decides what 193 prompts point at.
    """
    counts: dict[str, int] = {}
    pat = re.compile(r"([A-Za-z]:(?:\\\\|\\|/)[^\\/\"'\s,;)\]]+)")
    rr = Path(realm_root)
    for ap in sorted((rr / "agents").glob("*")) if (rr / "agents").is_dir() else []:
        jd = ap / "jobs"
        for f in (sorted(jd.glob("*.json")) if jd.is_dir() else []):
            try:
                t = f.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            for hit in pat.findall(t):
                norm = hit.replace("\\\\", "\\").replace("/", "\\").rstrip("\\")
                if norm:
                    counts[norm] = counts.get(norm, 0) + 1
    if not counts:
        return ""
    # Most references wins; ties go to the shorter (more general) root.
    return sorted(counts.items(), key=lambda kv: (-kv[1], len(kv[0])))[0][0]


def migrate(realm_root, old_root: str, *, apply: bool = False) -> dict:
    """Rewrite literal `old_root` references in the realm's job prompts as {workspace}.

    Call with apply=False first: it reports exactly what would change, per file, without touching
    anything. This edits the owner's own prompt text across every job in the realm, so a preview
    that can be read before agreeing to it is the minimum.

    Only job files are rewritten. Threads and run reports are history — what an agent was told at
    the time was a real path, and rewriting the past to look portable would be a lie. Memory and
    mandates are left alone too: they are prose the owner wrote, and a silent edit there is a
    bigger surprise than a stale path.
    """
    rr = Path(realm_root)
    old = str(old_root or "").strip()
    out = {"ok": bool(old), "root": old, "files": [], "refs": 0, "applied": bool(apply)}
    if not old:
        out["error"] = "No workspace root given."
        return out
    adir = rr / "agents"
    for ap in sorted(adir.glob("*")) if adir.is_dir() else []:
        jd = ap / "jobs"
        for f in sorted(jd.glob("*.json")) if jd.is_dir() else []:
            try:
                text = f.read_text(encoding="utf-8-sig")
            except OSError as e:
                out["files"].append({"path": f"{ap.name}/{f.name}", "refs": 0, "error": str(e)[:80]})
                continue
            new, n = tokenize(text, old)
            if not n:
                continue
            # It must still be a job afterwards. Tokenizing inside a JSON string can only stay
            # valid if the replacement has no quotes or backslashes — it doesn't — but parsing is
            # cheap and a corrupted job file is not.
            try:
                json.loads(new)
            except json.JSONDecodeError as e:
                out["files"].append({"path": f"{ap.name}/{f.name}", "refs": n,
                                     "error": f"would not be valid JSON: {e}"[:90]})
                continue
            out["files"].append({"path": f"{ap.name}/{f.name}", "refs": n})
            out["refs"] += n
            if apply:
                from . import util
                util.write_text_atomic(f, new)
    # Dashboard sections can point at a folder of local assets, which is as machine-bound as a job
    # prompt and breaks the same way. `exported_from` is provenance — a record of where this realm
    # came from — so it stays literal; rewriting it would erase the only trace of its origin.
    #
    # Locked read-modify-write: realm.json is the same file the scheduler daemon and the web server
    # both write, so the read (cfg = _realm_json(rr)) and the write below have to be one critical
    # section, not two operations a concurrent writer could land between (Phase 2, 2.9).
    from . import util
    with util.file_lock(rr / "realm.json"):
        cfg = _realm_json(rr)
        secs = cfg.get("sections")
        if isinstance(secs, list):
            hits = 0
            for s in secs:
                if not isinstance(s, dict):
                    continue
                a = str(s.get("assets") or "")
                if not a:
                    continue
                new_a, k = tokenize(a, old)
                if k:
                    hits += k
                    if apply:
                        s["assets"] = new_a
            if hits:
                out["files"].append({"path": "realm.json (dashboard sections)", "refs": hits})
                out["refs"] += hits
                if apply:
                    util.write_json_atomic(rr / "realm.json", cfg)

    out["changed"] = sum(1 for f in out["files"] if not f.get("error"))
    out["failed"] = [f for f in out["files"] if f.get("error")]
    return out


def set_root(realm_root, new_root: str) -> dict:
    """Point the realm at a workspace root on this machine."""
    from . import util
    p = Path(realm_root) / "realm.json"
    with util.file_lock(p):
        cfg = _realm_json(realm_root)
        cfg["workspace"] = str(new_root or "").strip().rstrip("\\/")
        util.write_json_atomic(p, cfg)
    return {"ok": True, "workspace": cfg["workspace"], "exists": exists(realm_root)}
