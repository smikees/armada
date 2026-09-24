"""Threads / chat rendering (Layer 2, carved from _core.py in Phase 3).

The thread rail, chat centre/composer, turn + activity-segment rendering, thread artifacts and
capabilities rails, and per-thread meta helpers. Imports lower layers (never _core); _core
re-imports these names.
"""
from __future__ import annotations
import html, json, datetime, time, re
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
from ..assets import THRESIZE_JS as _THRESIZE_JS, THREADLIST_JS as _THREADLIST_JS_ASSET  # Phase 2, 2.1
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _chat_running, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)
import logging
from ..util import swallowed
from .. import util
log = logging.getLogger(__name__)


def _user_avatar_file(realm_root):
    d = Path(realm_root) / "user"
    for ext in ("png", "jpg", "jpeg", "webp", "gif"):
        f = d / f"avatar.{ext}"
        if f.exists():
            return f
    return None


def _user_avatar(realm_root, size: int) -> str:
    """The owner's avatar <img> if one is set, else '' (callers fall back to the 'You' chip)."""
    f = _user_avatar_file(realm_root)
    if f:
        t = int(f.stat().st_mtime)
        return (f'<img src="/user-avatar?t={t}" width="{size}" height="{size}" '
                f'style="width:{size}px;height:{size}px;object-fit:cover;display:block" alt="You">')
    return ""


def _sub(active: str, agent_id: str, counts: dict) -> str:
    # (display label, url slug) — slug stays "skills" for routing even though we show "Capabilities"
    tabs = [("Threads", "threads"), ("Goals", "goals"), ("Jobs", "jobs"), ("Inbox", "inbox"),
            ("Memories", "memories"), ("Artefacts", "artefacts"), ("Capabilities", "skills")]
    out = ""
    for label, slug in tabs:
        cur = 'aria-current="page"' if (label == active or slug == active.lower()) else ""
        n = counts.get(label)
        badge = (f' <span style="opacity:.5">{n}</span>') if n else ""
        out += f'<a class="mc-sub" href="/agent/{E(agent_id)}/{slug}" {cur}>{E(label)}{badge}</a>'
    return f'<div style="display:flex;gap:16px;padding:0 24px;border-bottom:1px solid var(--color-divider);flex:none">{out}</div>'


def _est_tokens(chars: int) -> str:
    t = max(0, chars) // 4
    return f"{t/1000:.1f}k" if t >= 1000 else str(t)


def _thread_title(meta: dict, slug: str) -> str:
    return meta.get("titles", {}).get(slug) or ("Main" if slug == "main" else slug.replace("-", " ").strip().title())


def _meta_path(agent_dir) -> Path:
    return Path(agent_dir) / "threads" / "meta.json"


def _touch_last_thread(agent_dir, slug: str) -> None:
    """Remember the thread the owner is viewing so returning to the Threads tab reopens it (not 'main').
    Persisted in meta.json; written only when it actually changes.

    Runs during a render, and meta.json is also rewritten by the thread routes and by a run posting a
    reply — so the read-modify-write holds the file's lock (4.3 L5), and the common case (nothing to
    change) takes no lock at all."""
    if _thread_meta(agent_dir).get("last") == slug:
        return
    f = _meta_path(agent_dir)
    try:
        with util.file_lock(f):
            meta = _thread_meta(agent_dir)            # re-read under the lock
            if meta.get("last") == slug:
                return
            meta["last"] = slug
            util.write_json_atomic(f, meta)
    except OSError:
        log.debug("_touch_last_thread: could not persist the last-open thread", exc_info=True)


def _write_thread_meta(agent_dir, meta: dict) -> None:
    """Atomic write of meta.json. Callers doing a read-modify-write hold util.file_lock on it."""
    try:
        util.write_json_atomic(_meta_path(agent_dir), meta)
    except OSError:
        log.debug("_write_thread_meta: could not write meta.json", exc_info=True)


def _mark_thread_unread(agent_dir, slug: str) -> None:
    """Flag a thread as having unseen output (drives the teal 'unseen' status dot). Called when a run
    posts a reply, so the owner sees there's something new even away from that thread."""
    if _thread_meta(agent_dir).get("unread", {}).get(slug):
        return                                   # already flagged — no rewrite
    with util.file_lock(_meta_path(agent_dir)):
        meta = _thread_meta(agent_dir)
        if meta.get("unread", {}).get(slug):
            return
        meta.setdefault("unread", {})[slug] = True
        _write_thread_meta(agent_dir, meta)


def _clear_thread_unread(agent_dir, slug: str, render_meta: dict | None = None) -> None:
    """Opening/viewing a thread clears its unseen flag. Updates the in-memory meta the current render
    reads from (if given) so the thread list shows it read immediately, and persists to disk."""
    was = bool((render_meta or _thread_meta(agent_dir)).get("unread", {}).get(slug))
    if render_meta is not None:
        render_meta.setdefault("unread", {})[slug] = False
    if not was:
        return                                   # already read — skip the disk write
    with util.file_lock(_meta_path(agent_dir)):
        disk = _thread_meta(agent_dir)           # re-read under the lock so no concurrent write is lost
        disk.setdefault("unread", {})[slug] = False
        _write_thread_meta(agent_dir, disk)


def _ordered_threads(agent_dir):
    """Thread slugs in display order: main first, then pinned, then the rest (by saved order, else name)."""
    from ..threads import Thread
    names = Thread.list_threads(agent_dir)
    if "main" not in names:
        names = ["main"] + names
    meta = _thread_meta(agent_dir)
    order = meta.get("order", [])
    pinned = meta.get("pinned", {})

    archived = set(meta.get("archived", {}))

    def key(n):
        grp = 1 if pinned.get(n) else 2
        idx = order.index(n) if n in order else 10 ** 6
        return (grp, idx, n)
    rest = sorted([n for n in names if n != "main" and n not in archived], key=key)
    return ["main"] + rest, meta


