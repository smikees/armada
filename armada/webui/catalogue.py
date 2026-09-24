"""Catalogue tab rendering: search results, filters, the bring-a-link review report, and the
info box (ADR-004) — everything that renders from CATALOGUE/registry data rather than the realm's
own toolkit.

Split out of capabilities.py (Phase 2, 2.4) — a pure move, no behaviour change. capabilities.py
keeps the User tab, System tab, and the cross-cutting trust-model helpers every capability card
(there or here) is built from; this module imports the few of those it needs
(_KIND_SINGULAR, _cap_iconcluster, _cap_tier_why). _realm_skills, the page that stitches User +
System + this tab together, stays in capabilities.py and imports _catalogue_pane/_CAT_JS from here
locally — the same way this module already reached back into armada.catalogue (the data layer)
before the split, avoiding a module-level import cycle between the two.
"""
from __future__ import annotations
import json, re
from ..icons import _icon
from ._base import E, _J, _md_inline, _md, _pill, _tone
from .agentbits import _filter_dropdown
from .capabilities import _KIND_SINGULAR, _cap_iconcluster, _cap_tier_why
from ..assets import CAT_JS as _CAT_JS_ASSET
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


# Script body lives in webui/static/js/cat.js (Phase 2, 2.1).
_CAT_JS = (
    _CAT_JS_ASSET +
    # A small bouncing-dots "working" indicator, reused for the bring-a-link status line and the
    # results-list spinner — one component rather than two. currentColor so it picks up whatever
    # colour context it's dropped into.
    '<style>.mc-catdots{display:inline-flex;gap:3px;align-items:center;vertical-align:middle}'
    '.mc-catdots i{width:4px;height:4px;border-radius:50%;background:currentColor;display:block;'
    'animation:mc-catdots-a 1.1s ease-in-out infinite}'
    '.mc-catdots i:nth-child(2){animation-delay:.16s}.mc-catdots i:nth-child(3){animation-delay:.32s}'
    '@keyframes mc-catdots-a{0%,80%,100%{opacity:.25}40%{opacity:1}}'
    '@media (prefers-reduced-motion:reduce){.mc-catdots i{animation:none;opacity:.6}}</style>')

# ---- Catalogue: what you could add -------------------------------------------------------------

_CAT_PAGE = 24


def _cat_pill(text: str, col: str = "var(--text-muted)") -> str:
    return _pill(E(text), _tone(col))


def _cat_card(e: dict, publisher: str, where: list, labels: dict, here: bool = False) -> str:
    """One catalogue entry.

    No risk tier here, deliberately. A tier is a claim about what something can reach, and for
    almost everything in this list we have not looked yet — 244 of the marketplace's 297 entries
    are a git URL and nothing more. Showing "Trusted" against an uninspected entry is exactly the
    bug that was just fixed in the User tab; the inspection happens when you add it, and the tier
    appears there.

    No type pill either: the icon on the left already says what kind it is, and so does the filter
    you used to get here. Two of them was the same fact three times on one line.

    `publisher` used to be `why` — the reason a card sat where it did in the Suggested order. That
    order is gone (ADR-004: browsing is gone, so there is nothing left to rank), and with it the
    need to justify a position. What is worth keeping is just the fact, when there is one: who made
    this.
    """
    from .. import catalogue as cat
    kind = e.get("kind") or ""
    ic = {"connectors": "cap-connector", "extensions": "puzzle",
          "skills": "cap-skill", "plugins": "cap-plugin"}.get(kind, "plug")
    src = e.get("source") or ""
    _org = str((e.get("install") or {}).get("origin_note") or "") if src == cat.INSTALLED else ""
    # One name per source. The pill used to say "open registry" while the filter said "MCP
    # registry" — the same thing twice, which reads as two sources. The amber tint is what carries
    # "nobody vetted this".
    src_pill = _cat_pill(cat.source_label(src, labels),
                         "var(--status-warn)" if e.get("curated") == "registry" else "var(--text-muted)")
    where_chip = (f'<span style="font-size:11px;color:var(--status-ok);display:inline-flex;align-items:center;gap:4px">'
                  f'{_icon("circle-check",12)}in {E(", ".join(where[:2]))}</span>') if where else ""
    # The chip reports every realm; the button asks only about this one. They used to be the same
    # test, so a capability added to ANY realm came back "Added", greyed out, in all of them — and
    # could never be added to the realm you were actually looking at. The catalogue is the same
    # list whichever realm you are in, and this was the one place it was not.
    btn = (f'<button class="btn btn-secondary" disabled title="Already in this realm" '
           f'style="font-size:11.5px;padding:4px 10px;white-space:nowrap;opacity:.5">Added</button>'
           if here else
           f'<button class="btn btn-secondary btn-sm" style="white-space:nowrap" '
           f'onclick="mcCatAdd(this,{_J(e["key"])})">Add to realm</button>')
    # Joined with " \u00b7 " rather than always leading with one fixed field, because publisher
    # is now often blank (most of the registry declares no author) and a line starting with the
    # separator reads as broken.
    meta_bits = []
    if publisher:
        meta_bits.append(f'by {E(publisher)}')
    if e.get("homepage"):
        meta_bits.append(f'<a href="{E(e["homepage"])}" target="_blank" rel="noopener" '
                         f'style="color:var(--color-accent-2);text-decoration:none">Source \u2197</a>')
    # Where an installed skill actually came from, on the card rather than a click away: it is the
    # whole reason this source is separate from the one you wrote.
    if _org:
        meta_bits.append(f'from {E(_org)}')
    # A local skill has no homepage to link to \u2014 its "source" is a folder on this computer, so
    # the link opens that instead.
    if src in (cat.MINE, cat.INSTALLED):
        meta_bits.append(f'<a onclick="mcCatReveal(event,{_J(e["key"])})" '
                         f'style="color:var(--color-accent-2);cursor:pointer">Go to file</a>')
    meta = ' \u00b7 '.join(meta_bits)
    return (f'<div class="mc-cat-card mc-frame" style="border-radius:var(--r);padding:11px 13px;'
            f'display:grid;grid-template-columns:1fr auto;gap:12px;align-items:start;margin-bottom:8px">'
            f'<div style="min-width:0">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
            f'<span style="display:flex;flex:none;color:var(--text-muted)" title="{E(_KIND_SINGULAR.get(kind, kind))}">{_icon(ic,15)}</span>'
            f'<span style="font-family:var(--font-heading);font-weight:600;font-size:13.5px">{E(e.get("name") or e.get("id"))}</span>'
            f'{src_pill}{where_chip}</div>'
            + (f'<div style="font-size:12px;color:var(--text-muted);line-height:1.45;margin-top:4px;'
               f'max-width:640px">{E(e.get("description") or "")}</div>' if e.get("description") else "")
            + (f'<div style="font-size:11px;color:var(--text-42);'
               f'margin-top:5px">{meta}</div>' if meta else "")
            + f'</div><div>{btn}</div></div>')


