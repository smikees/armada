"""Shared agent/realm page helpers (Phase 3 split of agentpages): job cards, artefact gathering, autonomy/colour controls, filter dropdowns and the status-filter palette."""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import clock
from .. import goals as goalsmod
from ..icons import ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR, _ICON_REFRESH
from ._base import (E, _J, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _mini_pill, _poss)
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _ordinal, _next_hint, _fmt_ts)
from .agentbits import _filter_dropdown  # noqa: F401 — re-exported; lives lower down so capabilities can use it too
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _jobs_cell, _has_pending_proposals, _health_swatch, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta,
    _running_jobs, _job_prompt, _job_created, _job_created_ts,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)
from .threadsview import (_agent_model_label, _chat_center, _ordered_threads, _sub, _tab_threads,
    _thread_title, _user_avatar, _user_avatar_file, _mark_thread_unread, _clear_thread_unread)
from .widgets import (_RUNNING_COLOR, _UNSCHEDULED_COLOR, _HEALTH_STYLES, _health_legend_chips, _jobcal)
from .goalsview import _tab_goals
from .memoryview import _tab_memory, _agent_memory, _list_mem
from .capabilities import (_tab_skills, _agent_toolkit, _realm_toolkit, _cap_manage_btn,
    _tool_group, _tool_row, _toolkit_from)
from ..assets import (AGENT_COLOR_JS as _AGENT_COLOR_JS, APPOINT_JS as _APPOINT_JS,
    ARTEFACTS_JS as _ARTEFACTS_JS, AUTONOMY_JS as _AUTONOMY_JS, FDROP_JS as _FDROP_JS,
    JOB_PROPOSAL_JS as _JOB_PROPOSAL_JS, JOBCAL_JS as _JOBCAL_JS, JOBS_FILTER_JS as _JOBS_FILTER_JS,
    JOBS_SORT_JS as _JOBS_SORT_JS, NEW_JS as _NEW_JS, TABLE_SORT_JS as _TABLE_SORT_JS)
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


# _running_jobs / _job_prompt / _job_created / _job_created_ts moved to agentbits, which the
# Register widget can reach and this module cannot be reached from. Imported above and re-exported
# here so every existing call site is unchanged.


def _realm_cfg_value(realm_root, key: str, fallback: str = "") -> str:
    try:
        d = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
        return str((d.get(key) if isinstance(d, dict) else "") or fallback)
    except Exception:  # noqa — no realm.json / bad JSON just means "no default to name"
        swallowed(log, '_realm_cfg_value: failed; returning a fallback')
        return fallback


def _inherit_label(current: str) -> str:
    """'inherit realm default (high)' rather than a bare 'inherit'.

    Naming what you'd actually get means the option isn't a blank cheque — you can see the effect
    of leaving it alone without opening Realm settings to find out."""
    v = str(current or "").strip()
    return f"inherit realm default ({v})" if v else "inherit realm default"


def _effort_options(realm_root, selected: str = "", inherit: bool = False) -> str:
    """<option>s for an effort <select>. `inherit` adds the leading blank option, labelled with
    the realm's own default so every inherit dropdown on the page reads the same way."""
    html = (f'<option value="" {"selected" if not selected else ""}>'
            f'{E(_inherit_label(_realm_cfg_value(realm_root, "default_effort", "high")))}</option>'
            if inherit else "")
    return html + "".join(
        f'<option {"selected" if e == selected else ""}>{E(e)}</option>' for e in _EFFORTS)


def _model_options(realm_root, selected: str = "", inherit: bool = False) -> str:
    """<option>s for a model <select>, driven by the synced catalog (value=id, text=display name,
    newest-first). Preserves a stored value no longer offered (e.g. a retired model) so an agent or
    realm keeps its pick; `inherit` adds the leading 'inherit (realm default)' blank option."""
    opts = models.options(realm_root)
    ids = {mid for mid, _ in opts}
    dflt = _realm_cfg_value(realm_root, "default_model")
    dlab = next((lab for mid, lab in opts if mid == dflt), "") or (
        _pretty_model(dflt) if dflt.startswith("claude-") else dflt)
    html = f'<option value="">{E(_inherit_label(dlab))}</option>' if inherit else ""
    if selected and selected not in ids:
        lab = _pretty_model(selected) if selected.startswith("claude-") else selected
        html += f'<option value="{E(selected)}" selected>{E(lab)}</option>'
    for mid, lab in opts:
        html += f'<option value="{E(mid)}"{" selected" if mid == selected else ""}>{E(lab)}</option>'
    return html


