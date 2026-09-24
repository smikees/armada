"""Goals rendering (realm goals page + agent goals tab) (Layer 2, Phase 3).

Imports lower layers (never _core); _core re-imports these names.
"""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import goals as goalsmod
from ..icons import ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR
from ._base import (E, _J, _STAR, _md_inline, _md, _page_title, _chip, _pill, _tone, _poss)
from ..assets import GOALSEARCH_JS as _GOALSEARCH_JS  # Phase 2, 2.1
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _ordinal, _next_hint, _fmt_ts)
from ..assets import GOALS_JS as _GOALS_JS
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)


_GOAL_STATUS_COLOR = {
    "Not started": "--status-idle", "On track": "--status-ok",
    "At risk": "--status-warn", "Blocked": "--status-bad", "Done": "--color-accent-2",
}


def _goal_status_badge(status: str) -> str:
    if not status:
        return ""
    c = _GOAL_STATUS_COLOR.get(status, "--status-idle")
    return _pill(E(status), _tone(c))


def _goal_owner_chips(realm, realm_root, goal: dict) -> str:
    """Owners of a goal: coordinator pinned (non-removable) + mapped members (removable ×)."""
    stem = goal["stem"]
    mapped = [a for a in realm.members if a.id in set(goal.get("agents", []))]
    base = ("display:inline-flex;align-items:center;gap:5px;font-size:11.5px;"
            "padding:3px 4px 3px 3px;border-radius:999px;color:var(--color-text);")
    chip = (base + "background:var(--accent-13);"
                   "border:1px solid var(--accent-38)")
    # The coordinator is an owner of every goal and can't be removed, so its chip is grey rather
    # than accent-tinted: the accent tint is what the removable ones use, and giving both the same
    # treatment implied you could take this one off too.
    pinned = (base + "background:var(--text-6);"
                     "border:1px solid var(--color-divider);"
                     "color:var(--text-62)")
    def av(a):
        # No clipping wrapper — the portrait already rounds itself, and overflow:hidden here sliced
        # the colour crescent off the side of every owner chip.
        return _portrait(realm_root, a, 18)
    out = ""
    if realm.coordinator:
        c = realm.coordinator
        out += (f'<span title="{E(realm.theme_coordinator)} — always an owner" style="{pinned};padding-right:9px">'
                f'{av(c)}{E(c.display)}<span style="display:inline-flex;color:var(--text-38)">{_icon("pin",11)}</span></span>')
    for a in mapped:
        out += (f'<span style="{chip}">{av(a)}{E(a.display)}'
                f'<span onclick="mcGoalRemoveOwner({_J(stem)},{_J(a.id)})" title="Remove owner" '
                f'style="cursor:pointer;display:inline-flex;padding:1px;border-radius:50%;color:var(--text-faint)">{_icon("x",11)}</span></span>')
    if not mapped:
        out += ('<span style="font-size:11px;color:var(--text-42)">'
                '— drag an agent here to add an owner</span>')
    return out