def _cat_results(realm, realm_root, q: str = "", source: str = "", kind: str = "",
                 author: str = "", category: str = "", page: int = 0) -> str:
    """The results area — re-rendered on its own whenever a filter changes.

    ONE list. The registry used to render as a second block below the first, fetched by a call
    that received only the search text, so the type, publisher and category filters applied to
    half the page and not the other half: picking Extensions returned forty entries of which
    thirty-six were connectors. And because the registry joined in only when it was named as the
    source, clearing the source filter — asking for strictly more — dropped forty results to none.

    So the registry's entries are now merged into the same list, pass through the same `search`,
    sort together and share the pager. The one thing that stays special is that it is queried
    rather than mirrored, which the note above the results says out loud.

    No more "Suggested" order (ADR-004): the reframe drops browsing, so there is no default list
    left to rank — what's shown is always the answer to a filter, sorted alphabetically.
    """
    from .. import catalogue as cat
    idx = cat.load()
    entries = idx.get("entries") or []
    labels = idx.get("source_labels") or {}
    hits = cat.search(entries, q=q, source=source, kind=kind, author=author, category=category)

    # The registry's answer for this search. With no query, sample it rather than showing nothing:
    # ADR-004 dropped browsing across the whole catalogue, but a Source filter you can pick and
    # then never see contribute anything reads as broken, not as "search instead" — Mihai's call
    # after seeing it (2026-09-21). The registry API caps a page at 100 regardless. This still
    # costs no network call on the page-render path (CLAUDE.md): _cat_results only ever runs from
    # /api/catalogue, fetched once the Catalogue tab is actually opened — see test_cap_page_speed.py.
    reg_all, reg_note = cat.search_registry(q, sample=True)
    reg = []
    if cat.registry_wanted(q, source, kind):
        # The query has already been applied by the registry itself, and its matching is looser
        # than a substring test — re-applying `q` here would throw away good answers. Everything
        # else is ours to enforce, and must be, or the filter means one thing on half the page.
        # `reg_all` stays unfiltered: costing "what would Extensions return" against a list already
        # narrowed to connectors finds nothing, and greys out an option that has 26 behind it.
        reg = cat.search(reg_all, kind=kind, author=author, category=category)
    else:
        reg_note = ""      # another source is named; the registry is no part of THIS answer

    # One matching pass over everything on screen, so a live registry result gets the same
    # "already in your realms" mark the mirrored ones do.
    inst = _cat_installed(realm_root, hits + reg)
    # Separately: which are in THIS realm. That is the button's question; `inst` answers the
    # chip's, which is "have you used this anywhere".
    mine = set(_cat_installed(realm_root, hits + reg, only_here=True))
    # Alphabetical, on the name a card actually shows — not a claim about quality, just a stable,
    # explainable order (see test_suggested_is_not_a_popularity_claim in test_catalogue.py).
    hits = sorted(hits + reg, key=lambda e: (e.get("name") or e.get("id") or "").lower())
    total = len(hits)
    page = max(0, int(page or 0))
    shown = hits[page * _CAT_PAGE:(page + 1) * _CAT_PAGE]
    cards = "".join(_cat_card(e, e.get("author") or "", inst.get(e["key"]) or [],
                              labels, here=e["key"] in mine)
                    for e in shown)
    if not shown:
        cards = ('<div style="font-size:12.5px;color:var(--text-muted);padding:18px 0">'
                 'Nothing matches. Try fewer filters, or a different word.</div>')
    pager = ""
    if total > _CAT_PAGE:
        last = (total - 1) // _CAT_PAGE
        def btn(p, label, on):
            if not on:
                return (f'<span style="font-size:12px;padding:4px 10px;color:'
                        f'var(--text-30)">{label}</span>')
            return (f'<button class="btn btn-secondary btn-sm" '
                    f'onclick="mcCatPage({p})">{label}</button>')
        back, fwd = btn(page - 1, "\u2039 Back", page > 0), btn(page + 1, "Next \u203a", page < last)
        lo, hi = page * _CAT_PAGE + 1, min(total, (page + 1) * _CAT_PAGE)
        pager = (f'<div style="display:flex;align-items:center;gap:10px;margin-top:14px">{back}'
                 f'<span style="font-size:11.5px;color:var(--text-muted)">{lo}\u2013{hi} of {total}'
                 f'</span>{fwd}</div>')
    # What the registry contributed, said once above the list rather than as a second heading
    # inside it. search_registry always hands back a note when it was asked (sample or search),
    # so this fires whenever the registry is part of the current filter at all — "showing 100
    # of 33,657 — search to find a particular one" with nothing typed, a match count once typed.
    note = ""
    if reg_note:
        note = (f'<div style="font-size:11.5px;color:var(--text-muted);margin:0 0 10px;'
                f'display:flex;align-items:center;gap:6px">'
                f'<span style="text-transform:uppercase;letter-spacing:.06em;font-size:10.5px;'
                f'color:var(--text-42)">MCP registry</span>'
                f'<span>{E(reg_note)}</span></div>')
    # Which options in each dropdown would come back empty, computed from the very entries this
    # answer was built from, and carried to the page so the menus can grey them. Server-side
    # because only the server has the registry's contribution in hand; as data rather than as
    # re-rendered markup because the filter bar holds the search box, and swapping that mid-word
    # takes the caret with it.
    empties, dead = _cat_empty_options(entries, reg_all, q=q, source=source, kind=kind,
                                       author=author, category=category)
    avail = (f'<template id="cat-avail" data-empty="{E(json.dumps(empties))}" '
             f'data-dead="{E(json.dumps(dead))}"></template>')
    return f'<div id="cat-results">{avail}{note}{cards}{pager}</div>'


