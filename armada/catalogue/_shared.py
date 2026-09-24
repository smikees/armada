"""Constants and cross-cutting matching/identity helpers shared by both catalogue.sources and
catalogue.realm — every source label, the file-storage paths, the generic HTTP-JSON fetch, and the
name/id matching (_tokens/_same_capability*) that both "is this already in the mirrored index" and
"is this already in the realm" checks are built from.

Split out of catalogue.py (Phase 2, 2.4/2.9) — a pure move, no behaviour change. This is the base
layer: it imports nothing from .sources or .realm at module level (one exception, source_label's
own call to sources.load(), is a local import to avoid a cycle — sources.py needs the constants
and helpers defined here, so the dependency can only run one way at module scope).
"""
from __future__ import annotations
import datetime as _dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from .. import util


MARKETPLACE = "marketplace"
REGISTRY = "mcp-registry"
SKILLS = "anthropic-skills"
MINE = "mine"
# A skill that arrived on this machine from somewhere else without going through the Catalogue —
# an agent fetched it from a GitHub link, or it came over from Claude Desktop. It is on disk
# exactly like one you wrote, and for moving it to another realm that is all that matters; for
# deciding whether to trust it, it is the opposite. Two sources rather than one badge, because
# "show me everything that came off the internet" is the review you actually want to run.
INSTALLED = "installed"

# A source is what you'd point at and name, so "marketplace" on its own isn't one: a machine can
# have several, and which one an entry came from is the whole provenance story. Marketplace
# sources are therefore "marketplace:<its name>", and the label is the name the marketplace gives
# itself. MARKETPLACE stays as the prefix everything else keys off.
SOURCE_LABEL = {
    MARKETPLACE: "Claude plugin marketplaces",
    REGISTRY: "MCP registry",
    SKILLS: "Anthropic skills",
    MINE: "Created by you",
    INSTALLED: "Installed by an agent",
}


# Anthropic's own directory calls itself by its repo slug; the pill and the filter should read as
# a name someone would say out loud. "Claude marketplace" was also vague about what it holds —
# everything in it is a plugin, which is what a Claude plugin marketplace is.
_MARKETPLACE_NAMES = {"claude-plugins-official": "Claude plugin marketplace"}


def marketplace_source(name: str) -> str:
    return f"{MARKETPLACE}:{name}"


def is_marketplace(source: str) -> bool:
    return str(source or "").split(":", 1)[0] == MARKETPLACE


def source_label(source: str, labels: dict | None = None) -> str:
    """The human name for a source id, including per-marketplace ones.

    `labels` is the index's source_labels map — pass it when you already have the index loaded, so
    rendering a list of 300 cards doesn't read the file 300 times.
    """
    if source in SOURCE_LABEL:
        return SOURCE_LABEL[source]
    if is_marketplace(source):
        name = str(source).split(":", 1)[-1]
        # Our own override wins over whatever was stored at fetch time. The stored labels are a
        # snapshot from the last refresh, so without this a rename here would sit invisible until
        # the daily job next ran — the page would keep saying the old name for up to a day, with
        # nothing on screen to explain why.
        if name in _MARKETPLACE_NAMES:
            return _MARKETPLACE_NAMES[name]
        if labels is None:
            # Local, not module-level: sources.py imports the constants and matching
            # helpers in THIS file, so a top-of-file import the other way would be a cycle.
            from .sources import load
            labels = load().get("source_labels") or {}
        return labels.get(source) or name
    return str(source or "")

# "official" = listed in a directory somebody curates. "registry" = an open index where listing
# implies no review by anyone. _cap_tier reads this, so the distinction has to survive the trip.
CURATED_OFFICIAL = "official"
CURATED_REGISTRY = "registry"

_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
_SKILLS_API = "https://api.github.com/repos/anthropics/skills/contents/skills"
_UA = "ARMADA (local agent cockpit)"

# One page of live registry results per search. 100 rather than 40 because the type filter is
# applied on our side — the registry ignores `transport` and `packageType`, so the only way to show
# "connectors in the registry" is to fetch a page and sort it out here. A bigger page makes that
# filtering less lossy. 100 is the API's own ceiling: limit=1000 answers 422.
_REGISTRY_LIMIT = 100
_TIMEOUT = 20

# Registry answers, briefly remembered. Every filter change re-renders the results server-side and
# that used to mean a fresh network call each time — at typing speed the registry starts refusing,
# and a refused call rendered as "no results" rather than as a problem. Keyed by query, with the
# last good answer kept past its expiry so a failure shows yesterday's list instead of nothing.
_REG_TTL = 180
_reg_cache: dict = {}


def _dir() -> Path:
    return util.data_dir() / "catalogue"