_AGENT_PALETTE = ["#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99", "#e31a1c",
                  "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a", "#ffff99", "#b15928"]


def _agent_color_control(current: str, field_id: str) -> str:
    """Preset swatches (the graph palette) + a custom colour picker, writing to a hidden field."""
    cur = (current or _AGENT_PALETTE[0]).strip()
    ring = lambda on: f'0 0 0 2px {"var(--color-text)" if on else "transparent"},0 0 0 4px var(--color-bg)'
    sw = "".join(
        f'<span class="mc-color-sw" data-c="{c}" data-fid="{field_id}" onclick="mcPickColor(this)" title="{c}" '
        f'style="width:22px;height:22px;border-radius:50%;cursor:pointer;flex:none;background:{c};'
        f'box-shadow:{ring(c.lower() == cur.lower())}"></span>' for c in _AGENT_PALETTE)
    pick = cur if cur.startswith("#") else _AGENT_PALETTE[0]
    is_custom = cur.lower() not in [c.lower() for c in _AGENT_PALETTE]   # a non-preset (custom) colour
    circ_border = f'2px solid {cur}' if is_custom else '2px dashed var(--color-divider)'
    circ_bg = cur if is_custom else 'transparent'
    # The native colour input is overlaid invisibly ON the button (not display:none) so the browser
    # anchors its picker popup to the button — display:none anchors it at the window's top-left.
    return (f'<input type="hidden" id="{field_id}" value="{E(cur)}">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">{sw}'
            f'<span style="display:inline-flex;align-items:center;gap:8px;margin-left:14px">'
            f'<span id="{field_id}-circle" title="Custom colour" style="width:22px;height:22px;border-radius:50%;'
            f'flex:none;box-sizing:border-box;border:{circ_border};background:{circ_bg}"></span>'
            f'<span style="position:relative;display:inline-flex">'
            f'<button type="button" class="btn btn-secondary" style="font-size:12px;padding:5px 11px" '
            f'onclick="document.getElementById(\'{field_id}-pick\').click()">Pick a custom colour</button>'
            f'<input type="color" id="{field_id}-pick" value="{E(pick)}" '
            f'oninput="mcColorCustom(\'{field_id}\',this.value)" onchange="mcColorCustom(\'{field_id}\',this.value)" '
            f'style="position:absolute;inset:0;width:100%;height:100%;opacity:0;border:0;padding:0;margin:0;pointer-events:none">'
            f'</span></span></div>')