# Modal HTML stays inline; script body lives in webui/static/js/threadlist.js (Phase 2, 2.1).
_THREADLIST_JS = ("""
<div id="mc-thren-modal" class="mc-modal-ov" style="z-index:250" onclick="if(event.target===this)mcThrenClose()">
 <div class="mc-modal-box" style="width:min(440px,92vw)">
  <div style="font-family:var(--font-heading);font-weight:600;font-size:16px;margin-bottom:10px">Rename thread</div>
  <input type="hidden" id="thren-agent"><input type="hidden" id="thren-slug">
  <input id="thren-title" style="display:block;width:100%;padding:7px 9px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;font-size:14px">
  <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
   <button class="btn btn-primary" style="color:#fff;font-size:12.5px;padding:6px 14px" onclick="mcThrenSave()">Save</button>
   <button class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px" onclick="mcThrenClose()">Cancel</button>
   <span id="thren-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div></div>"""
    + _THREADLIST_JS_ASSET)


def _turn_actions(role: str, idx: int, aid: str, thread: str, is_last_user: bool, when: str) -> str:
    def btn(icon, title, onclick, cls=""):
        return (f'<button class="mc-act {cls}" title="{title}" onclick="{onclick}" '
                f'style="border:0;background:transparent;cursor:pointer;padding:3px;border-radius:var(--r);display:inline-flex;'
                f'color:var(--text-42)">{_icon(icon, 14)}</button>')
    ts = (f'<span style="font-size:10.5px;color:var(--text-ghost)">{E(when)}</span>') if when else ""
    acts = ts + btn("copy", "Copy", "mcCopyTurn(this)")
    align = "flex-start"
    if role == "user":
        align = "flex-end"
        acts += btn("refresh-cw", "Restart from here", f"mcRestartTurn(this,'{E(aid)}','{E(thread)}',{idx})")
        if is_last_user:
            acts += btn("pencil", "Edit", f"mcEditTurn(this,'{E(aid)}','{E(thread)}',{idx})", "mc-editbtn")
    return (f'<div class="mc-turn-actions" style="display:flex;align-items:center;gap:3px;margin-top:3px;justify-content:{align}">{acts}</div>')


_EVENT_ICONS = {
    "scheduled_task": "clock", "task_created": "clock", "schedule": "clock",
    "reminder": "bell", "job_run": "zap", "goal": "target", "memory": "brain",
    "connector": "cap-connector", "extension": "puzzle", "skill": "cap-skill", "plugin": "cap-plugin",
    "compaction": "sparkles", "note": "info",
}


def _event_card(m: dict) -> str:
    """A non-message thread entry rendered as an inline, centered card — e.g. 'Created
    scheduled task …' or a compaction progress bar. Distinct from chat bubbles: no avatar,
    full-width, subtle border. Driven by a {role:'event', type, title, …} jsonl entry."""
    et = str(m.get("type", "") or "").strip().lower()
    title = E(str(m.get("title", "") or "").strip())
    subtitle = E(str(m.get("subtitle", "") or "").strip())
    status = str(m.get("status", "") or "").strip().lower()
    when = str(m.get("ts", ""))[11:16]
    href = str(m.get("href", "") or "").strip()
    muted = "var(--text-muted)"
    faint = "var(--text-ghost)"

    # --- compaction: a live progress bar while summarizing, or a settled marker when done ---
    if et == "compaction":
        pct = m.get("pct")
        running = status in ("running", "in_progress", "progress") and pct is not None
        if running:
            try:
                p = max(0, min(100, int(round(float(pct)))))
            except (TypeError, ValueError):
                p = 0
            label = title or "Compacting our conversation so we can keep chatting…"
            return (f'<div class="mc-turn mc-event" data-role="event" style="margin:8px auto 14px;max-width:88%">'
                    f'<div style="display:flex;align-items:center;gap:9px;font-size:12px;color:{muted};margin-bottom:6px">'
                    f'<span class="mc-ev-spin" style="width:15px;height:15px;flex:none;color:var(--color-accent)">{_icon("refresh-cw", 15)}</span>'
                    f'<span>{E(label)}</span></div>'
                    f'<div style="display:flex;align-items:center;gap:8px">'
                    f'<div style="flex:1;height:4px;border-radius:3px;background:var(--text-10);overflow:hidden">'
                    f'<div style="width:{p}%;height:100%;border-radius:3px;background:var(--text-muted);transition:width .3s"></div></div>'
                    f'<span style="font-size:11px;color:{muted};min-width:30px;text-align:right">{p}%</span></div></div>')
        # settled
        return (f'<div class="mc-turn mc-event" data-role="event" style="align-self:center;margin:2px auto 10px">'
                f'<div style="display:inline-flex;align-items:center;gap:6px;background:var(--color-surface);border-radius:999px;'
                f'padding:5px 13px;font-size:11.5px;color:{muted}">'
                f'<span style="width:13px;height:13px;flex:none;opacity:.7">{_icon("sparkles", 13)}</span>'
                f'{E(title or "Conversation compacted")}</div></div>')

    # --- generic event card (scheduled task, reminder, job run, note, …) ---
    icon = str(m.get("icon", "") or "").strip() or _EVENT_ICONS.get(et, "info")
    accent = et in ("scheduled_task", "task_created", "schedule", "reminder")
    ring = "var(--color-accent)" if accent else muted
    tint = ("color-mix(in srgb,var(--color-accent) 8%,var(--color-bg))" if accent else "var(--color-bg)")
    right = (f'<span style="font-size:11.5px;color:{muted};white-space:nowrap">{subtitle}</span>') if subtitle else ""
    chev = (f'<span style="width:16px;height:16px;flex:none;color:{faint}">{_icon("chevron-right", 16)}</span>') if href else ""
    nav = (f' onclick="location.href={_J(href)}" ' if href.startswith("/") else "")
    cur = "cursor:pointer;" if nav else ""
    return (f'<div class="mc-turn mc-event" data-role="event"{nav} style="{cur}display:flex;align-items:center;gap:10px;'
            f'margin:8px auto 14px;max-width:92%;background:{tint};border:1px solid var(--color-divider);'
            f'border-radius:var(--r);padding:9px 12px">'
            f'<span style="width:26px;height:26px;border-radius:50%;flex:none;display:grid;place-items:center;'
            f'background:color-mix(in srgb,{ring} 12%,transparent);color:{ring}">{_icon(icon, 15)}</span>'
            f'<div style="flex:1;min-width:0"><div style="font-size:12.5px;line-height:1.35;color:var(--color-text);'
            f'overflow:hidden;text-overflow:ellipsis">{title or "Event"}</div></div>'
            f'{right}{chev}'
            + (f'<span style="font-size:10.5px;color:{faint};white-space:nowrap;margin-left:2px">{E(when)}</span>' if when and not subtitle else "")
            + '</div>')