def _cat_empty_options(entries: list, reg_all: list, *, q="", source="", kind="",
                       author="", category="") -> tuple:
    """({facet: [values that would return nothing]}, [facets with nothing left to offer]).

    A dropdown offering a choice that can only ever empty the page is a small lie the page tells
    about itself — "MCP registry" alongside "Skills" reads as though the registry might hold some.
    Each option is costed by re-running the same filter with that one value swapped in, over the
    entries already fetched. A few dozen passes over a few hundred records: cheaper than the
    request that produced them.

    The currently chosen value is never marked empty. If you have filtered yourself into a corner
    the page has to keep showing you which corner, or there is no way to read your way out of it.
    """
    from .. import catalogue as cat

    def hits(**over):
        f = {"source": source, "kind": kind, "author": author, "category": category}
        f.update(over)
        n = len(cat.search(entries, q=q, **f))
        # The registry leg follows the same rule the results do: in unless another source is named,
        # and never re-matched on q, which it answered itself.
        if cat.registry_wanted(q, f["source"], f["kind"]):
            n += len(cat.search(reg_all, kind=f["kind"], author=f["author"],
                                category=f["category"]))
        return n

    empty, dead = {}, []
    for fid, key, values in (
            ("cat-source", "source", sorted({e.get("source") for e in entries} | {cat.REGISTRY})),
            ("cat-kind", "kind", list(_KIND_SINGULAR)),
            ("cat-author", "author", sorted({e.get("author") for e in entries if e.get("author")})),
            ("cat-category", "category", sorted({e.get("category") for e in entries if e.get("category")}))):
        values = [v for v in values if v]
        chosen = {"source": source, "kind": kind, "author": author, "category": category}[key]
        empty[fid] = [v for v in values if v != chosen and not hits(**{key: v})]
        # ...and the control itself, when nothing it offers would change anything. Derived from
        # the costing rather than from a rule about which source lacks which field: the rule
        # version was right about the registry's missing publisher and category and silently
        # wrong everywhere else. A control you have already set stays live — that is the one you
        # need in order to undo your way back out of a corner.
        # One live option left is not a choice either: if filtering to the Claude plugin
        # marketplace leaves "Plugins" as the only thing Type can select, then Type can only
        # restate what the page already shows.
        if values and not chosen and (len(values) - len(empty[fid])) <= 1:
            dead.append(fid)
    return empty, dead