def _goal_cards(realm, realm_root, items) -> str:
    if not items:
        return ('<div class="mc-frame" style="font-size:12.5px;color:var(--text-muted);'
                'padding:18px;text-align:center;border-style:dashed">'
                'No goals yet. Use <b>Add goal</b> above, then drag agents from the right to set owners.</div>')
    out = ""
    for g in items:
        stem = g["stem"]
        badge = _goal_status_badge(g.get("effective_status", "") or g.get("status", ""))
        overdue = g.get("overdue")
        if g.get("target_label"):
            col = "var(--status-bad)" if overdue else "var(--text-soft)"
            eta = (f'<span style="font-size:11px;white-space:nowrap;color:{col}">'
                   f'{_icon("target", 12, "display:inline-block;vertical-align:-2px")} ETA {E(g["target_label"])}'
                   f'{" · overdue" if overdue else ""}</span>')
        else:
            eta = (f'<span style="font-size:11px;white-space:nowrap;color:var(--text-38)">'
                   f'{_icon("target", 12, "display:inline-block;vertical-align:-2px")} ETA — not set</span>')
        meta = f'<span style="font-size:10px;color:var(--text-ghost);white-space:nowrap">Modified {E(g["modified"])}</span>'
        out += (f'<div id="goal-{E(stem)}" class="mc-frame mc-goalcard" data-stem="{E(stem)}" '
                f'ondragover="mcGoalDragOver(event)" ondragleave="mcGoalDragLeave(event)" ondrop="mcGoalDrop(event,{_J(stem)})" '
                f'style="background:var(--color-sand-100);padding:12px 14px;border-radius:var(--r);margin-bottom:10px">'
                # Title row and body are siblings, not a column sharing a flex row with the actions.
                # Nesting them meant the actions cluster reserved its width down the whole card, so
                # every line of the goal text stopped short of the right edge for no visible reason.
                f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:4px">'
                f'<div style="flex:1;min-width:0;display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
                f'<span style="font-family:var(--font-heading);font-weight:600;font-size:14.5px">{E(g["title"])}</span>{badge}{eta}</div>'
                f'<div style="display:flex;gap:8px;flex:none;align-items:center">{meta}'
                f'<a onclick="mcEditGoal(this)" title="Edit" style="cursor:pointer;display:inline-flex;padding:3px;border-radius:var(--r);color:var(--text-muted)">{_icon("edit",14)}</a>'
                f'<a onclick="mcDelGoal({_J(stem)},{_J(g["title"])})" title="Delete" style="cursor:pointer;display:inline-flex;padding:3px;border-radius:var(--r);color:var(--status-bad)">{_icon("trash",14)}</a></div></div>'
                f'<div class="mc-goalbody mc-md" style="font-size:12.5px;line-height:1.5;color:color-mix(in srgb,var(--color-text) 82%,transparent)">{_md(g["body"][:800])}</div>'
                f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:10px;padding-top:10px;border-top:1px solid var(--color-divider)">'
                f'<span style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-faint);margin-right:2px">Owners:</span>'
                f'{_goal_owner_chips(realm, realm_root, g)}</div>'
                f'<template class="mc-goalraw" data-stem="{E(stem)}" data-title="{E(g["title"])}" data-status="{E(g.get("status",""))}" data-target="{E(g.get("target",""))}">{E(g["body"])}</template>'
                f'</div>')
    return out


def _goal_roster(realm, realm_root) -> str:
    """Right-hand roster of draggable agents; drop one onto a goal to make it an owner."""
    def av(a):
        return _portrait(realm_root, a, 20)
    chips = ""
    for a in realm.members:
        chips += (f'<div draggable="true" ondragstart="mcGoalDragStart(event,{_J(a.id)})" class="mc-rosteragent" '
                  f'style="display:flex;align-items:center;gap:8px;padding:6px 8px;border:1px solid var(--color-divider);'
                  f'border-radius:var(--r);background:var(--color-bg);cursor:grab;margin-bottom:6px;font-size:12.5px">'
                  f'{av(a)}<span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{E(a.display)}</span>'
                  f'<span style="display:flex;color:var(--text-35)">{_icon("grip-vertical",13)}</span></div>')
    coord_note = (f'<div style="font-size:11px;color:var(--text-faint);margin-top:8px;'
                  f'padding-top:8px;border-top:1px solid var(--color-divider)">{E(realm.theme_coordinator)} '
                  f'({E(realm.coordinator.display)}) is an owner of every goal by default.</div>') if realm.coordinator else ""
    return (f'<div class="mc-frame" style="padding:12px;border-radius:var(--r)">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:13px">Agents</div>'
            f'<div style="font-size:11px;color:var(--text-muted);margin:2px 0 10px">'
            f'Drag an agent to a goal to make them an owner</div>{chips}{coord_note}</div>')


def _goal_status_options(sel: str = "") -> str:
    return "".join(f'<option{" selected" if s == sel else ""}>{E(s)}</option>' for s in goalsmod.STATUSES)