def _render_segments(segs) -> str:
    """Render an assistant turn's full activity trail: text notes (Markdown), tool-activity
    chips ('Ran a command · 2 notes'), and any thought-process blocks — like the Claude app."""
    out = []
    for s in segs:
        t = s.get("t")
        c = str(s.get("c", ""))
        if t == "text":
            out.append(f'<div class="mc-md" style="margin-bottom:8px">{_md(c)}</div>')
        elif t == "think":
            out.append(f'<details class="mc-think"><summary>{_icon("sparkles",12)}Thought process</summary>'
                       f'<div class="mc-md" style="margin-top:6px">{_md(c)}</div></details>')
        elif t == "act":
            notes = s.get("notes") or 0
            nt = f' · {notes} note{"s" if notes != 1 else ""}' if notes else ""
            out.append(f'<div class="mc-actchip">{_icon("wrench",13)}<span>{E(c)}{nt}</span></div>')
    return "".join(out)


def _attachments_html(att, aid: str, thread: str) -> str:
    """Thumbnails for image attachments + name chips for file attachments, in a user turn."""
    if not att:
        return ""
    out = []
    for a in att:
        name = E(str(a.get("name", "")))
        if a.get("kind") == "image" and a.get("file"):
            src = f'/thread-file?agent={E(aid)}&thread={E(thread)}&name={E(str(a.get("file")))}'
            out.append(f'<a href="{src}" target="_blank" class="mc-att-img" title="{name}"><img src="{src}" alt="{name}"></a>')
        else:
            out.append(f'<span class="mc-att-file" title="{name}">{_icon("paperclip",12)}<span>{name}</span></span>')
    return f'<div class="mc-att-row">{"".join(out)}</div>'


def _turn(role: str, raw, ts: str, idx: int, is_last_user: bool, aid: str, thread: str, disp: str, coord: bool, av: str = "", userav: str = "", seg=None, att=None) -> str:
    content = E(str(raw).strip())
    when = str(ts)[11:16]
    tpl = f'<template class="mc-raw">{content}</template>'
    if role == "assistant":
        body = _render_segments(seg) if seg else f'<div class="mc-body mc-md">{_md(str(raw).strip())}</div>'
        return (f'<div class="mc-turn" data-role="assistant" data-idx="{idx}" style="margin-bottom:12px">'
                f'<div style="display:flex;gap:10px"><div style="display:flex;flex:none">{av or _bust(28, coord)}</div>'
                f'<div style="flex:1;min-width:0"><div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">{E(disp)}</div>'
                f'<div class="mc-body">{body}</div>'
                f'{_turn_actions("assistant", idx, aid, thread, False, when)}</div></div>{tpl}</div>')
    ubub = (f'<div style="width:28px;height:28px;border-radius:50%;overflow:hidden;flex:none;border:1px solid var(--color-divider)">{userav}</div>'
            if userav else
            '<div style="width:28px;height:28px;border-radius:50%;background:var(--color-accent);color:#fff;display:grid;place-items:center;font-size:11px;flex:none">You</div>')
    return (f'<div class="mc-turn" data-role="user" data-idx="{idx}" style="margin-bottom:12px">'
            f'<div style="display:flex;flex-direction:row-reverse;gap:10px">{ubub}'
            f'<div style="max-width:72%">{_attachments_html(att, aid, thread)}'
            f'<div class="mc-body mc-md" style="background:var(--color-sand-100);border-radius:var(--r);padding:8px 10px;font-size:13px;line-height:1.5">{_md(str(raw).strip())}</div>'
            f'{_turn_actions("user", idx, aid, thread, is_last_user, when)}</div></div>{tpl}</div>')


def _agent_model_label(realm_root, aid: str) -> str:
    """The agent's model label (its own, else the realm default) for context-window sizing."""
    m = None
    try:
        m = json.loads((Path(realm_root) / "agents" / aid / "agent.json").read_text(encoding="utf-8-sig")).get("model")
    except Exception:  # noqa
        swallowed(log, '_agent_model_label: failed; ignored')
    if not m:
        try:
            m = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig")).get("default_model")
        except Exception:  # noqa
            swallowed(log, '_agent_model_label: failed; ignored')
    return m or ""
_CAP_ICON = {"connectors": "cap-connector", "extensions": "puzzle", "skills": "cap-skill",
             "plugins": "cap-plugin", "builtin": "search"}
_CAP_KIND_LABEL = {"connectors": "connector", "extensions": "extension", "skills": "skill",
                   "plugins": "plugin", "builtin": "built-in"}


def _thread_caps_used(msgs: list, realm_root=None, agent_id: str = "", thread: str = "") -> dict:
    """Capabilities the agent ACTUALLY exercised in this thread, grouped by type. Read from the
    `caps_used` recorded on each assistant turn (a real tool call to that connector/skill), NOT
    guessed from keywords — so a thread that used no capability shows nothing.

    Each one is marked `new` when the agent gained it *through this conversation* rather than
    already having it. Those are different events for whoever is reading: one is an agent doing its
    job, the other is an agent's reach growing. Without the distinction the rail can only say "it
    used these", which is exactly the fact that hides the interesting half.
    """
    out, seen = {}, set()
    for m in msgs:
        if m.get("role") != "assistant":
            continue
        for c in (m.get("caps_used") or []):
            kind = c.get("type")
            key = (kind, c.get("id") or c.get("name"))
            if not kind or key in seen:
                continue
            seen.add(key)
            item = dict(c)
            if realm_root and agent_id and thread:
                try:
                    from .. import capabilities as _caps
                    item["new"] = _caps.granted_in_thread(
                        realm_root, agent_id, c.get("id") or c.get("name"), thread)
                except Exception:  # noqa — a badge must never cost the rail
                    swallowed(log, '_thread_caps_used: failed; ignored')
            out.setdefault(kind, []).append(item)
    return out