def _cat_installed(realm_root, entries: list | None = None, only_here: bool = False) -> dict:
    """{catalogue key: [realm names]} across every realm ARMADA knows about.

    Across all realms rather than just this one because the useful hint while browsing is "you
    already use this somewhere" — each realm still has to add it for itself, which is the rule the
    owner chose, but knowing you've vetted it before is worth saying.
    """
    from .. import catalogue as cat
    if only_here:
        roots = [str(realm_root)]
    else:
        # catalogue._known_realms reads the same realms.json that serve._reg_load does, and is the
        # reader the rest of the catalogue already uses. Going through serve made this the one
        # place with a second opinion about which realms exist.
        roots = list(cat._known_realms())
        if str(realm_root) not in roots:
            roots.append(str(realm_root))
    try:
        return cat.installed_keys(roots, entries)
    except Exception:  # noqa — a hint is not worth breaking the page for
        swallowed(log, '_cat_installed: failed; returning a fallback')
        return {}


def _catalogue_pane(realm, realm_root) -> str:
    from .. import catalogue as cat
    idx = cat.load()
    entries = idx.get("entries") or []
    labels = idx.get("source_labels") or {}
    age = cat.age_hours()
    if not entries:
        stale = "Not fetched yet."
    elif age < 0:
        stale = ""
    elif age < 48:
        stale = f"Updated {int(age)}h ago."
    else:
        stale = f"Updated {int(age // 24)} days ago."
    bad = [cat.source_label(s, labels) for s, m in (idx.get("sources") or {}).items()
           if not m.get("ok")]
    if bad:
        stale += " Couldn\u2019t reach: " + ", ".join(sorted(bad)) + "."
    f = cat.facets(entries)

    def sel(sid, label, opts, width=""):
        # Only rendered when the facet has values. The sources disagree about what they carry —
        # the marketplace lists publishers and categories, the MCP registry lists neither — and a
        # dropdown offering values that can never match reads as broken.
        #
        # Same control as the Jobs filters: one filter bar in the app, not two that look alike
        # but aren't. Options are (value, label) — the third slot is the status swatch, which
        # nothing here has.
        if not opts:
            return ""
        rows = [("", label)] + list(opts)
        return _filter_dropdown(sid, label, [(v, l, "") for v, l in rows],
                                width=width, onpick="mcCatFilter")

    # The MCP registry is a source you can filter by even though it contributes nothing to the
    # mirrored index — it is searched live. Deriving this list from the index alone left the one
    # source whose results are plainly on screen missing from the menu that filters them.
    # Sources keep their counts: each is a mirrored list we hold in full, so the number is the
    # whole answer. (Types don't — see below.)
    src_opts = [(s, cat.source_label(s, labels) + (f" ({n})" if n else "")) for s, n in f["source"]]
    # The registry's size comes from the daily count, not from the entries in hand (it mirrors
    # nothing here). Before the first count there is no number, because a guess is not a count.
    rn = cat.registry_count_label(idx)
    src_opts.append((cat.REGISTRY,
                     cat.SOURCE_LABEL[cat.REGISTRY] + (f" ({rn})" if rn else "")))
    src_opts.sort(key=lambda o: o[1].lower())
    # Every type ARMADA has, not only the ones the mirrored index happens to contain. Connectors
    # and Extensions come from the MCP registry, which is searched rather than mirrored — so
    # deriving this list from the index alone silently dropped two of the four, and the filter
    # couldn't reach results that were plainly on screen.
    #
    # And no counts on them, for the same reason: two of the four can only be counted by asking
    # the registry, so a number here would have been the mirrored half of the answer wearing the
    # whole answer's clothes. Better no number than a number that means something else.
    kind_opts = [(k, _KIND_SINGULAR[k] + "s") for k in ("connectors", "extensions", "skills", "plugins")]
    faint = "var(--text-faint)"
    bar = (f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 12px">'
           f'<div style="position:relative;flex:0 0 200px">'
           f'<span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);display:flex;'
           f'color:{faint}">{_icon("search",14)}</span>'
           f'<input id="cat-q" oninput="mcCatFilterSoon()" placeholder="Search the catalogue\u2026" '
           f'class="mc-field" style="padding-left:30px;padding-right:26px">'
           f'<span id="cat-q-x" onclick="mcCatClearSearch()" title="Clear" style="display:none;position:absolute;'
           f'right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:{faint}">{_icon("x",14)}</span></div>'
           f'<span style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;'
           f'color:{faint}">Filter</span>'
           f'{sel("cat-source", "All sources", src_opts, width="170px")}'
           f'{sel("cat-kind", "All types", kind_opts, width="140px")}'
           f'{sel("cat-author", "Any publisher", [(v, v) for v, n in f["author"][:40]], width="180px")}'
           f'{sel("cat-category", "Any category", [(v, v) for v, n in f["category"]], width="150px")}'
           f'<button id="cat-clear" onclick="mcCatClear()" style="display:none;align-items:center;gap:4px;'
           f'border:0;background:transparent;cursor:pointer;font-size:12px;color:var(--color-accent);'
           f'padding:6px 4px">{_icon("x",12)}Clear</button>'
           # Refreshing the catalogue belongs with the controls that search it, at the right end of
           # their row — there is room, and it was costing a line of its own above the info box.
           # margin-left:auto rather than a spacer, so on a narrow pane it wraps with the filters
           # instead of holding the row open.
           f'<div style="margin-left:auto;display:flex;align-items:center;gap:10px;flex:none">'
           + (f'<span style="font-size:11px;color:var(--text-muted)">{E(stale)}</span>'
              if stale else "")
           + f'<button class="btn btn-secondary btn-sm" style="'
           f'white-space:nowrap" '
           f'onclick="mcCatRefresh(this)">{_icon("refresh-cw",13)}Refresh catalogue</button>'
           f'</div>'
           f'</div>')
    # One line per source, because "from several places" is not something anyone can act on — and
    # whether a thing was vetted by anybody is the single most useful fact about it here.
    # Just the info box: it runs the full width of the pane, and the refresh pair that used to sit
    # on a line above it now rides at the right end of the filter row instead.
    head = _cat_infobox(realm, idx)
    # The results are NOT rendered here. Building them queries the MCP registry, and a network
    # call on the render path meant clicking Capabilities waited on it — about 700ms on a good
    # day and up to the 20-second timeout on a bad one, for a pane that starts hidden behind the
    # User tab. The page now arrives with everything it can know locally, and the results load
    # when the Catalogue tab is first opened.
    #
    # Bring a link sits above the search bar, not below the results: ADR-004 calls it the headline
    # path, the one that reaches everything the two mirrored sources don't. It needs no network call
    # on render either — nothing happens until Review is clicked.
    return (f'<div id="cap-pane-catalogue" style="display:none">{head}{_cat_bring_link()}{bar}'
            f'{_cat_placeholder()}</div>')