def _goal_modals(realm, add_title: str = "Add a goal", owner_id: str = "") -> str:
    """Add / edit / delete goal modals. When owner_id is set (agent Goals page), the new goal is
    auto-owned by that agent and the title reads 'Add goal for …'."""
    fh = "height:34px"   # same height across title / status / date
    if owner_id and realm.coordinator:
        msg = f"Owned by this agent and {E(realm.coordinator.display)} ({E(realm.theme_coordinator)})."
    elif realm.coordinator:
        msg = f"{E(realm.theme_coordinator)} is an owner by default."
    else:
        msg = ""
    add = (f'<div id="goal-add-modal" class="mc-modal-ov-top" style="padding:48px 16px;overflow:auto" '
           f'onclick="if(event.target===this)mcCloseAddGoal()">'
           f'<div class="mc-modal-box" style="width:min(620px,94vw)">'
           f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:10px">'
           f'<div class="mc-h-card" style="margin-bottom:0px">{add_title}</div>'
           f'<button type="button" class="mc-x" onclick="mcCloseAddGoal()" title="Close" aria-label="Close">×</button></div>'
           f'<input type="hidden" id="goal-owner" value="{E(owner_id)}">'
           f'<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px">'
           f'<div><label class="mc-label" style="margin-top:0">Title {_STAR}</label><input id="goal-title" placeholder="E.g. Become proficient in Spanish." class="mc-field"></div>'
           f'<div><label class="mc-label" style="margin-top:0">Status</label><select id="goal-status" class="mc-field">{_goal_status_options("Not started")}</select></div>'
           f'<div><label class="mc-label" style="margin-top:0">Target date (ETA)</label><input type="date" id="goal-target" class="mc-field"></div></div>'
           f'<label class="mc-label">Description</label>'
           f'<textarea id="goal-desc" placeholder="What does done look like? Why does it matter?" class="mc-textarea" style="min-height:80px"></textarea>'
           f'<div style="margin-top:12px;display:flex;gap:8px;align-items:center;justify-content:flex-end">'
           f'<span id="goal-msg" style="margin-right:auto;font-size:12px;color:var(--text-muted)">{msg}</span>'
           f'<button class="btn btn-secondary" onclick="mcCloseAddGoal()">Cancel</button>'
           f'<button class="btn btn-primary" onclick="mcAddGoal()">Add goal</button>'
           f''
           f'</div></div></div>')
    edit = (f'<div id="goal-edit-modal" class="mc-modal-ov-top" style="padding:48px 16px;overflow:auto" '
            f'onclick="if(event.target===this)mcCloseEditGoal()">'
            f'<div class="mc-modal-box" style="width:min(620px,94vw)">'
            f'<div class="mc-h-card">Edit goal</div>'
            f'<input type="hidden" id="goal-ed-stem">'
            f'<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px">'
            f'<div><label class="mc-label" style="margin-top:0">Title {_STAR}</label><input id="goal-ed-title" class="mc-field"></div>'
            f'<div><label class="mc-label" style="margin-top:0">Status</label><select id="goal-ed-status" class="mc-field">{_goal_status_options()}</select></div>'
            f'<div><label class="mc-label" style="margin-top:0">Target date (ETA)</label><input type="date" id="goal-ed-target" class="mc-field"></div></div>'
            f'<label class="mc-label">Description</label>'
            f'<textarea id="goal-ed-desc" class="mc-textarea" style="min-height:100px"></textarea>'
            f'<div style="margin-top:12px;display:flex;gap:8px;align-items:center;justify-content:flex-end">'
            f'<span id="goal-ed-msg" style="margin-right:auto;font-size:12px;color:var(--text-muted)"></span>'
            f'<button class="btn btn-secondary btn-sm" onclick="mcCloseEditGoal()">Cancel</button>'
            f'<button class="btn btn-primary btn-sm" onclick="mcSaveEditGoal()">Save changes</button>'
            f'</div></div></div>')
    dele = (f'<div id="goal-del-modal" class="mc-modal-ov" onclick="if(event.target===this)mcCloseDelGoal()">'
            f'<div class="mc-modal-box" style="width:min(420px,92vw)">'
            f'<input type="hidden" id="goal-del-stem">'
            f'<div class="mc-h-card" style="margin-bottom:6px">Delete goal?</div>'
            f'<div style="font-size:12.5px;color:var(--text-dim);margin-bottom:14px">'
            f'Delete <b id="goal-del-name"></b>. This removes it from every owner\'s context. This can\'t be undone.</div>'
            f'<div style="display:flex;gap:8px;justify-content:flex-end">'
            f'<button class="btn btn-secondary" onclick="mcCloseDelGoal()">Cancel</button>'
            f'<button class="btn btn-danger" onclick="mcConfirmDelGoal()">Delete</button>'
            f'</div></div></div>')
    return add + edit + dele


