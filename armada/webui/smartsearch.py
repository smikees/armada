"""Add a capability: smart search (Alexander), Bring a link, add by address, and where to browse.

The tab used to be a browser over a mirrored catalogue with five filters. It is now three ways in:
ask Alexander (armada/smart_search.py), bring a link, or browse a directory yourself and come back.
Every result card is built from a record a source returned; Alexander only picks and explains.
"""
from __future__ import annotations

from ..icons import _icon
from ._base import E, _J, _pill, _tone
from .capabilities import _KIND_SINGULAR

_KIND_ICON = {"connectors": "cap-connector", "extensions": "puzzle", "skills": "cap-skill", "plugins": "cap-plugin"}
_EXAMPLES = ("a PDF viewer for Codex", "connectors already set up in Claude Code",
             "skills I made in other realms", "something to read and send Gmail")
_REACH = {"any": ("engines-any", "Any engine"), "claude": ("claude", "Claude only"),
          "codex": ("codex", "Codex only"), "gemini": ("gemini", "Gemini only"),
          "per-engine": ("swap", "Added per engine")}
_HAVE = {"realm": "In this realm", "claude": "Set up in Claude Code", "chatgpt": "Installed in ChatGPT"}


def _sources_panel() -> str:
    from .. import smart_search as ss
    groups = (("yours", "What you have"), ("find", "Where to find more"))
    body = ""
    for gid, title in groups:
        chips = "".join(
            f'<label class="mc-ss-src" title="{E(desc)}"><input type="checkbox" value="{E(sid)}"'
            f'{" checked" if on else ""} onchange="mcSsSources()"><span>{E(label)}</span></label>'
            for sid, label, g, desc, on in ss.SOURCES if g == gid)
        body += f'<div class="mc-ss-srcgroup"><div class="mc-ss-srch">{E(title)}</div><div class="mc-ss-srcs">{chips}</div></div>'
    return (f'<details class="mc-ss-sources"><summary>{_icon("sort", 13)}<span>Sources</span>'
            f'<span id="ss-src-count" class="mc-ss-srccount"></span>{_icon("chevron-right", 12)}</summary>'
            f'<div class="mc-ss-srcbody">{body}'
            f'<div class="mc-ss-srcfoot"><span>Alexander searches only the sources switched on here. '
            f'Lists from directories refresh daily.</span>'
            f'<button type="button" class="btn btn-secondary btn-sm" onclick="mcSsRefresh(this)">'
            f'{_icon("refresh-cw", 12)}Refresh lists</button></div></div></details>')


def _directories() -> str:
    from .. import smart_search as ss
    rows = "".join(
        f'<a class="mc-ss-dir" href="{E(url)}" target="_blank" rel="noopener">'
        f'<span class="mc-ss-dirico">{_icon(icon, 15)}</span>'
        f'<span><strong>{E(name)} ↗</strong><small>{E(desc)}</small></span></a>'
        for name, url, icon, desc in ss.DIRECTORIES)
    return (f'<section class="mc-addways" aria-labelledby="ss-dirs-h">'
            f'<h3 id="ss-dirs-h" class="mc-addways-title">Browse for yourself</h3>'
            f'<p class="mc-addway-p" style="margin-top:-2px">Found something there? Bring its link back here '
            f'for a review before anything is added. Engine connectors and plugins install in the engine; '
            f'smart search then finds them under what you have.</p>'
            f'<div class="mc-ss-dirs">{rows}</div></section>')


def smart_search_pane(realm, realm_root) -> str:
    from .catalogue import _cat_other_ways_minimal
    examples = "".join(f'<button type="button" class="mc-ss-ex" onclick="mcSsExample(this)">{E(x)}</button>'
                       for x in _EXAMPLES)
    box = (f'<section class="mc-ss" aria-labelledby="ss-h">'
           f'<h3 id="ss-h" class="mc-ss-title"><img src="/static/alexander.png" alt="" class="mc-ss-av">'
           f'Ask Alexander to find it</h3>'
           f'<form class="mc-ss-box" onsubmit="mcSmartSearch(event)">'
           f'<span class="mc-ss-boxico">{_icon("search", 16)}</span>'
           f'<input id="ss-q" class="mc-field" maxlength="500" autocomplete="off" '
           f'placeholder="Describe what you need, or ask what you already have" aria-label="What do you need?">'
           f'<button id="ss-go" type="submit" class="btn btn-primary">Search</button></form>'
           f'<div class="mc-ss-row"><div class="mc-ss-exs"><span>Try</span>{examples}</div>{_sources_panel()}</div>'
           f'<div id="ss-out" class="mc-ss-out" aria-live="polite"></div></section>')
    from ..assets import js
    return (f'<div id="cap-pane-catalogue" style="display:none">{box}'
            f'{_cat_other_ways_minimal()}{_directories()}</div>' + js("smartsearch"))


# --------------------------------------------------------------------------- results