def _index_path() -> Path:
    return _dir() / "index.json"


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _get_json(url: str):
    """One HTTP GET returning parsed JSON, or None. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


# --- the record ------------------------------------------------------------------------------------

def _entry(source: str, kind: str, cid: str, name: str, description: str = "", *,
           author: str = "", category: str = "", homepage: str = "", curated: str = "",
           install: dict | None = None, version: str = "") -> dict:
    """One catalogue record. `key` is what the UI and the realm both refer to it by.

    Keyed by source+kind+id rather than by id alone: the same name can legitimately exist in two
    sources (a plugin and an MCP server can share a vendor's name), and collapsing them would make
    "add this one" ambiguous at exactly the moment it matters.
    """
    return {
        "key": f"{source}/{kind}/{cid}".lower(),
        "id": cid, "name": name or cid, "description": (description or "").strip(),
        "kind": kind, "source": source, "author": author, "category": category,
        "homepage": homepage, "curated": curated, "version": version,
        "install": install or {},
    }


# --- source: Claude plugin marketplaces --------------------------------------------------------


def _known_realms() -> list:
    """Realm folders from ARMADA's own registry. Read directly rather than through serve, which
    would drag the whole web layer into a module the daily job imports."""
    try:
        items = json.loads((util.data_dir() / "realms.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    return [str(i.get("path")) for i in items if isinstance(i, dict) and i.get("path")]


PROVENANCE_FILE = "armada.json"

ORIGIN_AUTHORED = "authored"
ORIGIN_INSTALLED = "installed"


def _norm_id(s) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


# Below this, a shared tail stops meaning anything: "mcp", "api", "ai" would match half the index.
_MATCH_MIN = 8


def _tokens(e: dict) -> set:
    """The forms of a capability's identity worth matching on.

    One capability is named three different ways by three different systems. IBKR is
    `com.ibkr/interactive-brokers-ibkr` in the MCP registry, `Interactive Brokers (IBKR)` as its
    title, and `claude.ai Interactive Brokers (IBKR)` once Claude has connected it — so comparing
    ids alone says the connector you have been using for weeks is not in your realm.
    """
    out = set()
    for v in (e.get("id"), e.get("name")):
        s = str(v or "")
        n = _norm_id(s)
        if n:
            out.add(n)
        tail = _norm_id(s.rsplit("/", 1)[-1])                # com.ibkr/foo -> foo
        if tail:
            out.add(tail)
        # Claude names a connector it set up `claude_ai_<the actual name>`. That prefix is Claude's
        # bookkeeping, not part of what the thing is called, and leaving it in is why the realm's
        # IBKR connector shared no exact token with the registry's `interactive-brokers-ibkr`.
        bare = _norm_id(re.sub(r"^claude[_.]?ai[_.\s-]*", "", s, flags=re.I))
        if bare:
            out.add(bare)
    return {x for x in out if len(x) >= 3}


def _same_capability(cat_tokens: set, realm_tokens: set) -> bool:
    """Do these name the same thing? Exact on any token, else containment above a length floor.

    Fuzzy on purpose, and the asymmetry of the costs is why: a false "already added" costs you a
    second look at a card, a missed one costs you a duplicate capability in the realm and a
    confusing failure when you try to add it.
    """
    if cat_tokens & realm_tokens:
        return True
    for a in cat_tokens:
        for b in realm_tokens:
            if len(a) >= _MATCH_MIN and len(b) >= _MATCH_MIN and (a in b or b in a):
                return True
    return False


def _looks_like_id(s: str) -> bool:
    """A reverse-DNS or slug-shaped string, as opposed to something written for a reader."""
    s = str(s or "")
    return bool(re.match(r"^[a-z0-9]+([.\-_][a-z0-9]+){2,}$", s))


def _same_capability_exact(cat_tokens: set, realm_tokens: set) -> bool:
    """Same thing, on a name both sides actually share — no containment.

    _same_capability is deliberately fuzzy, and for the "you already use this" hint that is the
    right trade: a false positive costs a second look at a card. Here the costs are reversed. This
    decides whether to REWRITE a realm record's name, publisher and trust badge, and a wrong
    answer replaces the thing the owner has been using with a stranger's project that happens to
    have a similar name.

    A real case: the realm's `windows-mcp` matched `windows-mcp-server` by containment \u2014 a
    different author's server \u2014 while the project it actually is, `CursorTouch/Windows-MCP`,
    matches exactly. Containment picked the wrong one.
    """
    return bool(cat_tokens & realm_tokens)


def _command_matches(cap: dict, entry: dict) -> bool:
    """Does the command this server actually runs match what the catalogue entry declares?

    Real evidence, where a name comparison is only a resemblance. The realm's `windows-mcp` runs
    `uvx windows-mcp`; the registry entry io.github.CursorTouch/Windows-MCP declares a pypi package
    named `windows-mcp` with runtimeHint `uvx`, and the other candidate for that name declares
    `windows-management-mcp-server`, which the command does not mention. One of those is a fact
    about the machine and the other is a coincidence of wording.
    """
    cmd = str(cap.get("command") or "").lower()
    if not cmd:
        return False
    for pkg in ((entry.get("install") or {}).get("packages") or []):
        ident = str((pkg or {}).get("identifier") or "").strip().lower()
        # Whole-word: `windows-mcp` must not be satisfied by `windows-mcp-server-extra`.
        if ident and re.search(r"(?<![a-z0-9._-])" + re.escape(ident) + r"(?![a-z0-9._-])", cmd):
            return True
    for rem in ((entry.get("install") or {}).get("remotes") or []):
        url = str((rem or {}).get("url") or "").strip().lower()
        if not url:
            continue
        # Either way round, and on the host as a fallback. The realm's IBKR connector points at
        # https://api.ibkr.com/v1/api/mcp while the registry entry declares .../mcp-public — the
        # authenticated endpoint and the open one, the same service either way. A plain
        # "is the declared URL inside the command" test says no to that, which is the wrong
        # answer for the reason it gives.
        if url in cmd or cmd in url:
            return True
        if _url_host(url) and _url_host(url) == _url_host(cmd):
            return True
    return False


def _url_host(s: str) -> str:
    m = re.search(r"https?://([^/\s]+)", str(s or "").lower())
    return m.group(1) if m else ""