def _job_proposals_block(realm, realm_root, only_agent: str = "") -> str:
    """A highlighted 'Proposed jobs' panel listing agent-authored proposals awaiting approval.
    Used on both the realm Jobs section (all agents) and an agent's own Jobs tab (only_agent)."""
    from .. import jobs as jobs_mod
    disp = {a.id: a.display for a in realm.agents}
    items = []
    for aid, slug, job, _path in jobs_mod.iter_pending(realm_root):
        if only_agent and aid != only_agent:
            continue
        ok, errs, norm = jobs_mod.validate(job)
        items.append((aid, slug, norm, ok, errs))
    if not items:
        return ""
    cards = ""
    for aid, slug, job, ok, errs in items:
        kind = job.get("kind", "agent")
        sched = job.get("cron") or job.get("schedule") or "manual"
        _r = job.get("run")
        _r = " ".join(str(x) for x in _r) if isinstance(_r, list) else _r
        preview = E((job.get("prompt") or _r or "")[:600])
        kbadge = ('<span class="tag mc-frame" style="font-size:9.5px;padding:0 5px;margin-left:2px">cmd</span>'
                  if kind == "command" else "")
        owner = "" if only_agent else (f'<span style="font-size:11.5px;color:var(--text-muted)">'
                                       f'proposed by {E(disp.get(aid, aid))}</span>')
        errhtml = (f'<div style="color:var(--status-bad);font-size:11.5px;margin-top:6px">⚠ {E("; ".join(errs))}</div>'
                   if errs else "")
        approve = (f'<button class="btn btn-primary" style="color:#fff;font-size:12px;padding:5px 11px"'
                   f'{"" if ok else " disabled title=\"fix the errors above first\""} '
                   f'onclick="mcJobProposal({_J(aid)},{_J(slug)},\'approve\',this)">Approve</button>')
        cards += (f'<div class="mc-prop mc-frame" style="border-radius:var(--r);padding:12px 14px;margin-bottom:10px">'
                  f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
                  f'<span style="font-family:var(--font-heading);font-weight:600;font-size:14px">{E(job.get("name") or slug)}</span>{kbadge}'
                  f'{owner}<span class="mono" style="font-size:11px;margin-left:auto;'
                  f'color:var(--text-dim)">{E(_humanize(sched))}</span></div>'
                  f'<pre style="white-space:pre-wrap;background:var(--color-sand-100);border:1px solid var(--color-sand-300);'
                  f'border-radius:var(--r);padding:9px 11px;margin:8px 0 0;font-size:11.5px;max-height:160px;overflow:auto">{preview}</pre>'
                  f'{errhtml}'
                  f'<div style="display:flex;gap:8px;margin-top:10px;align-items:center">{approve}'
                  f'<button class="btn btn-secondary" style="font-size:12px;padding:5px 11px" '
                  f'onclick="mcJobProposal({_J(aid)},{_J(slug)},\'reject\',this)">Reject</button>'
                  f'<span class="mc-propmsg" style="font-size:12px;color:var(--text-muted)"></span>'
                  f'</div></div>')
    n = len(items)
    head = (f'<div style="display:flex;align-items:center;gap:8px;margin:0 0 10px">'
            f'<span style="font-family:var(--font-heading);font-weight:600;font-size:14px">Proposed jobs</span>'
            f'<span style="background:var(--color-accent);color:#fff;font-size:11px;border-radius:999px;padding:1px 8px">{n}</span>'
            f'<span style="font-size:11.5px;color:var(--text-muted)">'
            f'awaiting your approval — nothing runs until you approve</span></div>')
    return (f'<div style="margin-bottom:18px;padding:14px 16px;border:1px solid var(--color-accent-2);border-radius:var(--r);'
            f'background:var(--accent2-7)">{head}{cards}</div>{_JOB_PROPOSAL_JS}')


