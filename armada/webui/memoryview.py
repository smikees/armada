"""Memory rendering (realm + agent memory pages) (Layer 2, Phase 3).

Imports lower layers (never _core); _core re-imports these names.
"""
from __future__ import annotations
import html, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import goals as goalsmod
from ..icons import ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR, _ICON_REFRESH
from ._base import (E, _J, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _mini_pill, _poss)
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _ordinal, _next_hint, _fmt_ts)
from ..assets import (MEM_ADD_JS as _MEM_ADD_JS, MEM_EXPAND_JS as _MEM_EXPAND_JS,
    MEMFOCUS_JS as _MEMFOCUS_JS, COVENANT_JS as _COVENANT_JS)  # Phase 2, 2.1
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)


def _agent_memory(realm_root: Path, agent_id: str) -> list[tuple[str, str]]:
    return memory._memories(Path(realm_root) / "agents" / agent_id / "memory")


def _tab_memory(realm, realm_root, a, focus: str = "") -> str:
    cards = _mem_cards(_list_mem(Path(realm_root) / "agents" / a.id / "memory"), "agent", a.id,
                       realm=realm, agent_display=a.display)
    focus_js = (_MEMFOCUS_JS + f'<script>mcMemFocusHighlight("mem-{E(focus)}")</script>') if focus else ""
    header = (f'<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px">'
              f'<h2 style="font-family:var(--font-heading);font-size:26px;margin:0">'
              f'{E(_poss(a.display))} memory'
              f'<span style="font-family:var(--font-body);font-weight:400;font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
              f'color:var(--text-soft);margin-left:6px">· per agent · loads only in {E(_poss(a.display))} threads</span></h2>'
              f'{_mem_add_button()}</div>')
    info = (f'<div style="display:flex;gap:8px;align-items:center;background:color-mix(in srgb,var(--color-accent-2) 8%,transparent);'
            f'border:1px solid color-mix(in srgb,var(--color-accent-2) 22%,transparent);border-radius:var(--r);'
            f'padding:8px 12px;margin-bottom:14px;font-size:12.5px;line-height:1.4">'
            f'<span style="display:flex;flex:none;color:var(--color-accent-2-700)">{_icon("info", 15)}</span>'
            f'<div>{E(a.display)} also loads the <b>System</b> and <b>Realm</b> memories in every thread. '
            f'These can be managed on the <a href="/memory" style="color:var(--color-accent)">realm Memory page</a>.</div></div>')
    return (f'<div style="padding:18px 24px 24px;max-width:820px">{header}{info}'
            f'{_mem_search()}{cards}{_mem_modals("agent", a.id, a.display)}{focus_js}</div>')


def _list_mem(mem_dir: Path) -> list[tuple[str, str, str, str, str, str]]:
    """(stem, title, body, modified, kind, by) per memory file. `kind` marks the managed system
    memory; `by` is who last updated it (owner | system | an agent id), `modified` the update date
    (from frontmatter `updated`, else file mtime), both used for the 'updated by … on …' line."""
    out = []
    if mem_dir.is_dir():
        for f in sorted(mem_dir.glob("*.md")):
            meta, body = memory._frontmatter(f.read_text(encoding="utf-8-sig"))
            body = body.strip()
            if not body:
                continue
            upd = (meta.get("updated") or "").strip()
            try:
                modified = datetime.date.fromisoformat(upd[:10]).strftime("%d-%m-%y") if upd else \
                    datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d-%m-%y")
            except ValueError:
                modified = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d-%m-%y")
            out.append((f.stem, meta.get("title", f.stem), body, modified,
                        (meta.get("kind") or "").strip().lower(), (meta.get("updated_by") or "").strip()))
    out.sort(key=lambda t: (t[4] not in ("core", "system"), t[0]))   # system/core first, then by stem
    return out


def _updater_label(by: str, realm=None, agent_display: str = "") -> str:
    """Human label for who last updated a memory: 'owner', 'system', or an agent's display name."""
    b = (by or "").strip()
    if not b:
        return ""
    low = b.lower()
    if low in ("owner", "user", "you"):
        return "owner"
    if low in ("system", "daily-job"):
        return "system"
    if realm is not None:
        m = next((x for x in getattr(realm, "agents", []) if x.id == b or x.display == b), None)
        if m:
            return m.display
    return agent_display or b