def _thread_caps_rail(caps: dict) -> str:
    """The 'Capabilities in this thread' block for the right rail, grouped by type under its icon.
    Always rendered — shows a placeholder until the agent actually invokes a connector/skill/plugin."""
    rows = ""
    for kind in ("connectors", "extensions", "skills", "plugins", "builtin"):
        items = caps.get(kind) or []
        if not items:
            continue
        chips = "".join(
            # A newly-granted capability wears the accent and says so. The tooltip carries the
            # reason it matters — "this agent could not do this before today" — because a coloured
            # dot on its own is decoration.
            f'<span title="{E(it.get("description") or "")}'
            f'{" — granted to this agent in this thread" if it.get("new") else ""}" '
            f'style="font-size:11px;border-radius:10px;padding:2px 8px;white-space:nowrap;'
            + ('background:color-mix(in srgb,var(--color-accent) 16%,transparent);'
               'box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--color-accent) 40%,transparent)"'
               if it.get("new") else
               'background:var(--text-6)"')
            + f'>{E(it.get("name") or it.get("id",""))}'
            + ('<span style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;'
               'margin-left:5px;color:var(--color-accent);font-weight:600">new</span>'
               if it.get("new") else "")
            + '</span>'
            for it in items)
        rows += (f'<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:9px">'
                 f'<span title="{_CAP_KIND_LABEL.get(kind, kind)}" style="display:flex;color:var(--text-muted);flex:none;margin-top:2px">'
                 f'{_icon(_CAP_ICON[kind], 14)}</span>'
                 f'<div style="display:flex;flex-wrap:wrap;gap:4px">{chips}</div></div>')
    if not rows:
        rows = ('<div style="font-size:11.5px;color:var(--text-faint);line-height:1.5">'
                'Connectors, skills and plugins the agent uses in this thread will appear here.</div>')
    return (f'<div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--color-divider)">'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;'
            f'color:var(--text-muted);margin-bottom:10px">Capabilities used in this thread</div>'
            f'{rows}</div>')


def _thread_artifacts(agent_dir, aid: str, thread: str, msgs: list) -> tuple[list, list]:
    """Split a thread's artifacts into INPUTS (what the owner attached) and OUTPUTS (files the agent
    wrote/edited this thread). Inputs come off user turns' `attachments`, outputs off assistant turns'
    `outputs`. Both are de-duplicated; outputs note whether the file still exists on disk."""
    inputs, outputs, seen_in, seen_out = [], [], set(), set()
    for m in msgs:
        role = m.get("role")
        if role == "user":
            for att in (m.get("attachments") or []):
                key = (att.get("kind"), att.get("file") or att.get("name"))
                if key in seen_in:
                    continue
                seen_in.add(key)
                it = dict(att)
                if att.get("kind") == "image" and att.get("file"):
                    it["url"] = (f'/thread-file?agent={E(aid)}&thread={E(thread)}&name={E(str(att["file"]))}')
                inputs.append(it)
        elif role == "assistant":
            for out in (m.get("outputs") or []):
                p = out.get("path") or ""
                if not p or p in seen_out:
                    continue
                seen_out.add(p)
                it = dict(out)
                try:
                    it["exists"] = bool(p) and Path(p).is_file()
                except Exception:  # noqa
                    log.debug('_thread_artifacts: failed; using a default', exc_info=True)
                    it["exists"] = False
                outputs.append(it)
    return inputs, outputs


def _art_chip(label: str, title: str, *, reveal: str = "", lightbox: str = "",
              icon: str = "file", dim: bool = False) -> str:
    """One artifact chip (type icon + filename). `reveal` (an absolute path) or `lightbox` (a URL) is
    stashed in a data- attribute and handled by a delegated click listener in chat.js — NOT inlined
    into onclick, so Windows backslashes in the path can't corrupt the JS string."""
    op = ";opacity:.5" if dim else ""
    click = bool(reveal or lightbox)
    cur = ";cursor:pointer" if click else ""
    data = (f' data-reveal="{E(reveal)}"' if reveal else "") + (f' data-lightbox="{E(lightbox)}"' if lightbox else "")
    return (f'<span title="{E(title)}"{data} style="display:inline-flex;align-items:center;gap:6px;max-width:100%;'
            f'font-size:11px;background:var(--text-6);border-radius:10px;'
            f'padding:3px 9px{cur}{op}">'
            f'<span style="display:flex;flex:none;color:var(--text-muted)">{_icon(icon, 13)}</span>'
            f'<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{E(label)}</span></span>')


def _thread_arts_rail(inputs: list, outputs: list, agent_id: str = "") -> str:
    """The 'Artifacts' rail block: Input artifacts (owner attachments) + Output artifacts (agent files).
    Always rendered — shows a placeholder until files are attached or created in the thread."""
    def _sub(title: str, chips: str, kind: str = "") -> str:
        if not chips:
            return ""
        head = E(title)
        if kind and agent_id:
            # The heading is the way through to the full list: same two filters already applied,
            # so "show me everything like this" doesn't mean re-selecting them by hand.
            import urllib.parse as _up
            href = f"/artefacts?owner={_up.quote(agent_id, safe='')}&type={kind}"
            head = (f'<a href="{href}" title="See all {E(title.lower())} from this agent" '
                    f'style="color:inherit;text-decoration:none;display:inline-flex;align-items:center;'
                    f'gap:4px" onmouseover="this.style.color=\'var(--color-accent)\'" '
                    f'onmouseout="this.style.color=\'inherit\'">{E(title)}'
                    f'<span style="display:inline-flex;opacity:.6">{_icon("link",12)}</span></a>')
        return (f'<div style="margin-bottom:11px">'
                f'<div style="font-size:11px;color:var(--text-soft);margin-bottom:6px">{head}</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:5px">{chips}</div></div>')
    in_chips = "".join(
        _art_chip(it.get("name") or it.get("file") or "file", it.get("name") or "",
                  lightbox=it.get("url", ""),
                  icon=_file_icon(it.get("name") or it.get("file") or ""))
        for it in inputs)
    out_chips = ""
    for it in outputs:
        p = it.get("path", "")
        exists = it.get("exists")
        tt = (p if exists else (p + "  (no longer on disk)"))
        out_chips += _art_chip(it.get("name") or "file", tt,
                               reveal=(p if exists else ""),
                               icon=_file_icon(it.get("name") or ""), dim=not exists)
    body = _sub("Input artifacts", in_chips, "input") + _sub("Output artifacts", out_chips, "output")
    if not body:
        body = ('<div style="font-size:11.5px;color:var(--text-faint);line-height:1.5">'
                'Files you attach or the agent creates in this thread will appear here.</div>')
    return (f'<div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--color-divider)">'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;'
            f'color:var(--text-muted);margin-bottom:10px">Artifacts</div>'
            f'{body}</div>')