_RISK_META = {"high": ("var(--status-bad)", "High risk"),
              "medium": ("var(--status-warn)", "Medium risk"),
              "low": ("var(--status-ok)", "Low risk")}
# Fallback when the agent left `risk` blank (or an older review predates the field): the same
# red/amber/green a capability with no set tier gets everywhere else in the app (_cap_tier_why,
# from runs/touch alone), translated to the word this card uses.
_TIER_TO_RISK = {"red": "high", "amber": "medium", "green": "low"}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _cat_final_risk(review: dict) -> str:
    """The one risk word the card commits to.

    The agent's own bucket, floored to at least the mechanical worst-case every OTHER capability
    in the app is held to (_cap_tier_why, from runs/touch alone — the same read the User tab's
    stripe uses). A capability that can run shell commands is red there regardless of what its
    review otherwise concluded; this card can't soften that just because the agent's own summary
    called it "medium" — the ability is the fact, the agent's word is a judgement on top of it,
    and the worse of the two wins. With no agent verdict at all, this is exactly the mechanical
    read (same as _cap_tier_why's own fallback).
    """
    mechanical = _TIER_TO_RISK.get(_cap_tier_why(review)[0], "medium")
    agent = (review.get("risk") or "").lower()
    if agent not in _RISK_META:
        return mechanical
    return agent if _RISK_ORDER[agent] >= _RISK_ORDER[mechanical] else mechanical

# The Step 5 report (system_skills/capability-review/SKILL.md) is written as prose with inline
# section labels the agent chooses its own wording for — "BUCKET — Connector...", "RUNS —
# service.", "EVIDENCE — ..." — a pattern the skill invites (Step 5 lists Bucket / Runs / Can
# touch / Evidence / Confidence / What was not checked) without asking for a paragraph break
# around each one. Matched generically — an ALL-CAPS run immediately before an em or en dash —
# rather than a fixed label list, since the exact wording is the agent's own choice each time.
_REVIEW_LABEL_RE = re.compile(r'\b([A-Z]{2}[A-Z /]{0,38}[A-Z])\s?[—–]\s')


def _paragraph_break_before_labels(text: str) -> str:
    """Insert a blank line before each "LABEL — " run, so _md() renders what was one dense block
    as separate paragraphs — one per section of the report.

    Skips a match whose label is really the tail of a compound one the agent wrote as its own
    phrase — "DECLARED vs OBSERVED — ..." — where the all-caps regex, scanning independently,
    finds "OBSERVED —" as if it opened a section on its own and splits the phrase in half. The
    tell is the character right before the match (past any spaces): a real section label is
    preceded by a sentence end or nothing, never a lowercase word like "vs".
    """
    out = []
    last_end = 0
    for m in _REVIEW_LABEL_RE.finditer(text):
        start = m.start()
        j = start
        while j > 0 and text[j - 1] in " \t":
            j -= 1
        prev_char = text[j - 1] if j > 0 else ""
        if prev_char.islower():
            continue
        out.append(text[last_end:start])
        out.append("\n\n")
        last_end = start
    out.append(text[last_end:])
    result = "".join(out)
    return re.sub(r"\n{3,}", "\n\n", result).lstrip("\n")