def _mem_cards(items, scope: str, agent_id: str = "", realm=None, agent_display: str = "") -> str:
    if not items:
        return ('<div style="font-size:12.5px;color:var(--text-muted)">No memories yet.</div>')
    # icon that marks the memory's scope: the realm's own icon for realm memories, the ai-agent icon
    # for an agent's own memories (dynamic — the realm icon follows whatever the realm has set). Each
    # carries a tooltip explaining what "loads where".
    if scope == "realm":
        scope_icon = _realm_icon(realm, 16) if realm is not None else _icon("landmark", 16)
        scope_tip = "Realm memory — loaded for every agent"
    elif scope == "agent":
        scope_icon = _icon("ai-agent", 15)
        scope_tip = "Agent memory — loads only in this agent's threads"
    else:
        scope_icon, scope_tip = "", ""
    icon_span = (f'<span title="{E(scope_tip)}" style="display:flex;flex:none;color:var(--text-muted)">{scope_icon}</span>') if scope_icon else ""
    out = ""
    for stem, title, body, modified, kind, by in items:
        core = kind in ("core", "system")
        # Card layout: the scope icon sits in a left column; the type-tag line, the title (below it),
        # and the content stack in a right column — so the icon is to the left of the content and the
        # title/content are indented past it. System memory reads as managed realm memory.
        _tag_style = ("font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--color-sand-700)")
        if core:
            tagline = f'<div style="{_tag_style}">Realm memory · system managed</div>'
            # Give the managed memory a real title too, so it reads and behaves like every other
            # card rather than being a nameless block of text.
            titleline = ('<div style="font-size:13px;font-weight:600;color:var(--color-text);'
                         'margin-top:2px">Environment, realm and owner context</div>')
        else:
            t = E(title) if title and title != stem else ""
            scope_lbl = ("Realm memory" if scope == "realm"
                         else ("Agent memory" if scope == "agent" else "Memory"))
            tagline = f'<div style="{_tag_style}">{scope_lbl}</div>'
            titleline = (f'<div style="font-size:13px;font-weight:600;color:var(--color-text);margin-top:2px">{t}</div>'
                         if t else "")
        # "updated by <role> on dd-mm-yy" (role: owner | agent name | system)
        who = _updater_label("system" if core and not by else by, realm, agent_display)
        upd = (f'<span title="Last update" style="font-size:10px;color:var(--text-42);white-space:nowrap">'
               f'updated{(" by " + E(who)) if who else ""} on {E(modified)}</span>') if modified else ""
        if core:
            actions = (f'<button onclick="mcRefreshSystem(this)" title="Regenerate from the realm now" '
                       f'style="border:0;background:transparent;cursor:pointer;padding:4px 6px;border-radius:var(--r);'
                       f'display:inline-flex;align-items:center;line-height:1;'
                       f'color:var(--text-muted)">{_ICON_REFRESH}</button>')
        else:
            actions = (f'<a onclick="mcEditMem(\'{scope}\',{_J(agent_id)},{_J(stem)},this)" title="Edit" style="cursor:pointer;display:inline-flex;padding:3px;border-radius:var(--r);color:var(--text-muted)">{_icon("edit",14)}</a>'
                       f'<a onclick="mcDelMem(\'{scope}\',{_J(agent_id)},{_J(stem)})" title="Delete" style="cursor:pointer;display:inline-flex;padding:3px;border-radius:var(--r);color:var(--status-bad)">{_icon("trash",14)}</a>')
        cardbg = ("background:var(--accent2-7);border-left:3px solid color-mix(in srgb,var(--color-accent-2) 55%,transparent)"
                  if core else "background:var(--color-sand-100)")
        # Body clamps to a single line; the card expands (via JS) only when it overflows.
        bodyhtml = (f'<div class="mc-membody mc-md" style="font-size:12.5px;line-height:1.5;margin-top:4px;'
                    f'max-height:1.55em;overflow:hidden">{_md(body)}</div>')
        # The caret sits *under* the scope icon rather than beside it, so the two share one narrow
        # left column instead of costing two — which is what lets the content start further left.
        # Shown by JS only when the body actually overflows; the whole card is the click target.
        caret = (f'<span class="mc-memexpand mc-cap-caret" title="Show all" '
                 f'style="display:none;align-items:center;justify-content:center;width:16px;'
                 f'color:var(--text-muted)">{_icon("chevron-right",13)}</span>')
        gutter = (f'<div style="flex:none;display:flex;flex-direction:column;align-items:center;gap:3px;'
                  f'padding-top:1px">{icon_span}{caret}</div>') if icon_span or caret else ""
        out += (f'<div id="mem-{E(stem)}" class="mc-frame mc-memcard" data-title="{E(title) if title and title != stem else ""}" data-kind="{E(kind)}" '
                f'style="{cardbg};padding:10px 12px 10px 7px;border-radius:var(--r);margin-bottom:8px;scroll-margin-top:16px">'
                f'<div style="display:flex;align-items:flex-start;gap:8px">'
                f'<div style="flex:1;min-width:0;display:flex;align-items:flex-start;gap:7px">'
                f'{gutter}<div style="flex:1;min-width:0">{tagline}{titleline}{bodyhtml}</div></div>'
                f'<div class="mc-memactions" style="display:flex;gap:8px;flex:none;align-items:center">{upd}{actions}</div></div>'
                f'<template>{E(body)}</template></div>')
    return out + _MEM_EXPAND_JS






