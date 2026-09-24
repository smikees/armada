"""Dashboard widget renderers (Layer 2, carved from _core.py in Phase 3).

The Register, Usage and Job-calendar widgets (+ their shared widget header/menu chrome and
health-legend styling). Import lower layers + the agent-rendering primitives (agentbits), never
_core, so _core imports these back without a cycle.
"""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import clock
from .. import goals as goalsmod
from ..icons import ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR, _ICON_REFRESH
from ._base import E, _J, _STAR, _md_inline, _md, _page_title, _chip
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _ordinal, _next_hint, _fmt_ts)
from .agentbits import _coord_mark
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _jobs_cell, _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES,
    # Health lives one layer down now, so the Register widget can draw the same seven squares the
    # Jobs list draws. Re-exported from here because everything above still imports them from here.
    _RUNNING_COLOR, _UNSCHEDULED_COLOR, _HEALTH_STYLES, _HEALTH_LEGEND_ORDER, _health_legend_chips,
    _health_square, _health7_header, _job_health7, _sysjob_health7, _status_legend, _WEEK_BACK, _WEEK_FWD,
    _agent_health7, _agent_week_strip, _health_tip, _health_styles_js,
    _HEALTH_PHRASE, _HEALTH_WORST, _HEALTH_RANK,
    _running_jobs, _job_prompt, _job_created, _job_created_ts)


def _reg_row(a, realm_root: Path, today: datetime.date, coord: bool = False, realm=None) -> str:
    # The same seven squares the Jobs list and the agent cards draw — worst status per day across
    # everything this agent owns. The old bars came from run-reports alone, so they could not tell
    # "nothing was due" from "everything was missed", and they disagreed with the Jobs page.
    now = clock.now()
    bars = _agent_week_strip(realm_root, a, now)
    ring =('border:1px solid var(--color-accent-2);background:var(--color-accent-2-100)') if coord else \
           'border:1px solid var(--color-divider);background:var(--color-accent-100)'
    dept_color = "var(--color-accent-2-700)" if coord else "var(--color-accent-700)"
    tok = f"{a.tokens_30d/1000:.0f}k" if a.tokens_30d else "—"
    rowbg = "background:var(--color-accent-2-100);cursor:pointer" if coord else "cursor:pointer"
    role = E(a.theme_role.upper())
    _model, _effort = _agent_model_effort(realm, realm_root, a.id)
    model_cell = _model_chip(_model, _effort, 11)
    autonomy = _autonomy_badge(_autonomy_of(realm_root, a.id), 15)
    return (f'<tr class="mc-row" style="{rowbg}" onclick="location.href=\'/agent/{E(a.id)}\'">'
            f'<td style="padding:6px 12px"><div style="display:flex;gap:10px;align-items:center">'
            # dot_grow: at 30px the proportional dot rounds to 7, which is a pixel shy of reading
            # clearly in a dense table row.
            f'<div style="flex:none">{_portrait(realm_root, a, 30, dot=True, dot_grow=1)}</div>'
            f'<div><div style="display:flex;align-items:center;gap:6px">'
            f'<span style="font-family:var(--font-heading);font-weight:600;font-size:15px;line-height:1.1" title="{E(a.leader)}">{E(a.display)}</span>'
            + (_coord_mark(14) if coord else "")
            # Autonomy rides with the name rather than holding a 70px column of its own. It is an
            # icon, it is a property of the agent, and the week strip needed the room more.
            + f'<span style="display:inline-flex;flex:none">{autonomy}</span></div>'
            f'<div style="font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:{dept_color};white-space:nowrap;margin-top:1px">{role}</div></div></div></td>'
            f'<td style="white-space:nowrap">{model_cell}</td>'
            f'<td style="text-align:center">{_goals_cell(realm_root, a)}</td>'
            f'<td style="text-align:center">{_jobs_cell(a)}</td>'
            f'<td style="font-family:ui-monospace,Menlo,monospace;font-size:11.5px">{_next_hint(a)}</td>'
            f'<td style="text-align:right;font-family:var(--font-heading);font-weight:600">{tok}</td>'
            f'<td style="white-space:nowrap">{bars}</td></tr>')