def _realm_goals(realm, realm_root) -> str:
    items = goalsmod.list_goals(realm_root)
    addicon = _icon("plus", 14)
    header = (f'<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:14px">'
              f'<h2 style="font-family:var(--font-heading);font-size:26px;margin:0">Goals'
              f'<span style="font-family:var(--font-body);font-weight:400;font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
              f'color:var(--text-soft);margin-left:6px">· realm objectives · loaded into every owner’s threads</span></h2>'
              f'<button class="btn btn-secondary btn-sm" style="flex:none" onclick="mcOpenAddGoal()">{addicon}Add goal</button></div>')
    search = (f'<div style="margin-bottom:12px"><div style="position:relative">'
              f'<span style="position:absolute;left:10px;top:50%;transform:translateY(-50%);display:flex;color:var(--text-muted);pointer-events:none">{_icon("search", 14)}</span>'
              f'<input id="goal-search" oninput="mcGoalSearch()" placeholder="Search goals…" '
              f'style="width:100%;box-sizing:border-box;padding:7px 30px 7px 32px;border:1px solid var(--color-divider);'
              f'border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;font-size:13px">'
              f'<span id="goal-search-x" onclick="mcGoalSearchClear()" title="Clear" style="display:none;position:absolute;'
              f'right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--text-muted);padding:2px">{_icon("x", 13)}</span></div>'
              f'<span id="goal-search-empty" style="display:none;font-size:12px;color:var(--text-muted);margin-top:8px">No goals match.</span></div>')
    return (f'<div style="padding:18px 24px 24px;max-width:1040px">{header}'
            f'<div style="display:grid;grid-template-columns:1fr 240px;gap:22px;align-items:start">'
            f'<div>{search}{_goal_cards(realm, realm_root, items)}</div>'
            f'<div style="position:sticky;top:8px">{_goal_roster(realm, realm_root)}</div></div>'
            f'{_goal_modals(realm)}</div>{_GOALS_JS}'
            + _GOALSEARCH_JS)


def _tab_goals(realm, realm_root, a) -> str:
    """Per-agent Goals tab: the goals this agent advances, with an add-goal modal that
    auto-maps the agent as an owner."""
    items = goalsmod.goals_for_agent(realm_root, a.id, is_coord=a.is_coordinator)
    addicon = _icon("plus", 14)
    sub = "owns every goal (coordinator)" if a.is_coordinator else "goals this agent advances"
    header = (f'<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:14px">'
              f'<div style="font-family:var(--font-heading);font-weight:600;font-size:17px">{E(_poss(a.display))} goals '
              f'<span style="font-weight:400;font-size:12px;color:var(--text-muted)">· {sub}</span></div>'
              f'<button class="btn btn-secondary btn-sm" style="flex:none" onclick="mcOpenAddGoal()">{addicon}Add goal</button></div>')
    if items:
        body = _goal_cards(realm, realm_root, items)
    else:
        body = ('<div class="mc-frame" style="font-size:12.5px;color:var(--text-muted);'
                'padding:18px;text-align:center;border-style:dashed">'
                f'No goals mapped to {E(a.display)} yet. Use <b>Add goal</b> to create one for them, '
                'or drag them onto a goal from the Goals section.</div>')
    return (f'<div style="padding:18px 24px 24px;max-width:900px">{header}{body}'
            f'{_goal_modals(realm, f"Add goal for {E(a.display)}", a.id)}</div>{_GOALS_JS}')