def _mem_add_button() -> str:
    return (f'<button class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px;flex:none" '
            f'onclick="mcOpenAddMem()">{_icon("plus", 14, "vertical-align:-2px")}&nbsp;Add memory</button>')


def _mem_search() -> str:
    return (f'<div style="position:relative;margin-bottom:12px">'
            f'<span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);display:flex;'
            f'color:var(--text-faint)">{_icon("search",14)}</span>'
            f'<input id="mem-search" placeholder="Search memories…" oninput="mcMemSearch()" '
            f'style="{_FIELD};padding-left:30px;padding-right:30px">'
            f'<span id="mem-search-x" onclick="mcMemSearchClear()" title="Clear" '
            f'style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);cursor:pointer;'
            f'color:var(--text-faint)">{_icon("x",14)}</span></div>')


def _mem_modals(scope: str, agent_id: str = "", agent_disp: str = "") -> str:
    if scope == "agent" and agent_disp:
        add_title = f"Add memory for {E(agent_disp)}"
        add_sub = f"loads only in {E(_poss(agent_disp))} threads"
        ph_title, ph_text = "E.g. Lodging preference", "E.g. The owner prefers hotels over Airbnbs."
    else:
        add_title = "Add a realm-level memory"
        add_sub = "loads in all threads"
        ph_title, ph_text = "E.g. Handedness", "E.g. Owner is left-handed"
    return (
            # --- add modal ---
            f'<div id="mem-add-modal" class="mc-modal-ov-top" style="padding:48px 16px;overflow:auto" '
            f'onclick="if(event.target===this)mcCloseAddMem()">'
            f'<div class="mc-modal-box" style="width:min(520px,94vw)">'
            f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:10px">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:16px">{add_title}</div>'
            f'<span style="font-size:11px;color:var(--text-soft)">· {add_sub}</span>'
            f'<button type="button" onclick="mcCloseAddMem()" style="margin-left:auto;border:0;background:transparent;cursor:pointer;font-size:20px;line-height:1;color:var(--text-soft)">×</button></div>'
            f'<input type="hidden" id="mem-edit" value="">'
            f'<label style="{_LBL};margin-top:0">Title (optional)</label>'
            f'<input id="mem-title" placeholder="{ph_title}" style="{_FIELD};margin-bottom:6px">'
            f'<label style="{_LBL}">Memory {_STAR}</label>'
            f'<textarea id="mem-text" placeholder="{ph_text}" style="{_TA};min-height:80px"></textarea>'
            f'<div style="margin-top:12px;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" style="color:#fff;font-size:12.5px;padding:6px 14px" '
            f'onclick="mcAddMemory(\'{scope}\',{_J(agent_id)})">Save memory</button>'
            f'<button class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px" onclick="mcCloseAddMem()">Cancel</button>'
            f'<span id="mem-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div></div>'
            # --- edit modal ---
            f'<div id="mem-edit-modal" class="mc-modal-ov" onclick="if(event.target===this)mcCloseEditMem()">'
            f'<div class="mc-modal-box" style="width:min(520px,92vw)">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:16px;margin-bottom:10px">Edit memory</div>'
            f'<input type="hidden" id="mem-ed-scope"><input type="hidden" id="mem-ed-agent"><input type="hidden" id="mem-ed-name">'
            f'<label style="{_LBL};margin-top:0">Title (optional)</label>'
            f'<input id="mem-ed-title" style="{_FIELD};margin-bottom:6px">'
            f'<label style="{_LBL}">Memory {_STAR}</label>'
            f'<textarea id="mem-ed-text" style="{_TA};min-height:90px"></textarea>'
            f'<div style="margin-top:12px;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" style="color:#fff;font-size:12px;padding:5px 12px" onclick="mcSaveEditMem()">Save changes</button>'
            f'<button class="btn btn-secondary" style="font-size:12px;padding:5px 12px" onclick="mcCloseEditMem()">Cancel</button>'
            f'<span id="mem-ed-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div></div>'
            # --- delete modal ---
            f'<div id="mem-del-modal" class="mc-modal-ov" onclick="if(event.target===this)mcCloseDelMem()">'
            f'<div class="mc-modal-box" style="width:min(420px,92vw)">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:16px;margin-bottom:6px">Delete memory?</div>'
            f'<div style="font-size:12.5px;color:var(--text-dim);margin-bottom:12px">This cannot be undone.</div>'
            f'<input type="hidden" id="mem-del-scope"><input type="hidden" id="mem-del-agent"><input type="hidden" id="mem-del-name">'
            f'<div style="display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-secondary" style="font-size:12px;padding:5px 12px" onclick="mcCloseDelMem()">Cancel</button>'
            f'<button class="btn btn-primary" style="background:var(--status-bad);border-color:var(--status-bad);color:#fff;font-size:12px;padding:5px 12px" onclick="mcConfirmDelMem()">Delete</button>'
            f'<span id="mem-del-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div></div>'
            + _MEM_ADD_JS)