def _thread_rail(realm_root, a, selected: str) -> str:
    """The right rail for a thread: loaded-context breakdown + capabilities used + artifacts. Factored
    out of _tab_threads so it can be refetched on its own after a reply (new outputs appear without a
    full reload). Carries id='mc-rail' so chat.js can swap it in place."""
    from ..threads import Thread
    agent_dir = Path(realm_root) / "agents" / a.id
    th = Thread(agent_dir, selected)
    agent_json = json.loads((agent_dir / "agent.json").read_text(encoding="utf-8-sig")) if (agent_dir / "agent.json").exists() else {}
    bd = memory.core_breakdown(realm_root, agent_dir, agent_json)
    thread_chars = len(th.render())
    items = [("Mission, soul & tenets", bd.get("mission", 0), "var(--color-accent)"),
             ("Agent's goals", bd.get("goals", 0), "var(--color-accent-2)"),
             ("Realm memory", bd.get("realm_memory", 0), "var(--color-sand-500)"),
             (f"{_poss(a.display)} memory", bd.get("agent_memory", 0), "var(--color-sand-300)"),
             ("Thread context", thread_chars, "var(--text-ghost)")]
    total = sum(c for _, c, _ in items) or 1
    bar = "".join(f'<i style="width:{max(2, round(100*c/total))}%;background:{col};height:8px;display:inline-block"></i>'
                  for _, c, col in items if c > 0)
    cards = ""
    for name, c, col in items:
        if c <= 0:
            continue
        cards += (f'<div style="display:flex;gap:8px;align-items:baseline;margin-bottom:8px">'
                  f'<i style="width:9px;height:9px;background:{col};flex:none;border-radius:2px;position:relative;top:2px"></i>'
                  f'<div style="flex:1"><div style="font-size:12px">{E(name)}</div></div>'
                  f'<div class="mono" style="font-size:11px;color:var(--text-muted)">{_est_tokens(c)}</div></div>')
    _allmsgs = th._messages()
    caps_block = _thread_caps_rail(_thread_caps_used(_allmsgs, realm_root, a.id, selected))
    _ins, _outs = _thread_artifacts(agent_dir, a.id, selected, _allmsgs)
    arts_block = _thread_arts_rail(_ins, _outs, a.id)
    return (f'<div id="mc-rail" data-agent="{E(a.id)}" data-thread="{E(selected)}" '
            f'style="background:var(--color-surface);padding:16px 18px;overflow:auto">'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--text-muted);margin-bottom:8px">'
            f'Loaded context · {_est_tokens(total)} tokens</div>'
            f'<div style="display:flex;border-radius:3px;overflow:hidden;margin-bottom:12px">{bar}</div>{cards}'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:8px;line-height:1.5">'
            f'≈ <b>{_est_tokens(total)}</b> tokens this reply. Core context is always present; the thread compacts as it grows.</div>'
            f'{caps_block}{arts_block}</div>')


def _render_turns(realm_root, a, selected: str) -> str:
    """Render just the transcript turns for a thread (server-canonical Markdown, icons, segments).
    Shared by _chat_center and the /api/thread-turns refresh endpoint, so the live view after a
    reply becomes identical to a reloaded page (no client/server rendering drift)."""
    from ..threads import Thread
    agent_dir = Path(realm_root) / "agents" / a.id
    th = Thread(agent_dir, selected)
    msgs = th._messages()
    summ = th.summary()
    av = _portrait(realm_root, a, 28)
    userav = _user_avatar(realm_root, 28)
    turns = ""
    if summ:
        turns += (f'<div class="mc-frame" style="align-self:center;background:var(--color-surface);border-radius:var(--r);'
                  f'padding:6px 12px;font-size:11.5px;color:var(--text-dim);margin:0 auto 6px">'
                  f'📚 Earlier in this thread — compacted</div>')
    last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=-1)
    for i, m in enumerate(msgs):
        if m.get("role") == "event" or m.get("kind") == "event":
            turns += _event_card(m)
            continue
        turns += _turn(m.get("role", ""), m.get("content", ""), str(m.get("ts", "")),
                       i, i == last_user, a.id, selected, a.display, a.is_coordinator,
                       av=av, userav=userav, seg=m.get("segments"), att=m.get("attachments"))
    # An owner message with nothing after it. Either the agent is working on it right now — in
    # which case the page has to say so, because the reply is arriving over an event stream this
    # page load knows nothing about — or the run died without answering, and saying that is far
    # better than a message sitting there looking ignored.
    if th.open_turn() is not None:
        if _chat_running(realm_root, a.id, selected):
            turns += _working_turn(av, a.display)
        else:
            turns += _unanswered_turn(av, a.display)
    if not msgs and not summ:
        turns = ('<div style="color:var(--text-muted);font-size:13px;padding:20px 0">'
                 'No messages yet. Say hello below — the reply is generated with this agent\'s core context + this thread.</div>')
    return turns


def _working_turn(av: str, disp: str) -> str:
    """The agent is working on the message above, right now.

    Rendered server-side, which is the whole point: the live reply streams over an SSE connection
    belonging to the tab that sent the message. Come back to the thread in a new page load and
    that connection isn't yours — without this the transcript looks like nothing is happening.
    mcRefreshTurns replaces it with the real reply when the turn lands.
    """
    return (f'<div class="mc-turn mc-pending" data-role="pending" style="margin-bottom:12px">'
            f'<div style="display:flex;gap:10px"><div style="display:flex;flex:none">{av}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">{E(disp)}</div>'
            f'<div style="display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--text-muted)">'
            f'<span class="mc-dots"><i></i><i></i><i></i></span>working on it…</div></div></div></div>'
            '<style>.mc-dots{display:inline-flex;gap:3px;align-items:center}'
            '.mc-dots i{width:5px;height:5px;border-radius:50%;background:var(--color-accent-2);'
            'display:block;animation:mc-dots 1.1s ease-in-out infinite}'
            '.mc-dots i:nth-child(2){animation-delay:.16s}.mc-dots i:nth-child(3){animation-delay:.32s}'
            '@keyframes mc-dots{0%,80%,100%{opacity:.25}40%{opacity:1}}'
            '@media (prefers-reduced-motion:reduce){.mc-dots i{animation:none;opacity:.6}}</style>')


