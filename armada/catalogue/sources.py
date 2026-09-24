"""The catalogue's three mirrored/queried sources — Claude plugin marketplaces, the MCP registry,
anthropics/skills, and the skills you wrote yourself — normalised into one record shape, indexed,
and searched. Nothing here writes to a realm; that is catalogue.realm.

Split out of catalogue.py (Phase 2, 2.4/2.9) — a pure move, no behaviour change.
"""
from __future__ import annotations
import datetime as _dt
import json
import time
import urllib.parse
from pathlib import Path

from .. import util
from ._shared import (
    CURATED_OFFICIAL, CURATED_REGISTRY, INSTALLED, MARKETPLACE, MINE, ORIGIN_AUTHORED,
    ORIGIN_INSTALLED, PROVENANCE_FILE, REGISTRY, SKILLS, _MARKETPLACE_NAMES, _REGISTRY_LIMIT,
    _REGISTRY_URL, _REG_TTL, _SKILLS_API, _dir, _entry, _get_json, _index_path, _known_realms,
    _now, _reg_cache, _same_capability, _tokens, is_marketplace, marketplace_source, source_label,
)
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


def _marketplaces_dir() -> Path:
    return Path.home() / ".claude" / "plugins" / "marketplaces"


def from_marketplaces() -> tuple:
    """(entries, note, answered). Every plugin listed by every marketplace the CLI has cloned.

    Read from the clone rather than from `claude plugin list --available`, which only reports what
    is installed plus what the CLI feels like resolving. The clone is the marketplace's own
    manifest: complete, offline, and already on disk.
    """
    base = _marketplaces_dir()
    out, seen, labels = [], set(), {}
    if not base.is_dir():
        # Nothing to read is an answer, not a failure: a machine can legitimately have no
        # marketplaces set up. Reporting it as an error would put a red mark on the catalogue job
        # forever on a machine where nothing is wrong.
        return out, "no marketplaces configured", True, labels
    for mp in sorted(p for p in base.iterdir() if p.is_dir()):
        man = mp / ".claude-plugin" / "marketplace.json"
        try:
            data = json.loads(man.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        src = marketplace_source(mp.name)
        # What the marketplace calls itself, falling back to its folder. Anthropic's is
        # "claude-plugins-official", which reads better as "Claude marketplace" — the pill and the
        # filter should agree, and both should be a name rather than a repo slug.
        labels[src] = _MARKETPLACE_NAMES.get(mp.name) or str(data.get("name") or mp.name)
        for it in (data.get("plugins") or []):
            if not isinstance(it, dict) or not it.get("name"):
                continue
            a = it.get("author")
            author = (a.get("name") if isinstance(a, dict) else a) or ""
            cid = str(it["name"])
            key = (mp.name, cid)
            if key in seen:
                continue
            seen.add(key)
            out.append(_entry(
                src, "plugins", cid, cid, it.get("description", ""),
                author=str(author), category=str(it.get("category") or ""),
                homepage=str(it.get("homepage") or ""), curated=CURATED_OFFICIAL,
                install={"marketplace": mp.name, "plugin": cid,
                         "source": it.get("source"),
                         # Language-server plugins declare their binary in the MARKETPLACE
                         # manifest, not in their own folder — typescript-lsp's directory is a
                         # LICENSE and a README. Without carrying this, inspecting one finds an
                         # empty folder and calls a plugin that launches a process on your machine
                         # "instructions only".
                         "lspServers": it.get("lspServers") or {}}))
    n_mp = len(labels)
    return out, f"{len(out)} from {n_mp} marketplace" + ("" if n_mp == 1 else "s"), True, labels


# --- source: the official MCP registry -----------------------------------------------------------

def _registry_kind(srv: dict) -> str:
    """Connector or Extension — the same rule capscan uses, so a thing doesn't change bucket
    between the catalogue and the realm it lands in: a URL runs somewhere else, a package runs
    here."""
    return "connectors" if (srv.get("remotes") or []) else "extensions"


def _registry_entry(srv: dict) -> dict:
    cid = str(srv["name"])
    repo = (srv.get("repository") or {})
    return _entry(
        REGISTRY, _registry_kind(srv), cid,
        str(srv.get("title") or cid), srv.get("description", ""),
        # The registry carries no author or category fields. Saying so by leaving them empty is
        # the point — a filter that silently invents values is worse than one that visibly
        # doesn't apply to this source.
        author="", category="",
        homepage=str(srv.get("websiteUrl") or (repo.get("url") if isinstance(repo, dict) else "") or ""),
        curated=CURATED_REGISTRY, version=str(srv.get("version") or ""),
        install={"server": cid, "remotes": srv.get("remotes") or [],
                 "packages": srv.get("packages") or []})


def search_registry(q: str, limit: int = _REGISTRY_LIMIT, sample: bool = False) -> tuple:
    """(entries, note) for a live search of the MCP registry.

    Live rather than from the index because this source is not mirrored — see the module docstring.

    With no query and `sample` off, this returns nothing: the registry rides along with a search of
    the mirrored catalogue, and a search box nobody has typed in shouldn't fire a network call.
    `sample` is the one case where an empty query means something — you have filtered the page
    down to this source, so an empty pane would read as "the registry has nothing in it". What
    comes back is labelled as a sample, not as the catalogue, because an alphabetical first page of
    tens of thousands of self-published servers is not a shortlist of anything.
    """
    q = (q or "").strip()
    if not q and not sample:
        return [], ""
    key = f"{q}|{int(limit)}"
    hit = _reg_cache.get(key)
    if hit and (_dt.datetime.now().timestamp() - hit[0]) < _REG_TTL:
        return list(hit[1]), hit[2]
    url = f"{_REGISTRY_URL}?limit={int(limit)}&version=latest"
    if q:
        url += f"&search={urllib.parse.quote(q, safe='')}"
    data = _get_json(url)
    if not isinstance(data, dict):
        # Stale beats empty. An unreachable or rate-limited registry rendering as zero results is
        # indistinguishable from "the registry holds nothing like that", and the second is a much
        # stronger claim than we are in a position to make.
        if hit:
            return list(hit[1]), hit[2] + " · couldn’t refresh just now"
        return [], "the MCP registry couldn’t be reached"
    out = []
    for row in (data.get("servers") or []):
        srv = row.get("server") if isinstance(row, dict) else None
        if isinstance(srv, dict) and srv.get("name"):
            out.append(_registry_entry(srv))
    more = bool((data.get("metadata") or {}).get("nextCursor"))
    if not q:
        # The size comes from the daily count, not from a number written into this sentence.
        # It said "over twelve thousand" whatever the registry actually held, which is a
        # claim the code was in no position to keep current.
        total = registry_count_label()
        note = (f"showing {len(out)} of {total} — search to find a particular one" if total
                else f"showing {len(out)} — search to find a particular one")
    else:
        note = (f"{len(out)}+ matches — narrow the search to see the rest" if more
                else f"{len(out)} match{'' if len(out) == 1 else 'es'}")
    _reg_cache[key] = (_dt.datetime.now().timestamp(), list(out), note)
    return out, note


# Types only the MCP registry can supply. The mirrored sources hold plugins and skills; a connector
# or an extension exists nowhere else, so filtering to one of these with no source chosen has to
# reach the registry or the page truthfully has nothing to show — which is how "Extensions, any
# source" came to report nothing while "Extensions, MCP registry" reported forty.
REGISTRY_ONLY_KINDS = ("connectors", "extensions")


def registry_wanted(q: str, source: str, kind: str) -> bool:
    """Should this set of filters reach the live registry?

    One rule, no exceptions: a narrower filter must never return MORE than a looser one. So the
    registry is in whenever it has not been filtered OUT — naming another source is the only thing
    that excludes it.

    The tempting version of this had extra conditions (only on a search, only when the type is one
    the registry alone can supply) to keep opening the tab off the network. Every one of them broke
    the rule in some cell of the grid: with an empty box, "MCP registry" showed a sample and "all
    sources" showed less than that. Choosing a source is narrowing, and narrowing cannot add. The
    cost is one request per distinct query, cached for a few minutes, and a registry that can't be
    reached leaves the mirrored sources listed with a line saying so — so browsing still works with
    no network, it just has less in it.
    """
    return not source or source == REGISTRY


# --- source: anthropics/skills ---------------------------------------------------------------------

def from_skills() -> tuple:
    """(entries, note, answered). Anthropic's public Agent Skills, one per folder."""
    data = _get_json(_SKILLS_API)
    if not isinstance(data, list):
        return [], "unreachable", False, {}
    out = []
    for it in data:
        if not isinstance(it, dict) or it.get("type") != "dir" or not it.get("name"):
            continue
        cid = str(it["name"])
        out.append(_entry(
            SKILLS, "skills", cid, cid.replace("-", " ").strip().capitalize(),
            # The listing carries no description; the SKILL.md inside does, and reading 19 of them
            # is 19 more requests. It's fetched when the skill is actually added, which is also
            # when we need the rest of the file.
            "", author="Anthropic", category="", homepage=str(it.get("html_url") or ""),
            curated=CURATED_OFFICIAL, install={"repo": "anthropics/skills", "path": cid}))
    return out, f"{len(out)}", True, {}


# --- source: skills you wrote yourself ------------------------------------------------------------

def _skill_roots() -> list:
    """Every folder a skill you wrote could be sitting in, with the realm it belongs to.

    Two machine-level roots that any realm can already reach, plus each realm's own skills and its
    agents' — those last are the ones that matter here: a skill written for one agent in one realm
    is invisible everywhere else, and moving it currently means knowing where the folder is.
    """
    out = [(Path.home() / ".claude" / "skills", ""), (Path.home() / ".agents" / "skills", "")]
    for r in _known_realms():
        root = Path(r)
        try:
            name = json.loads((root / "realm.json").read_text(encoding="utf-8-sig")).get("name") or root.name
        except (OSError, ValueError):
            name = root.name
        out.append((root / "skills", name))
        adir = root / "agents"
        if adir.is_dir():
            for ad in sorted(p for p in adir.iterdir() if p.is_dir()):
                out.append((ad / "skills", name))
    return out


def _imported_skill_ids() -> set:
    """Skills sitting in a realm that the realm got from somewhere else.

    Since adding an Anthropic skill downloads its folder, a realm's `skills/` holds two different
    things that look identical on disk: skills you wrote, and copies of other people's. "You" is
    meant to answer "what have I built that I could move to another realm" — an Anthropic skill
    listed there is a skill you can already add from its own source, filed under the wrong author.

    The realm's own record settles it: an entry carries the catalogue key it was added by, so
    anything added from a source other than you is excluded. A skill with no entry at all is one
    you wrote by hand, which is exactly the case this list exists for.
    """
    out = set()
    for r in _known_realms():
        try:
            js = json.loads((Path(r) / "realm.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        for c in ((js.get("toolkit") or {}).get("skills") or []):
            key = str(c.get("catalogue_key") or "")
            if key and key.split("/", 1)[0] != MINE:
                out.add(str(c.get("id") or ""))
    return out


# What an agent writes beside a skill it made or fetched. A file in the skill's own folder rather
# than a ledger somewhere central: it travels when the folder is copied to another realm, it
# survives an export, and there is no single index to corrupt or to get out of step with the disk.
def read_provenance(skill_dir) -> dict:
    """{origin, source, by, at, why} for a skill folder, or {} if nothing was recorded.

    Never raises and never guesses: a folder with no record returns nothing, and the caller
    decides what that silence means. Writing "authored" into the blank would be inventing the one
    fact this file exists to establish.
    """
    try:
        d = json.loads((Path(skill_dir) / PROVENANCE_FILE).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict):
        return {}
    origin = str(d.get("origin") or "").strip().lower()
    if origin not in (ORIGIN_AUTHORED, ORIGIN_INSTALLED):
        return {}
    return {"origin": origin, "source": str(d.get("source") or ""),
            "by": str(d.get("by") or ""), "at": str(d.get("at") or ""),
            "why": str(d.get("why") or "")}


def _match_known(name: str, desc: str, entries: list) -> dict | None:
    """The mirrored catalogue entry this local folder appears to BE, or None.

    For the skills that were already on disk before anything recorded provenance — most of them
    came over from Claude Desktop. Claiming you wrote Anthropic's `docx` because it happens to sit
    in your skills folder is worse than saying nothing, so where the name matches something the
    catalogue already knows, that entry's own metadata is used instead of an invented author.
    """
    mine = _tokens({"id": name, "name": name, "description": desc})
    for e in entries or []:
        if e.get("kind") != "skills" or e.get("source") in (MINE, INSTALLED):
            continue
        if _same_capability(mine, _tokens(e)):
            return e
    return None


def from_mine(known: list | None = None) -> tuple:
    """(entries, note, answered, labels). Skills sitting on this machine, split by where they came
    from: ones you wrote (source "You") and ones that arrived from elsewhere ("Installed by an
    agent").

    They are listed beside Anthropic's so they can be moved between realms the same way anything
    else is added — a skill written for one agent in one realm is otherwise invisible everywhere
    else, and the only way to reuse it is to know where the folder is and copy it by hand.

    The split is read from the record an agent writes beside the skill (see read_provenance). With
    no record we fall back to the catalogue: a folder that matches something the mirrored sources
    already list plainly came from there, and takes that entry's author and description. Only a
    folder that matches nothing is called authored — which is the honest reading of "this exists,
    nobody has said where it came from, and it isn't anything we know about".
    """
    known = known if known is not None else (load().get("entries") or [])
    out, seen = [], set()
    imported = _imported_skill_ids()
    for root, realm_name in _skill_roots():
        if not root.is_dir():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            md = d / "SKILL.md"
            if not md.is_file() or d.name in seen or d.name in imported:
                continue
            seen.add(d.name)
            desc = ""
            try:
                from .. import sysskills
                meta, _body = sysskills._parse_front(md.read_text(encoding="utf-8-sig"))
                desc = str(meta.get("description") or "")
            except Exception:  # noqa — a malformed SKILL.md still lists, just without its blurb
                swallowed(log, 'from_mine: failed; ignored')
            name = str(d.name).replace("-", " ").strip().capitalize()
            prov = read_provenance(d)
            author, homepage, origin_note = "You", "", ""
            source = MINE
            if prov.get("origin") == ORIGIN_INSTALLED:
                source = INSTALLED
                author = ""
                homepage = prov.get("source") or ""
                origin_note = prov.get("source") or "installed by an agent"
            elif not prov:
                hit = _match_known(d.name, desc, known)
                if hit:
                    source = INSTALLED
                    author = hit.get("author") or ""
                    homepage = hit.get("homepage") or ""
                    desc = desc or hit.get("description") or ""
                    origin_note = source_label(hit.get("source") or "")
            out.append(_entry(
                source, "skills", d.name, name, desc,
                author=author, category="", homepage=homepage,
                # Only something you wrote is trusted by authorship. Anything that arrived from
                # elsewhere is exactly as reviewed as wherever it came from, which is usually
                # nobody — see _cap_tier, which reads this.
                curated=CURATED_OFFICIAL if source == MINE else "",
                install={"path": str(d), "from_realm": realm_name,
                         "origin": prov.get("origin") or ("installed" if source == INSTALLED
                                                          else ORIGIN_AUTHORED),
                         "origin_note": origin_note, "by": prov.get("by", ""),
                         "at": prov.get("at", ""), "why": prov.get("why", "")}))
    return out, f"{len(out)}", True, {}


# --- the index ------------------------------------------------------------------------------------

# Mirrored sources only. The registry is searched live and deliberately absent here: see
# search_registry() and the module docstring.
# One fetcher per WALK, not per source: from_mine makes a single pass over the skill folders and
# its results land in two sources, MINE or INSTALLED, depending on where each one came from.
# Giving INSTALLED a fetcher of its own would walk the disk twice and file every skill twice.
_FETCHERS = {MARKETPLACE: from_marketplaces, SKILLS: from_skills, MINE: lambda: from_mine()}


def _fetcher_key(source: str) -> str:
    """Which fetcher owns a source id. Marketplace ids carry the marketplace name after a colon,
    so they all belong to the one fetcher that reads the clones."""
    s = str(source or "")
    if is_marketplace(s):
        return MARKETPLACE
    # Both local sources come out of the one walk over the skill folders, so they share a fetcher
    # — and, just as importantly, share the clear-and-replace step in refresh().
    return MINE if s == INSTALLED else s


def _fetcher_for(source: str):
    return _FETCHERS.get(_fetcher_key(source))


def load() -> dict:
    """The stored index, or an empty one. Never raises."""
    try:
        d = json.loads(_index_path().read_text(encoding="utf-8-sig"))
        if isinstance(d, dict) and isinstance(d.get("entries"), list):
            return d
    except (OSError, ValueError):
        pass
    return {"entries": [], "sources": {}, "fetched": ""}


def refresh(only: str = "") -> dict:
    """Re-fetch the sources and write the index. Returns a per-source report.

    A source that fails keeps whatever it had, with the timestamp of when that data was actually
    good — so the page can say "the registry is a week old" instead of quietly showing a short
    list as though it were complete. Refreshing all three is not atomic across sources on purpose:
    two working sources shouldn't be held back by one that's down.
    """
    cur = load()
    by_source = {}
    for e in cur.get("entries", []):
        # Drop anything from a source we no longer mirror. The registry was mirrored once, before
        # it turned out to hold twelve thousand servers; without this, an index written back then
        # would keep serving that stale slice forever as though it were the whole thing.
        if _fetcher_for(e.get("source")):
            by_source.setdefault(e.get("source"), []).append(e)
    meta = {k: v for k, v in (cur.get("sources") or {}).items() if k in _FETCHERS}
    all_labels = dict(cur.get("source_labels") or {})
    for src, fetch in _FETCHERS.items():
        if only and src != only:
            continue
        try:
            entries, note, answered, labels = fetch()
        except Exception as e:  # noqa — a source must never take the catalogue down
            swallowed(log, 'refresh: failed; recorded as an error')
            entries, note, answered, labels = [], f"error: {type(e).__name__}", False, {}
        if answered:
            all_labels.update(labels)
            # Replace this fetcher's entries wholesale, and only now — clearing them before the
            # fetch threw away the last good list the moment a source went down, which is the one
            # thing the keep-what-we-had rule exists to prevent.
            for k in [k for k in by_source if _fetcher_key(k) == src]:
                by_source.pop(k, None)
            for e in entries:
                by_source.setdefault(e.get("source"), []).append(e)
            meta[src] = {"count": len(entries), "fetched": _now(), "note": note, "ok": True}
        else:
            # Keep the last good list rather than letting the catalogue go quietly short. The
            # source didn't say it was empty — it didn't say anything.
            prev = meta.get(src) or {}
            kept = sum(len(v) for k, v in by_source.items() if _fetcher_key(k) == src)
            meta[src] = {"count": kept, "fetched": prev.get("fetched", ""),
                         "note": note, "ok": False}
    out = {"entries": [e for src in sorted(by_source) for e in (by_source.get(src) or [])],
           "sources": meta, "source_labels": all_labels, "fetched": _now()}
    try:
        _dir().mkdir(parents=True, exist_ok=True)
        util.write_json_atomic(_index_path(), out)
    except OSError:
        pass
    return {"ok": True, "total": len(out["entries"]), "sources": meta}


def age_hours() -> float:
    """How old the index is, in hours. -1 when it has never been fetched."""
    try:
        t = _dt.datetime.fromisoformat(load().get("fetched") or "")
    except ValueError:
        return -1.0
    if t.tzinfo is None:
        t = t.astimezone()
    return (_dt.datetime.now().astimezone() - t).total_seconds() / 3600.0


# --- querying -------------------------------------------------------------------------------------

def facets(entries: list) -> dict:
    """Which filter values actually exist in a given set of entries.

    Computed from the entries in hand rather than from a fixed list, because the sources don't
    agree on what they carry: the marketplace has authors and categories, the registry has
    neither. A filter offering values that can never match is a filter that looks broken.
    """
    def vals(field):
        seen = {}
        for e in entries:
            v = (e.get(field) or "").strip()
            if v:
                seen[v] = seen.get(v, 0) + 1
        # Alphabetical, not by count. A dropdown is somewhere you look a value up, and the only
        # order you can guess in advance is A–Z; by-frequency means hunting for a name whose
        # position depends on data you can't see.
        return sorted(seen.items(), key=lambda kv: kv[0].lower())
    return {"source": vals("source"), "kind": vals("kind"),
            "author": vals("author"), "category": vals("category")}


def search(entries: list, q: str = "", source: str = "", kind: str = "",
           author: str = "", category: str = "") -> list:
    """Filter the index. Plain substring matching on name + description — the index is a few
    thousand short records held in memory, so anything cleverer would be cost without benefit."""
    ql = (q or "").strip().lower()
    out = []
    for e in entries:
        if source and e.get("source") != source:
            continue
        if kind and e.get("kind") != kind:
            continue
        if author and e.get("author") != author:
            continue
        if category and e.get("category") != category:
            continue
        if ql and ql not in f"{e.get('name','')} {e.get('id','')} {e.get('description','')}".lower():
            continue
        out.append(e)
    return out


# --- ordering -------------------------------------------------------------------------------------
# Neither source carries a popularity signal. The marketplace manifest has no stars, installs or
# downloads; the MCP registry returns only status/publishedAt/updatedAt/isLatest and ignores a
# sort parameter. There used to be a "Suggested" order built from weak proxies (Anthropic first,
# then "already in your realms", then vendors publishing several) — dropped in the reframe
# (ADR-004): browsing is gone, so there is no default list to rank. Results are sorted
# alphabetically by whoever calls search(); see _cat_results in webui/catalogue.py.


_COUNT_PAGE = 100
# Headroom, not a guess: a full walk on 2026-09-20 took 337 pages for 33,657 servers. At 250 the
# count stopped dead on the ceiling and reported "25,000+" — a number that was really "this is as
# far as we were allowed to look", dressed as a fact about the registry. 800 pages is 80,000
# servers, which leaves room for it to more than double before anyone has to think about this
# again; the walk costs about four minutes once a day, in the background.
_COUNT_MAX_PAGES = 800
# Pacing for the count. A public index does not owe us a hundred requests in a second.
_COUNT_PACE = 0.15
_COUNT_RETRIES = 3
_COUNT_BACKOFF = 1.0


def count_registry() -> tuple:
    """(count, capped) — latest-version servers in the registry, or (-1, False) if unreachable.

    Paced and retried, because the first version wasn't and it showed: the count ran, the second
    request came back empty, and the job recorded "100, capped" — which the filter then displayed
    as "100+" beside a source holding tens of thousands. A hundred-odd back-to-back requests is
    exactly the pattern a public API rate-limits, and a rate-limited page is not the end of the
    list. This is a daily background job; spending a few seconds on pauses is free.

    `capped` still means "at least this many" — it is set when we genuinely run out of pages or
    give up on a page after retrying, and the label says "+" so the number is never read as final.
    """
    n, cursor = 0, ""
    for _page in range(_COUNT_MAX_PAGES):
        url = f"{_REGISTRY_URL}?limit={_COUNT_PAGE}&version=latest"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor, safe="")
        data = None
        for attempt in range(_COUNT_RETRIES):
            data = _get_json(url)
            if isinstance(data, dict):
                break
            time.sleep(_COUNT_BACKOFF * (attempt + 1))
        if not isinstance(data, dict):
            return (-1, False) if n == 0 else (n, True)   # partial: at least n, honestly capped
        n += len(data.get("servers") or [])
        cursor = ((data.get("metadata") or {}).get("nextCursor") or "")
        if not cursor:
            return n, False
        time.sleep(_COUNT_PACE)
    return n, True


# One walk at a time. The daily job and the Refresh button can both ask for a count, and two
# walks would double a few hundred requests to a public index for one answer.
_counting = False


def refresh_registry_count() -> dict:
    """Count the registry and remember the answer on the index. Best-effort, never raises."""
    global _counting
    if _counting:
        return {"ok": False, "detail": "already counting"}
    _counting = True
    try:
        return _refresh_registry_count()
    finally:
        _counting = False


def _refresh_registry_count() -> dict:
    n, capped = count_registry()
    if n < 0:
        return {"ok": False, "detail": "the MCP registry couldn't be reached"}
    idx = load()
    idx["registry_count"] = n
    idx["registry_count_capped"] = bool(capped)
    idx["registry_counted"] = _now()
    try:
        _dir().mkdir(parents=True, exist_ok=True)
        util.write_json_atomic(_index_path(), idx)
    except OSError:
        pass
    return {"ok": True, "count": n, "capped": capped}


def registry_count_label(idx: dict | None = None) -> str:
    """'12,345' or '25,000+' — or '' before the first count, because a guess is not a count."""
    idx = idx or load()
    n = idx.get("registry_count")
    if not isinstance(n, int) or n <= 0:
        return ""
    return f"{n:,}+" if idx.get("registry_count_capped") else f"{n:,}"


# --- inspection -----------------------------------------------------------------------------------
# What a capability can actually reach, worked out at the moment you add it rather than eagerly for
# a catalogue of thousands. The answer sets the risk tier, so it has to come from something we can
# point at: a transport, a folder on disk, a declared component. Never from a guess about intent.