def _cat_review_card(review: dict) -> str:
    """The report a bring-a-link review renders as — server-side, so it can reuse the exact
    Runs/Can-touch iconography (_cap_iconcluster) and per-ability colours the User tab's
    declared-vs-observed panel uses. One visual language for "what can this touch", not a second
    one invented in JS for this one screen.

    Leads with Armada's own recommendation (the review's `recommendation` field, a few plain
    sentences) rather than the full Step 5 evidence report: the evidence is long and dense by
    design — quoted file snippets, exact locations — and burying the one-paragraph verdict inside
    it is what made the old rendering unreadable. The full report is still here, one click away,
    for whoever wants to check the evidence behind the verdict rather than take it on faith.
    """
    kind = review.get("kind") or ""
    ic = {"connectors": "cap-connector", "extensions": "puzzle",
          "skills": "cap-skill", "plugins": "cap-plugin"}.get(kind, "plug")
    name = E(review.get("name") or "This capability")
    publisher = review.get("publisher") or ""
    # Runs/Can-touch, inline on the title row rather than a separate band below — the same
    # component the User tab's cards use, so "what can this touch" reads identically everywhere.
    # A left margin on top of the row's own flex gap, so it doesn't crowd "by X".
    cluster = _cap_iconcluster(review)
    cluster_html = f'<span style="margin-left:6px">{cluster}</span>' if cluster else ""
    summary = str(review.get("summary") or "").strip()
    # Fall back to the long report only for a review run before this field existed (or one where
    # the agent skipped it) — the card should never show nothing where the verdict belongs.
    rec = str(review.get("recommendation") or "").strip() or summary or "No summary returned."
    warn = str(review.get("warn") or "").strip()
    warn_html = ""
    if warn:
        warn_html = (f'<div style="display:flex;align-items:flex-start;gap:6px;margin-top:8px;'
                     f'color:var(--status-bad);font-size:12.5px">'
                     f'<span style="display:flex;flex:none;margin-top:1px">{_icon("warning-filled",18)}</span>'
                     f'<span><b>Flagged</b> — {_md_inline(E(warn))}</span></div>')
    # One label, not two: the agent's own bucket, floored to at least the mechanical worst-case
    # every other capability in the app is held to (_cat_final_risk) — never a softer word than
    # what Runs/Can-touch alone would earn elsewhere.
    risk = _cat_final_risk(review)
    rc, rlabel = _RISK_META[risk]
    risk_pill = _pill(E(rlabel.upper()), _tone(rc), style="font-weight:700;letter-spacing:.02em")
    # Already-added, checked across every realm ARMADA knows about (routes/catalogue.py's
    # _catalogue_review — see catalogue.realms_with_capability). In THIS realm, Add would only
    # create the duplicate add_link_to_realm's own dedupe already refuses — so the button is
    # disabled rather than left to fail on click. In some OTHER realm, it's worth knowing but not
    # worth blocking: this realm hasn't vetted it yet, and the rule has always been that every
    # realm adds for itself.
    already_here = bool(review.get("already_here"))
    elsewhere = [str(r) for r in (review.get("already_elsewhere") or []) if str(r).strip()]
    status_html = ""
    if already_here:
        status_html = (f'<div style="display:flex;align-items:center;gap:5px;margin-top:9px;'
                       f'font-size:11.5px;color:var(--status-ok)">'
                       f'{_icon("circle-check",12)}Already added to this realm</div>')
    elif elsewhere:
        status_html = (f'<div style="display:flex;align-items:center;gap:5px;margin-top:9px;'
                       f'font-size:11.5px;color:var(--status-ok)">'
                       f'{_icon("circle-check",12)}Added to {E(", ".join(elsewhere[:3]))}</div>')
    add_btn_html = (
        f'<button class="btn btn-secondary" disabled title="Already in this realm" '
        f'style="font-size:11.5px;padding:4px 10px;opacity:.5">Added</button>'
        if already_here else
        f'<button class="btn btn-secondary btn-sm" '
        f'onclick="mcCatAddLink(this)">Add to realm</button>')
    details_html = ""
    if summary and summary.strip() != rec.strip():
        details_html = (
            f'<details class="mc-cat-full" style="margin-top:12px" ontoggle="mcRevealSection && mcRevealSection(this)">'
            f'<summary style="cursor:pointer;display:inline-flex;align-items:center;gap:5px;'
            f'font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);'
            f'font-weight:700;list-style:none">'
            f'<span class="mc-cap-caret" style="display:flex">{_icon("chevron-right",11)}</span>Full review</summary>'
            f'<div class="mc-md" style="margin-top:9px;font-size:13px">'
            f'{_md(_paragraph_break_before_labels(summary))}</div></details>')
    return (
        f'<div class="mc-frame" style="border-radius:var(--r);padding:14px 16px">'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
        f'<span style="display:flex;flex:none;color:var(--text-muted)" '
        f'title="{E(_KIND_SINGULAR.get(kind, kind))}">{_icon(ic,16)}</span>'
        f'<span style="font-family:var(--font-heading);font-weight:600;font-size:15px">{name}</span>'
        + (f'<span style="font-size:11.5px;color:var(--text-muted)">by {E(publisher)}</span>' if publisher else "")
        + cluster_html +
        f'</div>'
        f'<div style="display:flex;align-items:flex-start;gap:8px;margin-top:11px;padding:10px 12px;'
        f'border-radius:var(--r);background:color-mix(in srgb,{rc} 7%,transparent)">'
        f'<span style="display:flex;flex:none;color:{rc};margin-top:2px">{_icon("risk-analysis",18)}</span>'
        f'<div style="font-size:13px;line-height:1.55">'
        f'<div style="margin-bottom:5px">{risk_pill}</div>'
        f'<b>Armada’s assessment:</b> {_md_inline(E(rec))}{warn_html}</div></div>'
        f'{status_html}'
        f'{details_html}'
        f'<div style="margin-top:12px">{add_btn_html}</div>'
        f'</div>')