def _autonomy_control(current: str, field_id: str) -> str:
    cur = _AUTONOMY_ALIAS.get(current, current) or "manual"
    cards = ""
    for v, label, ic, desc, color, hover in _AUTONOMY_MODES:
        on = v == cur
        cards += (f'<div class="mc-auto-opt" data-v="{v}" data-fid="{field_id}" onclick="mcPickAuto(this)" '
                  f'style="cursor:pointer;border:1px solid {"var(--color-accent)" if on else "var(--color-divider)"};'
                  f'background:{"var(--color-accent-100)" if on else "transparent"};border-radius:var(--r);padding:9px 11px;'
                  f'display:flex;gap:9px;align-items:flex-start">'
                  f'<span title="{E(hover)}" style="display:flex;color:{color};margin-top:1px">{_icon(ic,16)}</span>'
                  f'<div><div style="font-size:12.5px;font-weight:600">{E(label)}</div>'
                  f'<div style="font-size:11px;color:var(--text-muted)">{E(desc)}</div></div></div>')
    return (f'<input type="hidden" id="{field_id}" value="{cur}">'
            f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">{cards}</div>')




_EFFORTS = ["low", "medium", "high", "max"]
# Filter bucket → the legend's name for it. The dropdown used to carry its own table of flat
# colours, which drifted the moment the legend gained tinted fills and a glyph for Missed: the menu
# was still offering a solid teal "Success" the strip had not drawn in two revisions. There is one
# definition of what a status looks like now (_health_swatch) and this only says which is which.
_STATUS_FILTER_LABEL = {"success": "Success", "running": "Running", "warning": "Warning",
                        "failed": "Failed", "none": "Missed"}
# Kept as a name so older call sites still resolve; the values are legend labels, not colours.
_STATUS_FILTER_COLOR = _STATUS_FILTER_LABEL


def _gather_artifacts(realm, realm_root, only_agent: str = None) -> list[dict]:
    """Every artifact across the realm: input artifacts (owner attachments on user turns) and output
    artifacts (files agents wrote, on assistant turns). One row per artifact, with its thread owner,
    thread, type, extension, path, and last-touched date (the file's mtime if it's on disk, else the
    turn timestamp). Sorted newest-touched first."""
    from ..threads import Thread
    rows = []
    for a in realm.agents:
        if only_agent and a.id != only_agent:
            continue
        agent_dir = Path(realm_root) / "agents" / a.id
        if not (agent_dir / "threads").is_dir():
            continue
        _, meta = _ordered_threads(agent_dir)
        for tname in Thread.list_threads(agent_dir):
            th = Thread(agent_dir, tname)
            ttitle = _thread_title(meta, tname)
            for m in th._messages():
                role = m.get("role")
                ts = str(m.get("ts", ""))
                if role == "user":
                    for att in (m.get("attachments") or []):
                        name = att.get("name") or att.get("file") or "file"
                        path = (str(agent_dir / "threads" / tname / "attachments" / att["file"])
                                if att.get("kind") == "image" and att.get("file") else "")
                        rows.append(_art_meta(name, a, ttitle, tname, "input", path, ts))
                elif role == "assistant":
                    for out in (m.get("outputs") or []):
                        rows.append(_art_meta(out.get("name") or "file", a, ttitle, tname,
                                              "output", out.get("path") or "", ts))
    rows.sort(key=lambda r: r["date_iso"], reverse=True)     # newest touched first
    return rows


def _art_meta(name: str, agent, thread_title: str, thread_slug: str, kind: str, path: str, ts: str) -> dict:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    exists, date_iso = False, ts
    if path:
        try:
            p = Path(path)
            if p.is_file():
                exists = True
                date_iso = datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        except OSError:
            pass
    return {"name": name, "owner_id": agent.id, "owner": agent.display, "thread": thread_title,
            "thread_slug": thread_slug, "type": kind, "ext": ext, "path": path,
            "exists": exists, "date_iso": date_iso, "ymd": date_iso[:10]}


def _realm_artefacts(realm, realm_root, only_agent: str = None) -> str:
    rows = _gather_artifacts(realm, realm_root, only_agent)
    show_owner = only_agent is None
    owners = sorted({(r["owner_id"], r["owner"]) for r in rows}, key=lambda x: x[1])
    # header cells (Owner column dropped in the per-agent view)
    heads = [("Name", "text"), ("Thread owner", "text"), ("Thread", "text"), ("Type", "text"),
             ("File", "text"), ("Path", "text"), ("Last touched", "date"), ("", "")]
    if not show_owner:
        heads = [h for h in heads if h[0] != "Thread owner"]
    thead = "".join(
        (f'<th style="width:1%"></th>' if not t else                      # actions column: not sortable
         f'<th data-col="{i}" data-sort="{s}" onclick="mcArtSort(this)" '
         f'style="cursor:pointer;user-select:none;white-space:nowrap">{E(t)}'
         f'<span class="mc-arr" style="opacity:.4"> ↕</span></th>')
        for i, (t, s) in enumerate(heads))
    body = ""
    for r in rows:
        rev = f' data-open="{E(r["path"])}"' if r["exists"] else ""   # click the row → open the file
        cur = "cursor:pointer;" if r["exists"] else ""
        search = " ".join((r["name"], r["owner"], r["thread"], r["path"])).lower()
        is_out = r["type"] == "output"
        tcol = "var(--color-accent)" if is_out else "var(--color-sand-600, var(--text-muted))"
        cells = [f'<td style="padding:6px 8px"><span style="display:inline-flex;align-items:center;gap:7px;max-width:340px">'
                 f'<span style="display:flex;flex:none;color:var(--text-soft)">{_icon(_file_icon(r["name"]), 14)}</span>'
                 f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{E(r["name"])}</span></span></td>']
        if show_owner:
            cells.append(f'<td style="padding:6px 8px;white-space:nowrap">{E(r["owner"])}</td>')
        cells.append(f'<td style="padding:6px 8px"><a href="/agent/{E(r["owner_id"])}/threads?thread={E(r["thread_slug"])}" '
                     f'style="color:var(--color-accent);text-decoration:none">{E(r["thread"])}</a></td>')
        cells.append(f'<td style="padding:6px 8px"><span style="display:inline-flex;align-items:center;gap:6px;'
                     f'font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap">'
                     f'<span style="display:flex;flex:none;color:{tcol}">'
                     f'{_icon("art-output" if is_out else "art-input", 15)}</span>{E(r["type"])}</span></td>')
        cells.append(f'<td style="padding:6px 8px" class="mono">{("." + r["ext"]) if r["ext"] else "—"}</td>')
        cells.append(f'<td style="padding:6px 8px" class="mono"><span title="{E(r["path"] or "not saved to disk")}" '
                     f'style="display:inline-block;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
                     f'vertical-align:bottom;color:var(--text-dim)">{E(r["path"] or "—")}</span></td>')
        cells.append(f'<td style="padding:6px 8px;white-space:nowrap" data-v="{E(r["date_iso"])}">{_fmt_ts(r["date_iso"])}</td>')
        # Row actions. Only offered when the file is actually on disk — nothing to show or remove
        # otherwise. Both stop propagation so they don't also trigger the row's open-file click.
        if r["exists"]:
            # The path travels in a data- attribute, never inside an inline JS string: a Windows
            # path in a JS literal is destroyed by escape processing (\f in "\finance" becomes a
            # form feed, \W and \H just lose their backslash), so the server saw a mangled path.
            p = E(r["path"])
            acts = (f'<a class="mc-cap-ico mc-art-go" title="Go to file" data-path="{p}">'
                    f'{_icon("go-to-file",16)}</a>'
                    f'<a class="mc-cap-ico mc-art-del" title="Delete file" data-path="{p}" '
                    f'style="color:var(--text-muted)">{_icon("trash",16)}</a>')
        else:
            acts = ""
        cells.append(f'<td style="padding:6px 8px;white-space:nowrap;text-align:right">'
                     f'<span style="display:inline-flex;align-items:center;gap:8px">{acts}</span></td>')
        body += (f'<tr class="mc-row" data-owner="{E(r["owner_id"])}" data-type="{r["type"]}" data-ymd="{E(r["ymd"])}" '
                 f'data-search="{E(search)}"{rev} style="{cur}">' + "".join(cells) + "</tr>")
    if not rows:
        body = (f'<tr><td colspan="{len(heads)}" style="padding:14px 8px;color:var(--text-muted)">'
                f'No artefacts yet. Files an agent produces in a thread — and files you attach — show up here.</td></tr>')
    today = clock.today().isoformat()
    muted = "var(--text-soft)"
    faint = "var(--text-faint)"
    owner_dd = ""
    if show_owner:
        owner_dd = _filter_dropdown("art-owner", "All owners",
                                    [("", "All owners", "")] + [(oid, od, "") for oid, od in owners],
                                    width="150px", onpick="mcArtApply")
    type_dd = _filter_dropdown("art-type", "All types",
                               [("", "All types", ""), ("input", "Input", ""), ("output", "Output", "")],
                               width="130px", onpick="mcArtApply")
    dd_ids = "['art-owner','art-type']" if show_owner else "['art-type']"
    controls = (f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 12px">'
                f'<div style="position:relative;flex:0 0 220px">'
                f'<span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);display:flex;color:{faint}">{_icon("search",14)}</span>'
                f'<input id="art-q" placeholder="Search name, path, thread…" oninput="mcArtApply()" style="{_FIELD};padding-left:30px;padding-right:26px">'
                f'<span id="art-q-x" onclick="mcArtSearchClear()" title="Clear" style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:{faint}">{_icon("x",14)}</span></div>'
                f'<span style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:{faint}">Filter</span>'
                f'{owner_dd}{type_dd}'
                f'<span style="font-size:12px;color:{muted}">Touched</span>'
                f'<input id="art-from" type="date" max="{today}" onchange="mcArtApply()" style="{_FIELD};width:148px" title="From date (no future)">'
                f'<span style="color:{faint}">–</span>'
                f'<input id="art-to" type="date" max="{today}" onchange="mcArtApply()" style="{_FIELD};width:148px" title="To date (no future)">'
                f'<button id="art-clear" onclick="mcArtClear({dd_ids})" style="display:none;align-items:center;gap:4px;'
                f'border:0;background:transparent;cursor:pointer;font-size:12px;color:var(--color-accent);padding:6px 4px">{_icon("x",12)}Clear</button>'
                f'<span id="art-count" style="margin-left:auto;font-size:11.5px;color:{muted}"></span></div>')
    title = "" if not show_owner else _page_title("Artefacts", "input & output files across the realm")
    return (f'<div style="padding:{"12px 0 0" if not show_owner else "18px 24px 24px"}">'
            f'{title}'
            f'<div style="{"padding:0 24px" if not show_owner else ""}">'
            f'{controls}'
            f'<div style="overflow:auto"><table class="table" id="art-table" data-today="{today}" style="font-size:12.5px;width:100%">'
            f'<thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table></div></div></div>{_FDROP_JS}{_ARTEFACTS_JS}')