def _covenant_updated(realm_root) -> str:
    """When the Covenant was last changed, dd-mm-yy — or "" if it has never been written.

    The file's mtime is the honest answer: every edit goes through /api/save-covenant, which
    rewrites tenets.md, and the file is equally the source of truth when it is edited on disk.
    Memory cards carry their own `updated` field because they are written by agents as well as by
    the owner and the *who* matters; the Covenant is the owner's alone, so the date is the whole
    story.
    """
    p = Path(realm_root) / "tenets.md"
    try:
        if not p.exists():
            return ""
        return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%d-%m-%y")
    except OSError:
        return ""


def _covenant_block(realm, realm_root) -> str:
    """The Covenant — realm tenets.md, pinned above the memories.

    It sits on this page because this page already means "what every agent always knows", and it
    was the only realm-wide document with no surface at all: goals have the Goals page, realm
    memories have this list, and the terms binding all eight agents were editable only on disk.

    It is deliberately NOT a memory card. Memory is facts that change; this is governance that
    shouldn't, and it is yours to write — unlike System memory, which is generated and read-only.
    Styling it as a card would invite both mistakes at once.
    """
    txt = ""
    p = Path(realm_root) / "tenets.md"
    try:
        txt = p.read_text(encoding="utf-8-sig") if p.exists() else ""
    except OSError:
        txt = ""
    heads = [ln.lstrip("# ").strip() for ln in txt.splitlines()
             if ln.startswith("## ")][:6]
    summary = (" · ".join(h.split(". ", 1)[-1] for h in heads)
               if heads else "Not written yet — the terms every minister is bound by.")
    n = len([ln for ln in txt.splitlines() if ln.strip().startswith("- ")])
    upd = _covenant_updated(realm_root)
    stamp = (f'<span style="font-size:10px;text-transform:uppercase;letter-spacing:.07em;'
             f'color:var(--text-ghost)" '
             f'title="When the Covenant was last edited">updated {E(upd)}</span>') if upd else ""
    return (
        f'<div class="mc-frame" style="border-radius:var(--r);padding:14px 16px;margin-bottom:16px;'
        f'border-left:4px solid var(--color-accent-2);background:var(--color-bg)">'
        f'<div style="display:flex;align-items:flex-start;gap:10px">'
        f'<span style="display:flex;flex:none;color:var(--color-accent-2);margin-top:1px">{_icon("agreement",18)}</span>'
        f'<div style="flex:1;min-width:0">'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
        f'<span style="font-family:var(--font-heading);font-weight:600;font-size:15px">The Covenant</span>'
        f'<span style="font-size:10px;text-transform:uppercase;letter-spacing:.07em;'
        f'color:var(--text-soft)">binds every minister · {n} terms</span>'
        f'{stamp}</div>'
        f'<div style="font-size:11.5px;color:var(--text-muted);margin-top:3px;line-height:1.5">{E(summary)}</div>'
        f'<div style="font-size:11px;color:var(--text-faint);margin-top:6px;line-height:1.5">'
        f'Loaded into every agent\'s context, ahead of their own mandate and tenets. Yours to edit — '
        f'unlike System memory, which ARMADA generates.</div></div>'
        f'<div style="display:flex;gap:6px;flex:none">'
        f'<button class="btn btn-secondary" style="font-size:11.5px;padding:4px 10px" '
        f'onclick="mcCovOpen(false)">Read</button>'
        f'<button class="btn btn-secondary" style="font-size:11.5px;padding:4px 10px" '
        f'onclick="mcCovOpen(true)">Edit</button></div></div></div>'
        f'<template id="mc-cov-raw">{E(txt)}</template>')