def _cat_bring_link() -> str:
    """Paste a link, an agent reviews it, the report is what decides whether to add it.

    The second of ADR-004's two paths, and the one that scales to sources this catalogue doesn't
    mirror. Deliberately its own block rather than a third search result: nothing here is a match
    against an index, it is a live turn (system_skills/capability-review, run with tools, over the
    Claude engine) that reads the actual thing and can take real time — the copy says so rather than
    pretending this is as fast as a filter.
    """
    faint = "var(--text-faint)"
    return (
        f'<div class="mc-frame" style="border-radius:var(--r);padding:13px 15px;margin:0 0 16px">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
        f'<span style="display:flex;flex:none;color:var(--color-accent-2)">{_icon("link",15)}</span>'
        f'<span style="font-family:var(--font-heading);font-weight:600;font-size:14px">Bring a link</span>'
        f'<span style="font-size:11px;color:{faint}">A repository, a package, an MCP server — anything the two sources above don’t carry</span>'
        f'</div>'
        f'<div style="font-size:12px;color:var(--text-muted);margin:2px 0 10px">'
        f'An agent reads it — not just the README — and reports what it actually found before Add is turned on. '
        f'A real read takes real time; expect a minute or two, not a filter’s instant.</div>'
        f'<div style="display:flex;gap:8px;align-items:center">'
        f'<input id="cat-link" placeholder="https://github.com/owner/repo" '
        f'class="mc-field" style="flex:1;max-width:440px" onkeydown="if(event.key===\'Enter\')mcCatReview(this)">'
        f'<button class="btn btn-secondary" style="white-space:nowrap" '
        f'onclick="mcCatReview(this)">Review</button></div>'
        f'<div id="cat-review-out" style="margin-top:10px"></div>'
        f'</div>')


def _cat_placeholder() -> str:
    """What sits where the results will go, until they arrive.

    Card-shaped rather than a spinner: the pane keeps its height and the filter bar doesn't jump
    down the screen when the answer lands.
    """
    row = ('<div class="mc-cat-skel mc-frame" style="border-radius:var(--r);padding:11px 13px;'
           'margin-bottom:8px;height:58px"></div>')
    return (f'<div id="cat-results" data-pending="1">'
            f'<div style="font-size:11.5px;color:var(--text-muted);margin:0 0 10px">'
            f'Loading the catalogue\u2026</div>{row * 4}</div>')


def _cat_source_notes(idx: dict) -> list:
    """(label, what it is) for each source, so "where did this come from" has a real answer.

    The marketplace line stays generated rather than written out, because a machine can have more
    than one: the Claude CLI clones whichever the owner has configured, and Anthropic's is only
    the one that ships by default. Naming Anthropic in a fixed sentence would be right today and
    quietly wrong for anyone who adds a second directory.
    """
    from .. import catalogue as cat
    labels = idx.get("source_labels") or {}
    seen = {e.get("source") for e in (idx.get("entries") or [])}
    out = []
    for s in sorted(x for x in seen if cat.is_marketplace(x)):
        who = "Anthropic" if s.endswith(":claude-plugins-official") else "its owner"
        out.append((cat.source_label(s, labels),
                    f"plugins listed in a directory curated by {who}; each bundles skills, "
                    "commands, agents or an MCP server"))
    if cat.SKILLS in seen:
        out.append((cat.SOURCE_LABEL[cat.SKILLS],
                    "Anthropic\u2019s public skills repository \u2014 instructions an agent can use for "
                    "a particular kind of task"))
    if cat.MINE in seen:
        out.append((cat.SOURCE_LABEL[cat.MINE],
                    "skills written here \u2014 by you, or by an agent you asked \u2014 in any of your "
                    "realms, listed so you can use them in this one too"))
    if cat.INSTALLED in seen:
        out.append((cat.SOURCE_LABEL[cat.INSTALLED],
                    "skills an agent fetched from somewhere else (a repository link, a package) "
                    "or that came over from Claude Desktop. Each card says where. Nobody reviewed "
                    "these on the way in, so they are worth a look before you switch one on"))
    out.append((cat.SOURCE_LABEL[cat.REGISTRY],
                "the open MCP index \u2014 queried live rather than mirrored, so what you see is a "
                "sample until you search. Anyone can publish to it, so a listing there does not "
                "mean anyone has reviewed it"))
    return out