def _actions(r: dict) -> str:
    a = r.get("action") or {}
    t = a.get("type")
    if r.get("have") == "realm" or t == "in-realm":
        return (f'<button class="btn btn-secondary btn-sm" title="Already in this realm: show it on the User tab" '
                f'onclick="mcSsShow({_J(r["name"])})">{_icon("check", 12)}In this realm</button>')
    if t == "review":
        return (f'<button class="btn btn-secondary btn-sm" '
                f'onclick="mcSsReview(this,{_J(a.get("url", ""))},{_J(a.get("key", ""))})">Review &amp; add</button>')
    if t == "add":
        return (f'<button class="btn btn-secondary btn-sm" onclick="mcCatAdd(this,{_J(a.get("key", ""))})">'
                f'Add to realm</button>')
    if t == "engine":
        from .. import connector_registry
        svc = next((s for s in connector_registry.SERVICES if s["id"] == a.get("service")), None)
        added = set(a.get("added") or [])
        if svc and svc.get("endpoint"):
            return (f'<button class="btn btn-secondary btn-sm" onclick="mcCatAddService(this,{_J(svc["id"])},\'\')">'
                    f'Add to realm</button>')
        out = ""
        for eng, label in (("claude", "Claude"), ("codex", "Codex")):
            if eng in added:
                out += f'<span class="mc-cat-eng is-added">{_icon(eng, 13)}{_icon("check", 11)}Added for {label}</span>'
            elif not (r["source"] in ("chatgpt-plugins", "chatgpt-installed") and eng == "claude"):
                out += (f'<button class="btn btn-secondary btn-sm mc-cat-eng-add" '
                        f'onclick="mcCatAddService(this,{_J(a.get("service", ""))},{_J(eng)})">'
                        f'{_icon(eng, 13)}Add for {label}</button>')
        return out
    if t == "codex-plugin":
        open_link = (f'<a class="btn btn-secondary btn-sm" href="{E(r.get("url") or "https://chatgpt.com/plugins")}" '
                     f'target="_blank" rel="noopener">Open in ChatGPT ↗</a>')
        return (f'<button class="btn btn-secondary btn-sm" onclick="mcSsAddPlugin(this,{_J(a.get("plugin", ""))})">'
                f'{_icon("codex", 13)}Add for Codex</button>' + open_link)
    if t == "bring-in":
        return (f'<button class="btn btn-secondary btn-sm" onclick="mcSsBringIn(this)">'
                f'{_icon("claude", 13)}Bring in from Claude</button>')
    if r.get("url"):
        return (f'<a class="btn btn-secondary btn-sm" href="{E(r["url"])}" target="_blank" rel="noopener">'
                f'Open ↗</a>')
    return ""


def _card(r: dict) -> str:
    from .. import smart_search as ss
    icon, reach = _REACH.get(r.get("reach") or "any", _REACH["any"])
    kind = r.get("kind") or ""
    name = E(r.get("name") or "")
    if r.get("url"):
        name = f'<a href="{E(r["url"])}" target="_blank" rel="noopener">{name}</a>'
    have = _HAVE.get(r.get("have") or "")
    # The action button already says "In this realm", and the source pill already says where a
    # "set up in Claude Code" result came from: the chip appears only when it adds something.
    if r.get("have") == "realm" or have == ss.LABEL.get(r.get("source")) or r.get("source") == "claude-code":
        have = ""
    meta = []
    if r.get("publisher"):
        meta.append("by " + E(r["publisher"]))
    if kind:
        meta.append(E(_KIND_SINGULAR.get(kind, kind)))
    risky = r.get("source") == "mcp-registry"
    return (f'<article class="mc-ss-card mc-frame" data-source="{E(r.get("source", ""))}">'
            f'<span class="mc-ss-cardico" title="{E(_KIND_SINGULAR.get(kind, "Capability"))}">'
            f'{_icon(_KIND_ICON.get(kind, "plug"), 16)}</span>'
            f'<div class="mc-ss-cardmain">'
            f'<div class="mc-ss-cardhead"><span class="mc-ss-name">{name}</span>'
            f'<span class="mc-cat-reach" data-reach="{E(r.get("reach") or "any")}">{_icon(icon, 11)}{E(reach)}</span>'
            + _pill(E(ss.LABEL.get(r.get("source"), r.get("source") or "")),
                    _tone("var(--status-warn)" if risky else "var(--text-muted)"))
            + (f'<span class="mc-ss-have">{_icon("circle-check", 12)}{E(have)}</span>' if have else "")
            + '</div>'
            + (f'<p class="mc-ss-why">{E(r["why"])}</p>' if r.get("why") else "")
            + (f'<p class="mc-ss-desc">{E(r.get("description") or "")}</p>' if r.get("description") else "")
            + (f'<p class="mc-ss-meta">{" · ".join(meta)}</p>' if meta else "")
            + f'<div class="mc-ss-review"></div></div>'
            f'<div class="mc-ss-actions">{_actions(r)}</div></article>')


def render_results(realm_root, res: dict) -> str:
    from .. import smart_search as ss
    if not res.get("ok"):
        return (f'<div class="mc-ss-error">{_icon("warning-tri", 14)}<span>{E(res.get("error") or "The search failed.")}</span></div>')
    cards = "".join(_card(r) for r in res.get("results") or [])
    searched = ", ".join(ss.LABEL.get(s, s) for s in res.get("searched") or [])
    skipped = [ss.LABEL.get(s, s) for s in ss.SOURCE_IDS if s not in (res.get("enabled") or ss.SOURCE_IDS)]
    return (f'<div class="mc-ss-summary"><img src="/static/alexander.png" alt="Alexander" class="mc-ss-av">'
            f'<p>{E(res.get("summary") or "")}</p></div>'
            + (f'<div class="mc-ss-cards">{cards}</div>' if cards else "")
            + (f'<p class="mc-ss-searched">Searched: {E(searched)}'
               + (f' \u00b7 Switched off: {E(", ".join(skipped))}' if skipped else "") + '</p>' if searched else ""))