def _widget_menu(widget_id: str) -> str:
    """The ⋮ options menu on a single-instance widget (Register / Usage / Job calendar), top-right.
    'Add as section' promotes the widget to its own nav page; 'Remove widget' hides it (client handlers)."""
    _mi = ("display:flex;align-items:center;gap:9px;padding:7px 10px;font-size:12.5px;cursor:pointer;"
           "text-decoration:none;border-radius:var(--r)")
    return (f'<div class="mc-wmwrap" style="position:relative;display:flex;flex:none">'
            f'<button class="mc-iconbtn mc-wdots" title="Options" onclick="mcWidgetMenu(event,this)">'
            f'{_icon("dots", 18)}</button>'
            f'<div class="mc-wmenu" style="display:none;position:absolute;top:26px;right:0;z-index:40;min-width:172px;'
            f'background:var(--color-bg);border:1px solid var(--color-divider);border-radius:var(--r);box-shadow:var(--shadow-md);padding:4px">'
            f'<a onclick="mcWidgetAddSection({_J(widget_id)})" style="{_mi};color:inherit">'
            f'<span style="display:flex;color:var(--text-dim)">{_icon("plus", 16)}</span>'
            f'<span style="flex:1">Add as section</span></a>'
            f'<a onclick="mcWidgetRemove({_J(widget_id)})" style="{_mi};color:var(--status-bad)">'
            f'<span style="display:flex">{_icon("trash", 16)}</span><span style="flex:1">Remove widget</span></a>'
            f'</div></div>')


def _wid_header(title: str, meta: str = "", right: str = "", widget_id: str = "", chrome: bool = True) -> str:
    m = (f'<span style="font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;'
         f'color:var(--text-soft)">{meta}</span>') if meta else ""
    grip = GRIP if chrome else ""
    menu = _widget_menu(widget_id) if (widget_id and chrome) else ""
    tail = (f'<div style="margin-left:auto;display:flex;align-items:center;gap:10px">{right}{menu}</div>'
            if (right or menu) else "")
    return (f'<div class="mc-wid-h" style="display:flex;align-items:center;gap:6px;padding:8px 12px;border-bottom:1px solid var(--color-divider)">'
            f'{grip}<span style="font-family:var(--font-heading);font-weight:600;font-size:15px">{E(title)}</span>{m}{tail}</div>')


def _register(realm, realm_root, today, section: bool = False) -> str:
    rows = ""
    if realm.coordinator:
        rows += _reg_row(realm.coordinator, realm_root, today, coord=True, realm=realm)
    for a in realm.members:
        rows += _reg_row(a, realm_root, today, realm=realm)
    meta = f"· {realm.theme_coordinator} + {len(realm.members)} {realm.theme_agent.lower()}s"
    appoint = '' if section else '<a onclick="mcOpenAppoint()" style="font-size:11.5px;color:var(--color-accent);text-decoration:none;cursor:pointer">+ Appoint</a>'
    return (f'<div class="mc-widget" style="height:100%;display:flex;flex-direction:column;overflow:hidden">'
            f'{_wid_header("Register", meta, appoint, widget_id="register", chrome=not section)}'
            f'<div class="mc-scroll" style="flex:1;min-height:0;overflow:auto">'
            f'<table class="table" style="font-size:12.5px"><thead><tr>'
            f'<th style="padding-left:12px">Member</th><th>Model</th>'
            f'<th style="text-align:center;width:60px">Goals</th>'
            f'<th style="text-align:center;width:44px">Jobs</th><th style="width:124px">Next run</th>'
            f'<th style="text-align:right;width:70px">Tok / 30d</th>'
            # Not day initials: every square here is a day that has already happened, so the column
            # needs to say what it is, not which weekday each cell was.
            f'<th title="Worst job outcome per day, across this member\'s jobs" '
            f'style="width:100px;white-space:nowrap">7D job status</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div></div>')


_ICON_LINE = ('<svg width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" '
              'stroke-linecap="round" stroke-width="2" d="M5 6h14M5 12h14M5 18h14"/></svg>')
_ICON_GRAPH = ('<svg width="15" height="15" viewBox="0 0 16 16"><g fill="currentColor">'
               '<path d="M1.5 1a.5.5 0 0 1 .5.5V14h12.5a.5.5 0 0 1 0 1h-13a.5.5 0 0 1-.5-.5v-13a.5.5 0 0 1 .5-.5"/>'
               '<path d="M5 8a1 1 0 0 1 1 1v4H3V9a1 1 0 0 1 1-1zm4-6a1 1 0 0 1 1 1v10H7V3a1 1 0 0 1 1-1zm4 4a1 1 0 0 1 1 1v6h-3V7a1 1 0 0 1 1-1z"/></g></svg>')