def _unanswered_turn(av: str, disp: str) -> str:
    """The message above never got a reply and nothing is working on it.

    Reachable when the app was closed or the server stopped mid-turn — the run can't write its
    own failure if it isn't there any more. Says so plainly rather than leaving the message
    looking ignored, and points at the one thing that fixes it.
    """
    return (f'<div class="mc-turn" data-role="pending" style="margin-bottom:12px">'
            f'<div style="display:flex;gap:10px"><div style="display:flex;flex:none;opacity:.6">{av}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">{E(disp)}</div>'
            f'<div style="font-size:12.5px;color:var(--text-muted);line-height:1.5">'
            f'No reply — the run stopped before it answered, most likely because the app was '
            f'closed mid-turn. Send it again when you want an answer.</div></div></div></div>')


def _chat_center(realm_root, a, selected: str, embed: bool = False, lead: str = "") -> str:
    """The center chat column: transcript + composer. Shared by the Threads tab and the
    dashboard thread widget (embedded via iframe) so both use the exact same chat UI/UX.
    In embed mode the header line is dropped — the widget box header carries that info.
    `lead` prepends HTML (e.g. an avatar + status dot) inside the header, before the title."""
    from ..threads import Thread
    agent_dir = Path(realm_root) / "agents" / a.id
    th = Thread(agent_dir, selected)
    msgs = th._messages()
    summ = th.summary()
    av = _portrait(realm_root, a, 28)       # for the optimistic-turn <template> that chat.js clones
    userav = _user_avatar(realm_root, 28)
    turns = _render_turns(realm_root, a, selected)
    # display title matches the side pane (capitalised / custom-renamed), not the raw slug
    _title = E(selected)
    if not embed:
        try:
            _, _tmeta = _ordered_threads(agent_dir)
            _title = E(_thread_title(_tmeta, selected))
        except Exception:  # noqa
            swallowed(log, '_chat_center: failed; using a default')
            _title = E(selected)
    # how full the live history is toward the next auto-compaction. The threshold is derived from the
    # agent model's real context window (Opus/Haiku 200K tokens, Sonnet 5 / Fable 1M) — the same value
    # threads.compact_if_needed uses — so the % is grounded in Claude's actual limits, not a guess.
    _mlabel = _agent_model_label(realm_root, a.id)
    _thr = max(1, model.compaction_threshold_chars(_mlabel))
    _pct = min(100, round(100 * len(th.render()) / _thr))          # always shown, even with no messages
    _cw = model.context_window_tokens(_mlabel)
    _comp_title = (f"History uses ~{_est_tokens(len(th.render()))} of the model's {_cw//1000}K-token "
                   f"context window. At 100% the oldest turns are summarised to keep the thread lean.")
    _comp_col = "var(--status-bad)" if _pct >= 90 else ("var(--status-warn)" if _pct >= 70 else "var(--color-accent-2)")
    _comp_bar = (f'<span style="display:inline-block;width:74px;height:5px;border-radius:3px;'
                 f'background:var(--color-neutral-200);overflow:hidden;vertical-align:middle">'
                 f'<span style="display:block;width:{_pct}%;height:100%;background:{_comp_col}"></span></span>')
    _comp = (f' · <span title="{_comp_title}" style="display:inline-flex;align-items:center;gap:6px">'
             f'{_pct}% to compaction {_comp_bar}</span>')
    header = "" if embed else (
        f'<div style="padding:12px 20px 6px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--color-divider)">'
        f'{lead}'
        f'<span id="mc-cttitle" ondblclick="mcThreadInlineRename(this,{_J(a.id)},{_J(selected)})" title="Double-click to rename" '
        f'style="display:inline-block;max-width:100%;min-width:0;font-family:var(--font-heading);font-weight:600;font-size:17px;'
        f'cursor:text;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_title}</span>'
        f'<span style="font-size:11px;color:var(--text-muted);white-space:nowrap">'
        f'{"main thread" if selected=="main" else "sub-thread"} · {sum(1 for _m in msgs if _m.get("role") in ("user","assistant"))} messages{" · compacted" if summ else ""}{_comp}</span>'
        + f'</div>')
    return (f'<div style="position:relative;display:flex;flex-direction:column;min-height:0;height:100%">'
            f'{header}<template class="mc-av">{av}</template><template class="mc-userav">{userav}</template>'
            f'<div style="position:relative;flex:1;min-height:0">'
            f'<div id="mc-turns" class="mc-scroll" data-agent="{E(a.id)}" data-thread="{E(selected)}" data-display="{E(a.display)}" '
            f'data-coord="{"1" if a.is_coordinator else ""}" data-comp-pct="{_pct}" data-activity="{_agent_activity(realm_root, a.id)}" '
            f'style="height:100%;overflow:auto;padding:16px 20px 160px;display:flex;flex-direction:column">{turns}</div>'
            # composer floats over the transcript; a gradient fades messages out beneath it (Claude-style).
            # right inset clears the 8px scroll gutter so the scrollbar stays fully visible (not hidden by the fade)
            f'<div style="position:absolute;left:0;right:10px;bottom:0;pointer-events:none">'
            f'<div style="height:38px;background:linear-gradient(to bottom, transparent, var(--color-bg))"></div>'
            f'<div style="background:var(--color-bg);pointer-events:auto;padding:0 20px 14px">'
            f'<div class="mc-frame" style="display:flex;flex-direction:column;gap:6px;'
            f'border-radius:22px;padding:6px 8px 6px 10px;box-shadow:var(--shadow-sm)">'
            f'<div id="mc-attach" style="display:none;flex-wrap:wrap;gap:6px;padding:2px 2px 0"></div>'
            # single horizontal row: [+]  [textarea grows]  [↵ / Stop] — matches Claude
            f'<div style="display:flex;align-items:flex-end;gap:6px">'
            f'<div style="position:relative;flex:none">'
            f'<button id="mc-plus" title="Add" onclick="mcPlusMenu(event)" style="border:0;background:transparent;'
            f'cursor:pointer;width:30px;height:30px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
            f'color:var(--text-dim)">{_icon("plus",18)}</button>'
            f'<div id="mc-plusmenu" style="display:none;position:absolute;bottom:40px;left:0;z-index:40;min-width:210px;background:var(--color-bg);'
            f'border:1px solid var(--color-divider);border-radius:var(--r);box-shadow:var(--shadow-md);padding:5px">'
            f'<a onclick="document.getElementById(\'mc-file\').click();mcPlusClose()" style="display:flex;align-items:center;gap:9px;padding:7px 10px;cursor:pointer;font-size:13px;border-radius:var(--r)">'
            f'<span style="display:flex;color:var(--text-dim)">{_icon("image",15)}</span><span style="flex:1">Add files or photos</span>'
            f'<span style="font-size:10.5px;color:var(--text-ghost)">Ctrl U</span></a>'
            f'</div><input type="file" id="mc-file" multiple style="display:none" onchange="mcAddFiles(this)"></div>'
            f'<textarea id="mc-msg" rows="1" spellcheck="true" lang="en" autocapitalize="sentences" placeholder="Ask {E(a.display)} in the {E(selected)} thread…" '
            f'style="flex:1;border:0;outline:0;background:transparent;resize:none;font:inherit;font-size:15px;line-height:1.5;'
            f'color:var(--color-text);min-height:30px;max-height:260px;overflow-y:hidden;padding:4px 0;transition:height .12s ease"></textarea>'
            f'<button id="mc-send" title="Send" style="flex:none;display:none;border:0;background:transparent;cursor:pointer;'
            f'width:30px;height:30px;border-radius:8px;align-items:center;justify-content:center;'
            f'color:var(--text-muted)" '
            f'onclick="mcChat({_J(a.id)},{_J(selected)})">'
            f'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="9 10 4 15 9 20"/><path d="M20 4v7a4 4 0 0 1-4 4H4"/></svg></button>'
            f'<button id="mc-stop" title="Stop" style="display:none;flex:none;border:1px solid var(--color-divider);background:transparent;'
            f'cursor:pointer;font-size:13px;padding:7px 14px;border-radius:10px;align-items:center;gap:6px;color:var(--color-text)" '
            f'onclick="mcStop()">{_icon("square",14)}Stop</button></div></div>'
            f'<div id="mc-chatmsg" style="font-size:11px;color:var(--text-muted);margin-top:4px"></div></div></div></div></div>')