def _covenant_modal(realm_root=None) -> str:
    """App-native reader/editor for the Covenant (no browser dialogs — house rule).

    The reading view is rendered server-side by the same _md() every other document on the page
    goes through. The first version deferred to a `window.mcMd` that doesn't exist and fell back to
    a <pre>, so the Covenant — the one text written in headings and lists precisely so it can be
    read — displayed as a wall of hashes and hyphens. Raw markdown belongs in the editor and
    nowhere else.
    """
    txt = ""
    if realm_root is not None:
        p = Path(realm_root) / "tenets.md"
        try:
            txt = p.read_text(encoding="utf-8-sig") if p.exists() else ""
        except OSError:
            txt = ""
    rendered = _md(txt) if txt.strip() else (
        '<div style="color:var(--text-muted)">Nothing written yet. Use Edit to set the terms every '
        'agent in this realm is bound by.</div>')
    upd = _covenant_updated(realm_root) if realm_root is not None else ""
    sub = "binds every minister in this realm" + (f" · updated {upd}" if upd else "")
    return (
        f'<template id="mc-cov-rendered">{E(rendered)}</template>' +
        '<div id="mc-cov-modal" style="display:none;position:fixed;inset:0;z-index:70;'
        'background:var(--text-38);align-items:center;'
        'justify-content:center;padding:24px" onclick="if(event.target===this)mcCovClose()">'
        '<div class="mc-frame" style="background:var(--color-bg);border-radius:var(--r);'
        'width:min(860px,96vw);max-height:88vh;display:flex;flex-direction:column;padding:18px 20px">'
        '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:4px">'
        '<div style="font-family:var(--font-heading);font-weight:600;font-size:17px">The Covenant</div>'
        f'<div id="mc-cov-sub" style="font-size:11.5px;color:var(--text-muted)">{E(sub)}</div></div>'
        '<div id="mc-cov-read" class="mc-md" style="overflow:auto;font-size:13px;line-height:1.6;'
        'padding:6px 2px 2px"></div>'
        '<textarea id="mc-cov-edit" spellcheck="false" style="display:none;flex:1;min-height:420px;'
        'font-family:ui-monospace,Menlo,monospace;font-size:12.5px;line-height:1.55;padding:10px;'
        'border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);'
        'color:var(--color-text);resize:vertical"></textarea>'
        '<div style="display:flex;align-items:center;gap:8px;margin-top:12px">'
        '<span id="mc-cov-msg" style="font-size:11.5px;color:var(--text-muted);flex:1"></span>'
        '<button class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px" '
        'onclick="mcCovClose()">Close</button>'
        '<button id="mc-cov-save" class="btn" style="display:none;font-size:12.5px;padding:6px 12px" '
        'onclick="mcCovSave(this)">Save</button></div></div></div>'
        # Script body lives in webui/static/js/covenant.js (Phase 2, 2.1); it reads mc-cov-sub's own
        # server-rendered text at load time instead of a baked-in copy of `sub`.
        + _COVENANT_JS)


def _realm_memory(realm, realm_root) -> str:
    cards = _mem_cards(_list_mem(Path(realm_root) / "memory"), "realm", realm=realm)
    links = "".join(f'<a href="/agent/{E(a.id)}/memories" class="mc-frame" style="text-decoration:none;color:inherit;display:flex;'
                    f'align-items:center;justify-content:space-between;padding:8px 12px;border-radius:var(--r);margin-bottom:6px">'
                    f'<span style="font-size:12.5px">{E(a.display)}</span>'
                    f'<span style="display:inline-flex;align-items:center;gap:5px;font-size:11.5px;color:var(--text-muted)">'
                    f'<span style="display:flex">{_icon("brain",13)}</span>{len(_agent_memory(realm_root, a.id))} ›</span></a>'
                    for a in realm.agents)
    header = (f'<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:14px">'
              f'<h2 style="font-family:var(--font-heading);font-size:26px;margin:0">Memory'
              f'<span style="font-family:var(--font-body);font-weight:400;font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
              f'color:var(--text-soft);margin-left:6px">· realm-level · loads for every agent</span></h2>'
              f'{_mem_add_button()}</div>')
    return (f'<div style="padding:18px 24px 24px">{header}'
            f'{_covenant_block(realm, realm_root)}'
            f'<div style="display:grid;grid-template-columns:1fr 320px;gap:22px">'
            f'<div>{_mem_search()}{cards}</div>'
            f'<div><div style="font-family:var(--font-heading);font-weight:600;font-size:15px;margin-bottom:2px">Per-agent memories</div>'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--text-soft);margin-bottom:8px">loads only in the agent\'s threads</div>{links}</div></div>'
            f'{_mem_modals("realm")}{_covenant_modal(realm_root)}</div>')