def _usage(realm, realm_root, today, section: bool = False) -> str:
    def mbtn(k, icon, title):
        return (f'<button class="mc-um" data-um="{k}" title="{title}" style="border:0;background:transparent;cursor:pointer;'
                f'padding:4px 8px;border-radius:var(--r);display:inline-flex;align-items:center;line-height:1;'
                f'color:var(--text-soft)">{icon}</button>')
    # view (line/graph) selectors sit next to the title; the time-span selectors at the far right —
    # all in the widget header. mc-usage-tb class kept on the header so the client JS still finds them.
    grip = "" if section else GRIP
    menu = "" if section else _widget_menu("usage")
    header = (f'<div class="mc-wid-h mc-usage-tb" style="display:flex;align-items:center;gap:6px;padding:8px 12px;'
              f'border-bottom:1px solid var(--color-divider);position:relative">'
              f'{grip}<span style="font-family:var(--font-heading);font-weight:600;font-size:15px">Usage</span>'
              f'<div style="display:flex;gap:2px;margin-left:8px">{mbtn("line", _ICON_LINE, "Line view")}{mbtn("graph", _ICON_GRAPH, "Graph view")}</div>'
              f'<div class="mc-usage-intervals" style="margin-left:auto;display:flex;gap:2px"></div>'
              f'<button class="mc-iconbtn mc-usage-refresh" title="Refresh now (auto every 30 min)" '
              f'style="margin-left:12px;padding:4px 6px">{_ICON_REFRESH}</button>'
              f'{menu}</div>')
    return (f'<div class="mc-widget mc-usage" style="height:100%;display:flex;flex-direction:column;overflow:hidden">'
            f'{header}'
            f'<div class="mc-usage-body mc-scroll" style="flex:1;min-height:0;overflow:auto"></div></div>')


def _jobcal(realm, realm_root, today, legend: bool = True, widget: bool = True,
            scope: str = "", fpfx: str = "", title: str = "Job calendar") -> str:
    """The job calendar. `scope` selects which events it loads ('' = the realm's agent jobs,
    'system' = ARMADA's own upkeep) and `fpfx` names the filter bar it should obey — empty on the
    dashboard widget, which has no filters."""
    def nav(k, label):
        return (f'<button class="mc-jc-nav" data-jc="{k}" style="border:0;background:transparent;cursor:pointer;'
                f'font-size:12px;padding:3px 8px;border-radius:var(--r);line-height:1;'
                f'color:var(--text-dim)">{label}</button>')

    def vbtn(k, label):
        return (f'<button class="mc-jc-view" data-jc="{k}" style="border:0;background:transparent;cursor:pointer;'
                f'font-size:11px;padding:4px 10px;border-radius:var(--r);line-height:1;'
                f'color:var(--text-muted)">{label}</button>')
    # controls live in the widget header itself (like Usage): [grip] Job calendar  ‹ Today ›  label … Month/Week/Day [⋮]
    grip = GRIP if widget else ""
    menu = _widget_menu("jobcal") if widget else ""
    tb = (f'<div class="mc-wid-h" style="display:flex;align-items:center;gap:4px;padding:8px 12px;'
          f'border-bottom:1px solid var(--color-divider)">'
          f'{grip}<span style="font-family:var(--font-heading);font-weight:600;font-size:15px;margin-right:20px">{title}</span>'
          f'{nav("prev", "‹")}{nav("today", "Today")}{nav("next", "›")}'
          f'<span class="mc-jc-label" style="display:inline-block;box-sizing:border-box;min-width:150px;text-align:center;'
          f'font-weight:400;font-size:11px;margin-left:4px;white-space:nowrap;'
          f'background:var(--text-9);padding:3px 9px;border-radius:var(--r)"></span>'
          f'<div style="margin-left:auto;display:flex;align-items:center;gap:8px">'
          f'<div style="display:flex;gap:2px">{vbtn("month", "Month")}{vbtn("week", "Week")}{vbtn("day", "Day")}</div>'
          f'{menu}</div></div>')

    # same status swatches as the Jobs list legend (minus 'Not scheduled', which is a per-job
    # state that doesn't apply to a calendar). Omitted entirely on the Jobs page, where the
    # status legend already sits above the calendar.
    legend_html = ""
    if legend:
        legend_html = (f'<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;padding:5px 12px;'
                       f'border-top:1px solid var(--color-divider)">{_health_legend_chips(exclude=("Not scheduled",))}</div>')
    return (f'<div class="mc-widget mc-jobcal" data-scope="{scope}" data-fpfx="{fpfx}" '
            f'style="height:100%;display:flex;flex-direction:column;overflow:hidden">'
            f'{tb}'
            f'<div class="mc-jc-body mc-scroll" style="flex:1;min-height:0;overflow:auto"></div>{legend_html}</div>')