_CAT_TYPE_NOTES = (
    ("cap-connector", "Connector",
     "a <b>remote</b> link to an outside service (a broker, Google Drive, Telegram, a data feed). "
     "A hosted integration an agent uses to read or send real data."),
    ("puzzle", "Extension",
     "a <b>local</b> tool running on this machine (local files, a private script, a developer "
     "tool). Like a connector, but it stays on your computer rather than calling out to the cloud."),
    ("cap-skill", "Skill",
     "a packaged instruction set that teaches an agent a repeatable way of doing something "
     "(a house writing style, a review checklist, a workflow)."),
    ("cap-plugin", "Plugin",
     "a bundle that brings several skills and connectors together, added as one unit."),
)


def _cat_infobox(realm, idx: dict) -> str:
    """The Catalogue's explainer: one line closed, the whole picture open.

    It was four paragraphs and a bullet list sitting permanently above the results, which is a lot
    of reading to scroll past every time you come here to find one thing. The same words are worth
    having; they are worth having on request.
    """
    types = "".join(
        f'<div style="display:flex;gap:10px">'
        f'<span style="display:flex;flex:none;color:var(--color-accent);margin-top:2px">{_icon(ic, 16)}</span>'
        f'<div><b>{name}</b> \u2014 {body}</div></div>'
        for ic, name, body in _CAT_TYPE_NOTES)
    srcs = "".join(f'<li style="margin:3px 0"><b>{E(lab)}</b> \u2014 {E(desc)}</li>'
                   for lab, desc in _cat_source_notes(idx))
    hd = ("font-size:11px;letter-spacing:.05em;text-transform:uppercase;"
          "color:var(--text-faint);margin:16px 0 7px")
    # Full width, like the filter row under it, and headed the way an Overview widget is headed —
    # same class, so the two cannot drift apart if that header is ever restyled.
    return (
        f'<details class="mc-catinfo mc-frame" style="border-radius:var(--r);margin:0 0 14px">'
        # .mc-wid-h carries only the background; a widget header's padding and rule are inline in
        # _wid_header, so they are repeated here with the same values rather than inherited.
        f'<summary class="mc-wid-h" style="display:flex;align-items:center;gap:8px;'
        f'padding:8px 12px;border-bottom:1px solid transparent;'
        f'cursor:pointer;list-style:none">'
        f'<span style="display:flex;flex:none;color:var(--color-accent-2)">{_icon("info",15)}</span>'
        f'<span style="font-family:var(--font-heading);font-weight:600;font-size:15px">'
        f'Search known sources, or bring a link for anything else.</span>'
        # The widget header's meta slot, in its colour and size but not its uppercase: that slot
        # normally holds two or three words, and a sentence shouted is a sentence nobody reads.
        f'<span style="font-size:11px;color:var(--text-soft)">'
        f'Expand to learn about capability types, sources and how a link gets reviewed.</span>'
        f'<span class="mc-catinfo-ch" style="margin-left:auto;display:flex;flex:none;'
        f'color:var(--text-muted)">{_icon("chevron-right",14)}</span></summary>'
        f'<div style="padding:2px 13px 14px;font-size:12.5px;line-height:1.6;color:var(--text-muted)">'
        f'<div style="{hd}">Capability types</div>'
        f'<div style="display:flex;flex-direction:column;gap:9px">{types}</div>'
        f'<div style="{hd}">Sources for this catalogue</div>'
        f'<ul style="margin:0;padding-left:18px">{srcs}</ul>'
        f'<div style="{hd}">Adding one</div>'
        f'<div>Adding a capability puts it in <b>{E(realm.name)}</b> and ARMADA evaluates it '
        f'automatically, so you can decide whether to turn it on knowing what it can reach. '
        f'No new capability can be used by an agent until you have turned it on '
        f'<i>and</i> given that agent access to it.</div>'
        f'<div style="margin-top:9px">Results are sorted alphabetically \u2014 no source here '
        f'publishes a popularity signal, so nothing here claims one. A card still says when '
        f'you already use it, and where.</div>'
        f'</div></details>')