def _tab_threads(realm, realm_root, a, selected: str = None) -> str:
    from ..threads import Thread
    agent_dir = realm_root / "agents" / a.id
    names, meta = _ordered_threads(agent_dir)
    if not selected:                       # no ?thread= → reopen the last thread the owner viewed
        selected = meta.get("last") or "main"
    if selected not in names:
        selected = "main"
    _touch_last_thread(agent_dir, selected)
    _clear_thread_unread(agent_dir, selected, meta)   # opening a thread marks its new output as seen

    # left list — pin/unread/rename + drag-to-reorder
    def menu_item(action, slug, icon, label, key):
        return (f'<a onclick="mcThreadAction(event,{_J(a.id)},{_J(slug)},\'{action}\')" '
                f'style="display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12.5px;cursor:pointer;color:inherit;text-decoration:none">'
                f'<span style="display:flex;color:var(--text-dim)">{_icon(icon,14)}</span>'
                f'<span style="flex:1">{label}</span>'
                f'<span style="font-size:10px;color:var(--text-ghost)">{key}</span></a>')
    left_rows = ""
    for n in names:
        th = Thread(agent_dir, n)
        msgs = th._messages()
        sub = E(msgs[-1]["content"][:40]) if msgs else "empty"
        is_main = n == "main"
        pinned = bool(meta.get("pinned", {}).get(n)) or is_main
        unread = bool(meta.get("unread", {}).get(n))
        title = _thread_title(meta, n)
        selcss = ("background:var(--color-accent-100);border-left:2px solid var(--color-accent)"
                  if n == selected else "border-left:2px solid transparent")
        dot = ('<span style="width:7px;height:7px;border-radius:50%;background:var(--color-accent);flex:none"></span>'
               if unread else '')
        pinmark = (f'<span title="Pinned" style="display:flex;color:var(--text-ghost)">{_icon("pin",11)}</span>'
                   if pinned and not is_main else '')
        grip = ('' if is_main else
                f'<span class="mc-thgrip" style="display:flex;cursor:grab;color:var(--text-35);opacity:0;transition:opacity .12s">{_icon("grip-vertical",13)}</span>')
        # 3-dots menu
        items = ""
        if not is_main:
            items += menu_item("unpin" if pinned else "pin", n, "pin-off" if pinned else "pin", "Unpin" if pinned else "Pin", "P")
        items += menu_item("read" if unread else "unread", n, "mail-open" if unread else "mail",
                           "Mark as read" if unread else "Mark as unread", "U")
        items += (f'<a onclick="mcThreadRename(event,{_J(a.id)},{_J(n)},{_J(title)})" '
                  f'style="display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12.5px;cursor:pointer;color:inherit;text-decoration:none">'
                  f'<span style="display:flex;color:var(--text-dim)">{_icon("square-pen",14)}</span>'
                  f'<span style="flex:1">Rename</span><span style="font-size:10px;color:var(--text-ghost)">R</span></a>')
        if not is_main:
            items += menu_item("archive", n, "archive", "Archive", "A")
            items += ('<div style="height:1px;background:var(--color-divider);margin:4px 6px"></div>'
                      f'<a onclick="mcThreadDelete(event,{_J(a.id)},{_J(n)},{_J(title)})" '
                      f'style="display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12.5px;cursor:pointer;color:var(--status-bad);text-decoration:none">'
                      f'<span style="display:flex">{_icon("trash",14)}</span>'
                      f'<span style="flex:1">Delete</span></a>')
        menu = (f'<div class="mc-thmenu" style="display:none;position:absolute;top:30px;right:8px;z-index:30;min-width:170px;'
                f'background:var(--color-bg);border:1px solid var(--color-divider);border-radius:var(--r);box-shadow:var(--shadow-md);padding:4px">{items}</div>')
        dots = (f'<button class="mc-thdots" onclick="mcThreadMenu(event,this)" title="Thread options" '
                f'style="border:0;background:transparent;cursor:pointer;padding:3px;border-radius:var(--r);display:flex;'
                f'color:var(--text-soft);opacity:0;transition:opacity .12s">{_icon("ellipsis-vertical",15)}</button>')
        left_rows += (
            f'<div class="mc-thread" data-slug="{E(n)}" draggable="{"false" if is_main else "true"}" '
            f'style="position:relative;display:flex;align-items:center;gap:6px;padding:8px 8px 8px 8px;{selcss}">'
            f'{grip}{dot}'
            f'<div onclick="location.href=\'/agent/{E(a.id)}/threads?thread={E(n)}\'" style="flex:1;min-width:0;cursor:pointer">'
            f'<div style="display:flex;align-items:center;gap:5px;font-family:var(--font-body);'
            f'font-weight:{"700" if (is_main or unread) else "500"};font-size:13px">'
            f'<span class="mc-thtitle" onclick="mcThTitleClick(event,this,{_J(a.id)},{_J(n)})" ondblclick="mcThTitleDbl(event,this,{_J(a.id)},{_J(n)})" '
            f'title="Double-click to rename" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{E(title)}</span>{pinmark}</div>'
            f'<div style="font-size:11px;color:var(--text-muted);'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{sub}</div></div>'
            f'{dots}{menu}</div>')
    # archived threads → the modal opened by the always-visible "Archived" button
    archived_meta = meta.get("archived", {})

    def _fmt_arch(d):
        try:
            return datetime.date.fromisoformat(str(d)).strftime("%d %b %Y")
        except (ValueError, TypeError):
            return str(d or "")
    arch_rows = ""
    for aslug, adate in sorted(archived_meta.items(), key=lambda kv: str(kv[1]), reverse=True):
        at = E(_thread_title(meta, aslug))
        arch_rows += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:9px 4px;border-bottom:1px solid var(--color-divider)">'
            f'<div style="flex:1;min-width:0"><div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{at}</div>'
            f'<div style="font-size:11px;color:var(--text-soft)">Archived {E(_fmt_arch(adate))}</div></div>'
            f'<button onclick="mcThreadAction(event,{_J(a.id)},{_J(aslug)},\'unarchive\')" class="btn btn-secondary" '
            f'style="font-size:12px;padding:4px 10px;display:inline-flex;align-items:center;gap:5px">{_icon("archive-restore",13)}Revive</button>'
            f'<button onclick="mcThreadDelete(event,{_J(a.id)},{_J(aslug)},\'{at}\')" title="Delete permanently" '
            f'style="border:0;background:transparent;cursor:pointer;color:var(--status-bad);display:inline-flex;padding:5px;border-radius:var(--r)">{_icon("trash",15)}</button></div>')
    if not arch_rows:
        arch_rows = '<div style="padding:18px 4px;font-size:12.5px;color:var(--text-muted)">No archived threads yet. Archive one from its ⋮ menu.</div>'
    arch_modal = (
        f'<div id="mc-tharch-modal" class="mc-modal-ov-top" style="z-index:250;padding:56px 16px;overflow:auto" '
        f'onclick="if(event.target===this)mcArchClose()">'
        f'<div class="mc-modal-box" style="width:min(520px,94vw)">'
        f'<div style="display:flex;align-items:center;margin-bottom:6px"><div style="font-family:var(--font-heading);font-weight:600;font-size:16px">Archived threads</div>'
        f'<button class="btn btn-secondary" style="margin-left:auto;font-size:12px;padding:4px 10px" onclick="mcArchClose()">Close</button></div>'
        f'<div style="max-height:60vh;overflow:auto">{arch_rows}</div></div></div>')
    hint = ('<div style="padding:8px 14px;font-size:11px;color:var(--text-soft)">'
            'Sub-threads scope memory — a "taxes" thread doesn\'t load trading context.</div>')
    arch_btn = (f'<button onclick="mcArchOpen()" title="View archived threads" style="width:100%;display:flex;align-items:center;gap:8px;'
                f'border:0;border-top:1px solid var(--color-divider);background:transparent;cursor:pointer;padding:10px 14px;font-size:12px;'
                f'color:var(--text-62)">'
                f'{_icon("archive",14)}<span style="flex:1;text-align:left">Archived</span>'
                f'<span style="font-size:11px;color:var(--text-faint)">{len(archived_meta)}</span></button>')
    left = (f'<div style="background:var(--color-surface);display:flex;flex-direction:column;min-height:0">'
            f'<div style="display:flex;align-items:center;padding:10px 14px 6px"><span style="font-size:10px;text-transform:uppercase;'
            f'letter-spacing:.1em;color:var(--text-muted)">Threads</span>'
            f'<a style="margin-left:auto;color:var(--color-accent);cursor:pointer;display:flex" title="New thread" aria-label="New thread" onclick="mcNewThread({_J(a.id)})">{_icon("chat-new-line",16)}</a></div>'
            f'<div id="mc-threadlist" data-agent="{E(a.id)}" data-selected="{E(selected)}" '
            f'data-selunread="{"1" if meta.get("unread",{}).get(selected) else ""}" style="overflow:auto">{left_rows}</div>'
            f'<div style="margin-top:auto">{hint}{arch_btn}</div>{arch_modal}</div>{_THREADLIST_JS}')

    # center transcript + composer (shared helper)
    th = Thread(agent_dir, selected)
    msgs = th._messages()
    summ = th.summary()
    center = _chat_center(realm_root, a, selected)

    # right rail — loaded context + capabilities + artifacts (refetched live after each reply)
    rail = _thread_rail(realm_root, a, selected)

    return (f'<div id="mc-thgrid" style="display:grid;grid-template-columns:var(--mc-thleft,220px) 5px 1fr 300px;height:100%;min-height:0">'
            f'{left}'
            f'<div class="mc-thresize" onmousedown="mcThResizeStart(event)" title="Drag to resize the thread list"></div>'
            f'{center}{rail}</div>{_THRESIZE_JS}')
