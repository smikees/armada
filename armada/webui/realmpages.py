"""Realm-level management pages (Phase 3 split of agentpages): Ministers, Jobs (health grid + filters) and Artefacts."""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import clock
from .. import goals as goalsmod
from ..icons import (ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR,
                     ICON_MISSED, _ICON_REFRESH)
from ._base import (E, _J, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _mini_pill, _poss)
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _sysjob_cadence_bucket, _status_bucket,
    _STATUS_FILTERS, _CADENCE_FILTERS, _next_run_dt, _job_next_dt, _ordinal, _next_hint, _fmt_ts)
from .agentbits import _week_filter_bucket, _FILTER_BACK_DAYS, _coord_mark
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _jobs_cell, _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)
from .threadsview import (_agent_model_label, _chat_center, _ordered_threads, _sub, _tab_threads,
    _thread_title, _user_avatar, _user_avatar_file, _mark_thread_unread, _clear_thread_unread)
from .widgets import (_RUNNING_COLOR, _UNSCHEDULED_COLOR, _HEALTH_STYLES, _health_legend_chips, _jobcal,
    # The health strip moved down to agentbits so the Register widget can draw it too; these are
    # re-exports, and agentframe still imports them from here.
    _health_square, _health7_header, _job_health7, _sysjob_health7, _status_legend, _WEEK_BACK, _WEEK_FWD,
    _agent_health7, _agent_week_strip, _health_tip, _health_styles_js)
from .goalsview import _tab_goals
from .memoryview import _tab_memory, _agent_memory, _list_mem
from .capabilities import (_tab_skills, _agent_toolkit, _realm_toolkit, _cap_manage_btn,
    _tool_group, _tool_row, _toolkit_from)
from ..assets import (AGENT_COLOR_JS as _AGENT_COLOR_JS, APPOINT_JS as _APPOINT_JS,
    ARTEFACTS_JS as _ARTEFACTS_JS, AUTONOMY_JS as _AUTONOMY_JS, FDROP_JS as _FDROP_JS,
    JOB_PROPOSAL_JS as _JOB_PROPOSAL_JS, JOBCAL_JS as _JOBCAL_JS, JOBS_FILTER_JS as _JOBS_FILTER_JS,
    SYSJOBS_JS as _SYSJOBS_JS, ADOPT_JS as _ADOPT_JS,
    JOBS_SORT_JS as _JOBS_SORT_JS, NEW_JS as _NEW_JS, TABLE_SORT_JS as _TABLE_SORT_JS,
    JOBSTAB_JS as _JOBSTAB_JS)  # Phase 2, 2.1
from .agentcommon import (_AGENT_PALETTE, _EFFORTS, _STATUS_FILTER_COLOR, _agent_color_control, _art_meta, _autonomy_control, _effort_options, _filter_dropdown, _gather_artifacts, _job_created, _job_created_ts, _job_prompt, _job_proposals_block, _model_options, _realm_artefacts, _running_jobs)
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


def _fmt_date_short(s) -> str:
    """A date as dd/mm/yy (falls back to the raw string)."""
    s = str(s or "")
    try:
        return datetime.date.fromisoformat(s[:10]).strftime("%d/%m/%y")
    except ValueError:
        return s


def _new_agent_form(realm, cancel_html: str) -> str:
    """Shared appoint-a-agent form body (fields + actions). Used by the full /new/agent page
    and the dashboard Appoint modal — same field IDs, so mcNewAgent() works in both."""
    model_opts = _model_options(realm.root, inherit=True)
    effort_opts = _effort_options(realm.root, inherit=True)
    _next = len(([realm.coordinator] if realm.coordinator else []) + list(realm.members))
    defcolor = _AGENT_PALETTE[_next % len(_AGENT_PALETTE)]     # next palette colour as the default
    return (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
            f'<div><label style="{_LBL}">Name {_STAR}</label><input id="n-name" placeholder="E.g. Warren" style="{_FIELD}"></div>'
            f'<div><label style="{_LBL}">Role</label><input id="n-role" placeholder="E.g. {E(realm.theme_agent)} of Finance" style="{_FIELD}"></div>'
            f'<div style="grid-column:1 / 3"><label style="{_LBL}">Profile (optional)</label><input id="n-leader" placeholder="E.g. after Warren Buffett — value discipline, margin of safety…" style="{_FIELD}"></div>'
            # Same order as the Configure page: cosmetics together, then behaviour.
            f'<div style="grid-column:1 / 3"><label style="{_LBL}">Agent colour — shows up in token usage breakdowns, etc.</label>'
            f'{_agent_color_control(defcolor, "n-color")}</div>'
            f'<div style="grid-column:1 / 3"><label style="{_LBL}">Autonomy</label>{_autonomy_control("manual", "n-autonomy")}</div>'
            f'<div><label style="{_LBL}">Model</label><select id="n-model" style="{_FIELD}">{model_opts}</select></div>'
            f'<div><label style="{_LBL}">Effort</label><select id="n-effort" style="{_FIELD}">{effort_opts}</select></div>'
            f'<div id="n-cons" style="grid-column:1 / 3"><label style="{_LBL}">Relative token consumption '
            f'<span style="text-transform:none;letter-spacing:0;color:var(--text-muted)">· this model &amp; effort</span></label>'
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<span class="mc-modelmark" style="display:inline-flex;color:var(--text-muted)">{_icon("claude", 16)}</span>'
            f'<div style="position:relative;flex:1;height:12px;border-radius:6px;background:{_consumption_gradient_css()}">'
            f'<div id="n-consmarker" style="position:absolute;top:-3px;left:0%;transform:translateX(-50%);width:4px;height:18px;'
            f'border-radius:3px;background:var(--color-text);box-shadow:0 0 0 2px var(--color-bg)"></div></div>'
            f'<span style="font-size:10px;color:var(--text-muted);white-space:nowrap">low → high</span></div>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:5px">Where this model + effort sits between the '
            f'cheapest and most token-hungry combination. The icon colour tracks the marker.</div></div>'
            f'</div>'
            f'<label style="{_LBL};display:flex;align-items:center;gap:7px;cursor:pointer">'
            f'<input type="checkbox" id="n-coord" style="margin:0;flex:none"><span>Is coordinator</span>'
            # The same laurel the agent will wear once the box is ticked, so the mark is learnable
            # from the place you set it rather than only from the lists that show it.
            + _coord_mark(16)
            + f'<span class="mc-tip" data-tip="A coordinator agent has realm-wide visibility and is added automatically to every goal." '
            f'style="display:inline-flex;align-items:center;color:var(--text-muted);cursor:help">{_icon("info", 16)}</span></label>'
            f'<label style="{_LBL}">Soul (character, voice &amp; traits)</label><textarea id="n-soul" style="{_TA};min-height:70px" '
            f'placeholder="Precise, unsentimental, numbers-first."></textarea>'
            f'<label style="{_LBL}">Role and Mission</label><textarea id="n-mandate" style="{_TA};min-height:120px" '
            f'placeholder="You watch the books and surface decisions with the numbers. You never move money."></textarea>'
            f'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" style="color:#fff;font-size:12.5px;padding:6px 14px" onclick="mcNewAgent()">Appoint</button>'
            f'{cancel_html}'
            f'<span id="n-msg" style="font-size:12px;color:var(--text-muted)"></span></div>'
            f'<div style="margin-top:10px;font-size:11.5px;color:var(--text-muted)">'
            f'These and other settings can be added/edited later in the agent Configure section.</div>')


def _reinstate_pane(realm, retired: list) -> str:
    """Pick someone back out of retirement.

    Deliberately a picker and not a form to fill in: a retired agent is a settled thing — a
    mandate, a soul, tenets, jobs on schedules, months of threads — and retyping any of it would
    be both tedious and a way to come back subtly different from how you left. The fields shown
    are the handful you might reasonably want to change on the way in; everything else is restored
    untouched, and the fields fill themselves the moment you choose a name.
    """
    role = E(realm.theme_agent.lower())
    opts = '<option value="">Choose who to bring back…</option>' + "".join(
        f'<option value="{E(r["id"])}">{E(r["display"])}'
        + (f' — {E(r["role"])}' if r.get("role") else "")
        + (f' · retired {E(str(r["retired"])[:10])}' if r.get("retired") else "")
        + '</option>' for r in retired)
    data = json.dumps({r["id"]: r for r in retired})
    return (f'<div id="mc-appoint-reinstate" style="display:none">'
            f'<div style="font-size:12.5px;color:var(--text-muted);line-height:1.6;margin-bottom:12px;max-width:620px">'
            f'Bring a retired {role} back exactly as they were. Their jobs, threads, memories, '
            f'capability grants and run history all return with them — nothing was deleted when '
            f'they were retired. Change anything below on the way in, or leave it and they come '
            f'back unchanged.</div>'
            f'<label style="{_LBL}">Who</label>'
            f'<select id="r-agent" onchange="mcReinstatePick()" style="{_FIELD}">{opts}</select>'
            f'<div id="r-fields" style="display:none;margin-top:12px">'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
            f'<div><label style="{_LBL}">Name</label><input id="r-name" style="{_FIELD}"></div>'
            f'<div><label style="{_LBL}">Role</label><input id="r-role" style="{_FIELD}"></div>'
            f'<div style="grid-column:1 / 3"><label style="{_LBL}">Profile</label>'
            f'<input id="r-leader" style="{_FIELD}"></div>'
            f'<div><label style="{_LBL}">Model</label>'
            f'<select id="r-model" style="{_FIELD}">{_model_options(realm.root, inherit=True)}</select></div>'
            f'<div><label style="{_LBL}">Effort</label>'
            f'<select id="r-effort" style="{_FIELD}">{_effort_options(realm.root, inherit=True)}</select></div>'
            f'</div>'
            f'<div id="r-carry" style="font-size:11.5px;color:var(--text-muted);margin-top:10px;line-height:1.5"></div>'
            f'</div>'
            f'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" style="color:#fff;font-size:12.5px;padding:6px 14px" '
            f'onclick="mcReinstate()">Reinstate</button>'
            f'<button type="button" class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px" '
            f'onclick="mcCloseAppoint()">Cancel</button>'
            f'<span id="r-msg" style="font-size:12px;color:var(--text-muted)"></span></div>'
            f'<script>window.MC_RETIRED={data};</script></div>')


def _appoint_modal(realm) -> str:
    """The Appoint form as a dashboard modal — same form as /new/agent, opened in place.

    Gains a Reinstate tab when, and only when, there is somebody to reinstate. A permanently
    visible tab that is empty most of the time teaches people to ignore it, and the one moment it
    matters is the moment they stop looking.
    """
    from .. import agentops
    try:
        retired = agentops.list_retired(realm.root)
    except Exception:  # noqa — a retired folder we can't read must not break Appoint
        swallowed(log, '_appoint_modal: failed; using a default')
        retired = []
    cancel = ('<button type="button" class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px" '
              'onclick="mcCloseAppoint()">Cancel</button>')
    role = E(realm.theme_agent.lower())
    tabs = ""
    if retired:
        tabs = (f'<div class="mc-captabs" style="display:flex;gap:2px;'
                f'border-bottom:1px solid var(--color-divider);margin:2px 0 16px">'
                f'<a id="mc-appoint-tab-new" class="mc-captab" onclick="mcAppointTab(\'new\')">Appoint</a>'
                f'<a id="mc-appoint-tab-reinstate" class="mc-captab" onclick="mcAppointTab(\'reinstate\')">'
                f'Reinstate <span style="opacity:.6">({len(retired)})</span></a></div>')
    return (f'<div id="mc-appoint-ov" onclick="if(event.target===this)mcCloseAppoint()" style="display:none;position:fixed;inset:0;z-index:120;'
            f'background:rgba(0,0,0,.38);align-items:flex-start;justify-content:center;padding:40px 16px;overflow:auto">'
            f'<div style="background:var(--color-bg);border:1px solid var(--color-divider);border-radius:14px;box-shadow:var(--shadow-lg);'
            f'width:100%;max-width:720px;padding:20px 22px 22px">'
            f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">'
            f'<h2 id="mc-appoint-title" style="font-family:var(--font-heading);font-size:22px;margin:0">'
            f'Appoint a new {role}</h2>'
            f'<button type="button" onclick="mcCloseAppoint()" title="Close" style="margin-left:auto;border:0;background:transparent;cursor:pointer;'
            f'font-size:20px;line-height:1;color:var(--text-soft)">×</button></div>'
            f'{tabs}'
            f'<div id="mc-appoint-new">{_new_agent_form(realm, cancel)}</div>'
            + (_reinstate_pane(realm, retired) if retired else "")
            + f'<script>window.MC_ROLE_LABEL={json.dumps(realm.theme_agent.lower())};</script>'
            f'</div></div>')




def _health_grid(realm, realm_root, today) -> str:
    """Scheduler/reliability: jobs × last-7-days grid."""
    rows = ""
    day_labels = "".join(f'<th style="width:20px;text-align:center;font-size:9px">{(today-datetime.timedelta(days=i)).strftime("%a")[0]}</th>' for i in range(6, -1, -1))
    for a in realm.agents:
        runs = _runs(realm_root, a.id)
        for j in a.jobs:
            jruns = [ev for ev in runs if ev.get("task") == j.id]
            week = _health7(jruns, today)
            cells = "".join(f'<td style="text-align:center"><i style="display:inline-block;width:14px;height:14px;'
                            f'border-radius:2px;background:{c}"></i></td>' for c in week)
            rows += (f'<tr class="mc-row"><td style="padding:5px 8px;font-size:12px">{E(a.display)} <span style="color:'
                     f'var(--text-soft)">· {E(j.name)}</span></td>{cells}</tr>')
    if not rows:
        rows = '<tr><td colspan="8" style="padding:10px;color:var(--text-muted)">No jobs.</td></tr>'
    return (f'<table class="table" style="font-size:12px"><thead><tr><th style="padding-left:8px">Job</th>{day_labels}</tr></thead>'
            f'<tbody>{rows}</tbody></table>')


def _agent_cap_counts(realm_root, aid: str) -> dict:
    """How many connected capabilities this agent can actually USE, per kind.

    Was realm-wide + agent-specific, from when every agent inherited the realm's catalogue. That
    made the number on an agent's card the size of the realm rather than anything about the agent,
    so every card showed the same figures — and after grants arrived it was simply wrong. It reads
    the grant model now, which is also what decides what the engine will let through.
    """
    from .. import capabilities as _caps
    out = {}
    try:
        use = _caps.usable(realm_root, aid)
    except Exception:  # noqa — a card must render even if one agent.json is unreadable
        swallowed(log, '_agent_cap_counts: failed; returning a fallback')
        return {k: 0 for k in ("connectors", "extensions", "plugins", "skills")}
    for kind in ("connectors", "extensions", "plugins", "skills"):
        out[kind] = sum(1 for it in (use.get(kind) or [])
                        if (it.get("status") or "connected").lower() == "connected")
    return out


def _cap_count_row(realm_root, aid: str, is_coord: bool = False, active_jobs: int = 0) -> str:
    """The card's footer tally, in two groups.

    Left is what this agent is working on and with — goals, memories, active jobs. Right is what it
    can reach — connectors, extensions, skills, plugins. Six icons in an undifferentiated line read
    as one list of six equivalent things, which they are not; the gap does the explaining."""
    c = _agent_cap_counts(realm_root, aid)
    ng = len(goalsmod.goals_for_agent(realm_root, aid, is_coord=is_coord))
    nm = len(_agent_memory(realm_root, aid))
    mine = [("goals", "target", ng), ("memories", "brain", nm),
            ("active jobs", "clock-play", active_jobs)]
    reach = [(label, icon, c[kind]) for kind, icon, label in
             (("connectors", "cap-connector", "connectors"), ("extensions", "puzzle", "extensions"),
              ("skills", "cap-skill", "skills"), ("plugins", "cap-plugin", "plugins"))]

    def chip(label, icon, n):
        return (f'<span title="{n} {label}" style="display:inline-flex;align-items:center;gap:4px;'
                f'font-size:11.5px;color:var(--text-dim)">'
                f'<span style="display:flex;color:var(--text-soft)">'
                f'{_icon(icon,13)}</span>{n}</span>')
    left = "".join(chip(*it) for it in mine)
    right = "".join(chip(*it) for it in reach)
    return (f'<div style="display:flex;align-items:center;gap:16px;border-top:1px solid var(--color-divider);'
            f'padding-top:8px;margin-top:2px">{left}'
            f'<span style="margin-left:auto;display:inline-flex;align-items:center;gap:16px">{right}</span></div>')


def _realm_ministers(realm, realm_root, today) -> str:
    cards = ""
    now = clock.now()
    for a in ([realm.coordinator] if realm.coordinator else []) + realm.members:
        # The last seven days, rolled up across everything this agent owns. This is a log, not a
        # plan: on a card the strip answers "how has it been going", and every square is a day that
        # has already happened, so day initials would only be repeating what the tooltips say.
        week = (f'<div style="display:flex;justify-content:flex-end" '
                f'title="Job outcomes, last 7 days">{_agent_week_strip(realm_root, a, now)}</div>')
        # Was a word-shaped pill beside the name. The role is a property of the agent and it shows
        # up in four lists; the laurel says it once, in the space a badge takes.
        coordtag = (' ' + _coord_mark(16, tip=True)) if a.is_coordinator else ''
        profile = (f'<div style="font-size:11.5px;color:var(--text-dim);font-style:italic;'
                   f'margin-top:8px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden">{E(a.leader)}</div>') if a.leader else ""
        # Appointed sits under the avatar, icon over date. It was pushed to the far end of the
        # footer, where it competed with the tallies for the eye without belonging to them — it is
        # a fact about the person, so it lives with the portrait. Stacked rather than side by side
        # because the avatar column is 44px wide and a date is not.
        appointed = (f'<div title="Appointed {E(a.appointed)}" style="display:flex;flex-direction:column;'
                     f'align-items:center;gap:1px;margin-top:6px;'
                     f'color:var(--text-faint)">'
                     f'<span style="display:flex">{_icon("agreement", 14)}</span>'
                     f'<span style="font-family:ui-monospace,Menlo,monospace;font-size:10px;white-space:nowrap">'
                     f'{E(_fmt_date_short(a.appointed))}</span></div>') if a.appointed else ""
        cards += (f'<a href="/agent/{E(a.id)}" class="mc-agent mc-frame" style="text-decoration:none;color:inherit;'
                  f'border-radius:var(--r);padding:12px 14px;display:flex;flex-direction:column;gap:8px;background:var(--color-bg);height:250px">'
                  # Two columns: the portrait (with its appointment) and everything else. The strip
                  # FLOATS to the top-right of that second column rather than being a third column
                  # of its own, so only the lines tall enough to collide with it are narrowed — the
                  # name — and the role, model and profile run the column's full width underneath.
                  # As a column the strip squeezed every line below it too, which is what broke
                  # "THE HAND (PRIME MINISTER)" across two lines in a card with room to spare.
                  # The portrait column stays, so none of it runs to the card's left edge.
                  f'<div style="display:flex;gap:12px;align-items:flex-start;flex:1;min-height:0;overflow:hidden">'
                  f'<div style="flex:none">{_portrait(realm_root, a, 44, dot=True)}{appointed}</div>'
                  f'<div style="flex:1;min-width:0;overflow:hidden">'
                  f'<div style="float:right;margin:2px 0 4px 10px">{week}</div>'
                  f'<div style="display:flex;align-items:center;gap:7px">'
                  f'<span style="display:inline-flex;align-items:center;gap:5px;'
                  f'font-family:var(--font-heading);font-weight:600;font-size:16px">{E(a.display)}{coordtag}</span>'
                  f'{_autonomy_badge(_autonomy_of(realm_root, a.id), 14)}</div>'
                  f'<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--color-accent-700);margin-top:2px">{E(a.theme_role)}</div>'
                  f'<div style="margin-top:6px">{_model_chip(*_agent_model_effort(realm, realm_root, a.id))}</div>'
                  f'{profile}</div></div>'
                  f'{_cap_count_row(realm_root, a.id, is_coord=a.is_coordinator, active_jobs=sum(1 for j in a.jobs if j.enabled))}</a>')
    grid = f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px">{cards}</div>'
    add = ('<button class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px;cursor:pointer" '
           'onclick="mcOpenAppoint()">+ Appoint</button>')
    scripts = (_appoint_modal(realm) + _APPOINT_JS + _NEW_JS + _AUTONOMY_JS + _AGENT_COLOR_JS
               + _consumption_js(realm, "n-model", "n-effort", "n-consmarker", "#n-cons"))
    # A reference, not the text. This page is a roster you scan to pick someone; the Covenant is
    # ~3k characters and would take it over. But "what do these eight have in common" is a fair
    # question to ask while looking at all eight, so the answer is one line away.
    cov = ""
    _tp = Path(realm_root) / "tenets.md"
    try:
        _has_cov = _tp.is_file() and bool(_tp.read_text(encoding="utf-8-sig").strip())
    except OSError:
        _has_cov = False
    if _has_cov:
        cov = (f'<a href="/memory" style="display:inline-flex;align-items:center;gap:6px;'
               f'text-decoration:none;font-size:11.5px;margin:0 0 12px;'
               f'color:var(--text-muted)">'
               f'<span style="display:flex;color:var(--color-accent-2)">{_icon("agreement",14)}</span>'
               f'Every {E(realm.theme_agent.lower())} is bound by the Covenant '
               f'<span style="color:var(--color-accent-2)">›</span></a>')
    return (f'<div style="padding:18px 24px 24px"><div style="display:flex;align-items:center;margin-bottom:8px">'
            f'{_page_title(realm.theme_agent + "s", f"{len(realm.members)} + 1 {realm.theme_coordinator}")}'
            f'<span style="margin-left:auto">{add}</span></div>{cov}{grid}</div>{scripts}')


_SORT_IC = f'<span style="opacity:.6;display:inline-flex;vertical-align:middle;margin-left:2px">{_icon("sort",12)}</span>'


def _jobs_view_toggle() -> str:
    """List / calendar selector — borderless icons, sits at the start of a filter row. Used by both
    the User and the System pane, which is the point: one Jobs page, one set of views."""
    def vbtn(v, icon, title, active):
        on = ("background:var(--text-9);color:var(--color-text)"
              if active else "background:transparent;color:var(--text-soft)")
        return (f'<button class="mc-jv" data-v="{v}" onclick="mcJobsView(\'{v}\',this)" title="{title}" '
                f'style="border:0;cursor:pointer;padding:5px 8px;border-radius:var(--r);display:inline-flex;align-items:center;{on}">{icon}</button>')
    return (f'<div style="display:inline-flex;gap:2px;margin-right:6px">'
            f'{vbtn("list", _icon("list", 16), "List view", True)}{vbtn("cal", _icon("calendar", 16), "Calendar view", False)}</div>')


def _sysjob_every(mins: int) -> str:
    """A system job's interval in the same shorthand the Cadence column uses for cron jobs."""
    if mins < 60:
        return "every minute" if mins == 1 else f"every {mins} min"
    h = mins // 60
    if h % 24 == 0:
        d = h // 24
        return {1: "daily", 7: "weekly"}.get(d) or f"every {d} days"
    return "hourly" if h == 1 else f"every {h}h"


def _sysjob_next(iso_ts: str, due_now: bool, now) -> str:
    """When this job will actually run next: 'Mon 9/21, 20:00'.

    It used to say "due now", which describes the scheduler's internal state rather than answering
    the question the column asks. A job whose time has passed runs on the daemon's next sweep — a
    minute away — so that is what we say, and everything else gets a wall-clock time you can plan
    around rather than a relative "in 2d".
    """
    if due_now:
        return "any moment"
    if not iso_ts:
        return "—"
    try:
        t = datetime.datetime.fromisoformat(iso_ts)
    except ValueError:
        return "—"
    if t.tzinfo is None:
        t = t.astimezone()
    # %-m/%-d is not portable to Windows; build the date parts by hand.
    return f"{t:%a} {t.month}/{t.day}, {t:%H:%M}"


def _sysjob_when(iso_ts: str, now) -> str:
    """'3h ago' / 'in 2d' / '—'. Rendered server-side so the row is complete without JavaScript."""
    if not iso_ts:
        return "—"
    try:
        t = datetime.datetime.fromisoformat(iso_ts)
    except ValueError:
        return "—"
    if t.tzinfo is None:
        t = t.astimezone()
    secs = (now - t).total_seconds()
    ahead = secs < 0
    secs = abs(secs)
    if secs < 60:
        return "just now" if not ahead else "any moment"
    if secs < 3600:
        v = f"{round(secs / 60)}m"
    elif secs < 86400:
        v = f"{round(secs / 3600)}h"
    else:
        v = f"{round(secs / 86400)}d"
    return f"in {v}" if ahead else f"{v} ago"


def _system_job_row(j, now, grid: str) -> str:
    """One system job, in the same row as a user job — minus the parts that don't apply.

    Same grid, same fonts, same week strip. What is missing is missing for a reason: no Owner
    (they are all ARMADA, and a column of identical values is decoration), no expand (there is no
    prompt to read and no run history page behind it), and no Last run column — the week strip
    carries the last few days, which is more than a single timestamp ever said.
    """
    free = j.get("cost") != "quota"
    warn = ("background:var(--status-warn-16);color:var(--status-warn);"
            "display:inline-flex;align-items:center;gap:4px")
    ok = "background:var(--status-ok-16);color:var(--status-ok)"
    # Word-for-word the user list's pills, including the dial glyph: the same cost means the same
    # thing on both tabs, and two spellings of it invites the question of whether it does.
    pill = (f'<span class="mc-cap-pill" title="Runs locally — no model call" style="{ok}">free</span>'
            if free else
            f'<span class="mc-cap-pill" title="Spends your Claude subscription" style="{warn}">'
            f'<span style="display:flex;flex:none">{_icon("quota", 11)}</span>uses quota</span>')
    on = bool(j.get("enabled"))
    nxt = "off" if not on else _sysjob_next(j.get("next_due") or "", bool(j.get("due_now")), now)
    nxt_style = ("color:var(--text-muted)" if not on
                 else "color:var(--text-strong)")
    week7 = _sysjob_health7(j.get("runs"), now, on)
    week = "".join(_health_square(label, _health_tip(day, dt, label, wknd))
                   for day, dt, label, wknd in week7)
    # Read from the strip, exactly as the user jobs are: one definition of what a row's status is.
    bucket = _week_filter_bucket(week7)
    toggle = (f'<label class="mc-toggle" onclick="event.stopPropagation()" '
              f'title="{"On — click to stop it running on its schedule" if on else "Off — click to let it run again"}">'
              f'<input type="checkbox" {"checked" if on else ""} '
              f'onchange="mcSysJobToggle(this,{_J(j["id"])})">'
              f'<span class="mc-toggle-sl"></span></label>')
    # Dead while the job is off, for the same reason as a user job: the switch beside it already
    # says this job does not run, and a live button that runs it contradicts the switch.
    run = (f'<button class="btn btn-primary" style="color:#fff;font-size:12px;padding:5px 11px;'
           f'display:inline-flex;align-items:center;gap:5px'
           f'{"" if on else ";opacity:.45;cursor:not-allowed"}" '
           f'{"" if on else "disabled "}'
           f'title="{"Run this job now" if on else "This job is switched off — switch it on to run it"}" '
           f'onclick="mcSysJobRun(this,{_J(j["id"])})">{_icon("play",12)}Run now</button>')
    detail = str(j.get("detail") or "")
    return (f'<div class="mc-job mc-sysjob" data-sysjob="{E(j["id"])}" '
            f'data-owner="system" data-cost="{E(j.get("cost") or "")}" '
            f'data-name="{E(str(j.get("name") or j["id"]).lower())}" '
            f'data-status="{bucket}" data-jstatus="{bucket}" '
            f'data-cadence="{E(_sysjob_every(int(j.get("every_minutes") or 0)))}" '
            f'data-jcad="{_sysjob_cadence_bucket(int(j.get("every_minutes") or 0))}" '
            f'data-next="{E(str(j.get("next_due") or "zzzz"))}" '
            f'style="display:grid;{grid};gap:8px;align-items:center;padding:9px 10px;'
            f'border-bottom:1px solid var(--color-divider)'
            f'{"" if on else ";opacity:.55"}">'
            f'<span style="min-width:0">'
            # No caret, but the same indent: two lists whose titles start at different x are two
            # lists, however alike everything to the right of them is.
            f'<span style="display:flex;align-items:baseline;gap:6px">'
            f'<span style="display:inline-flex;flex:none;width:14px"></span>'
            f'<span style="font-family:var(--font-heading);font-weight:600;font-size:14px">'
            f'{E(j.get("name") or j["id"])}</span></span>'
            f'<span style="display:block;margin-left:20px;font-size:11.5px;line-height:1.4;'
            f'color:var(--text-muted)">{E(j.get("description") or "")}</span>'
            + (f'<span style="display:block;margin-left:20px;font-size:11px;line-height:1.4;'
               f'color:var(--text-muted)">{E(detail)}</span>' if detail else "")
            + f'<span class="mc-sysjob-msg" data-for="{E(j["id"])}" style="display:none;'
              f'margin-left:20px;font-size:11.5px;color:var(--text-muted);margin-top:4px"></span>'
            f'</span>'
            f'<span class="mono" style="font-size:11.5px;color:var(--text-dim)">'
            f'{E(_sysjob_every(int(j.get("every_minutes") or 0)))}</span>'
            f'<span>{pill}</span>'
            f'<span style="font-size:12px;white-space:nowrap;{nxt_style}" data-next-cell>{E(nxt)}</span>'
            f'<span style="white-space:nowrap" data-week>{week}</span>'
            f'<span style="justify-self:end">{run}</span>'
            f'<span style="display:flex;gap:6px;align-items:center;justify-self:end">{toggle}</span></div>')


def _system_jobs_table(realm_root, now) -> tuple[str, int]:
    """The System pane's list — the User jobs list, over ARMADA's own upkeep work.

    It was a <table> while User jobs were expandable rows, which is how the same two facts came to
    be laid out two different ways on two tabs of one page. Same renderer shape now, same header,
    same columns bar the ones that don't apply.
    """
    jobs = []
    try:
        from .. import sysjobs as _sj
        jobs = _sj.status(realm_root)
    except Exception:  # noqa — a broken state file must not take the page down
        swallowed(log, '_system_jobs_table: failed; using a default')
        jobs = []
    rows = "".join(_system_job_row(j, now, _SYSJOB_GRID) for j in jobs)
    return (f'<div id="mc-sysjobstable" class="mc-joblist mc-frame" '
            f'style="border-radius:var(--r);overflow:hidden">'
            f'{_system_jobs_header(now.date())}{rows}</div>'), len(jobs)


def _system_jobs_header(today) -> str:
    """The User list's header, minus Owner, plus a column for Run now."""
    def hcol(label, key):
        return (f'<span onclick="mcSortJobs(this,\'{key}\',\'mc-sysjobstable\')" '
                f'style="cursor:pointer;user-select:none">{label} '
                f'<span style="opacity:.6;display:inline-flex;vertical-align:middle;margin-left:2px">'
                f'{_icon("sort",12)}</span></span>')
    return (f'<div style="display:grid;{_SYSJOB_GRID};gap:8px;padding:6px 10px 6px 28px;'
            f'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;'
            f'color:var(--text-muted);border-bottom:1px solid var(--color-divider)">'
            f'{hcol("Job","name")}{hcol("Cadence","cadence")}{hcol("Cost","cost")}'
            f'{hcol("Next run","next")}'
            f'<span style="text-transform:none;letter-spacing:0;font-weight:600">{_health7_header(today)}</span>'
            f'<span></span><span style="justify-self:end">On/Off</span></div>')


# --------------------------------------------------------------------------- the one job list
# The realm Jobs page and an agent's Jobs tab were two lists of the same thing. One was a sortable
# table with a Created column and a last-run dot; the other was expandable rows with cost, next run,
# a week strip and an on/off switch. The same job read differently depending on which door you came
# in by, and only one of the two let you do anything to it. They are one renderer now. The realm
# page adds Kind and Owner — the two facts an agent's own page answers by being that agent's page —
# and everything else, including the column widths, is shared.
_JOB_TAIL = "108px 96px 132px 100px 56px"        # cadence · cost · next run · week strip · on
_JOB_GRID = f"grid-template-columns:1fr {_JOB_TAIL}"
_JOB_GRID_OWNED = f"grid-template-columns:1fr 62px 108px {_JOB_TAIL}"
# System jobs: the same columns minus Owner/Kind, plus one for Run now — a system job has no
# expanded view to put the button in, and "run this now" is the main thing you do to one.
_SYSJOB_GRID = "grid-template-columns:1fr 108px 96px 132px 100px 104px 56px"


def _job_token_estimate(jruns) -> tuple[int, int]:
    """(median total tokens per run, sample size) from this job's own telemetry.

    Median rather than mean: one outlier run — a first run that wrote the whole context into cache,
    a run that hit an error after a long tool chain — would otherwise set the expectation for every
    future one. Returns (0, 0) when the job has never run, and the caller says so rather than
    inventing a number from the prompt length.
    """
    vals = sorted(int((ev.get("tokens") or {}).get("total") or 0)
                  for ev in jruns if (ev.get("tokens") or {}).get("total"))
    if not vals:
        return 0, 0
    n = len(vals)
    return (vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) // 2), n


def _job_cost_pill(kind: str, tokens: int, n: int) -> str:
    """What one run of this job costs you, in the same language the System jobs list uses.

    A command job is deterministic and local, so it is free in the same sense theirs are. An agent
    job spends the subscription, and where we have run history we say roughly how much instead of
    only that it costs something — "uses your quota" is true of every agent job and therefore tells
    you nothing about which one to switch off.
    """
    if kind == "command":
        return (f'<span class="mc-cap-pill" title="Runs a local command — no model call" '
                f'style="background:var(--status-ok-16);'
                f'color:var(--status-ok)">free</span>')
    warn = ("background:var(--status-warn-16);color:var(--status-warn);"
            "display:inline-flex;align-items:center;gap:4px")
    dial = f'<span style="display:flex;flex:none">{_icon("quota", 11)}</span>'
    if not n:
        return (f'<span class="mc-cap-pill" title="Spends your Claude subscription. No runs yet, '
                f'so there is nothing to estimate from." style="{warn}">{dial}uses quota</span>')
    t = f"{tokens / 1000:.0f}k" if tokens >= 1000 else str(tokens)
    plural = "" if n == 1 else "s"
    return (f'<span class="mc-cap-pill" title="Median of {n} recorded run{plural} — typical, not a cap" '
            f'style="{warn}">{dial}≈{t} / run</span>')


def _job_list_header(today, show_owner: bool, list_id: str) -> str:
    grid = _JOB_GRID_OWNED if show_owner else _JOB_GRID
    def hcol(label, key):
        return (f'<span onclick="mcSortJobs(this,\'{key}\',\'{list_id}\')" style="cursor:pointer;user-select:none">'
                f'{label} <span style="opacity:.6;display:inline-flex;vertical-align:middle;margin-left:2px">'
                f'{_icon("sort",12)}</span></span>')
    extra = (hcol("Kind", "kind") + hcol("Owner", "owner")) if show_owner else ""
    # Bold, matching the System list's header — the two were the same list drawn twice, and the
    # lighter weight here made the column names read as data rather than as headings.
    return (f'<div style="display:grid;{grid};gap:8px;padding:6px 10px 6px 28px;font-size:11px;'
            f'font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);'
            f'border-bottom:1px solid var(--color-divider)">{hcol("Job","name")}{extra}'
            f'{hcol("Cadence","cadence")}{hcol("Cost","cost")}{hcol("Next run","next")}'
            f'<span style="text-transform:none;letter-spacing:0;font-weight:600">{_health7_header(today)}</span>'
            # The switch column had no name at all, so the one control in the row that changes
            # whether a job runs was the only thing on the page you had to guess at.
            f'<span style="justify-self:end">On/Off</span></div>')


# The expanded view's run log. Seven because that is what the row's strip covers and what anyone
# asking "has this been working" wants to see, not because a week has seven days — this is a list
# of runs, and a job that runs hourly fills it in an afternoon.
_RUN_LOG_ROWS = 7


def _job_row(realm_root, a, j, now, runs_all, running, show_owner: bool, open_job: str = "") -> str:
    """One job, expandable, identical on both pages bar the Kind and Owner cells."""
    grid = _JOB_GRID_OWNED if show_owner else _JOB_GRID
    jc = _job_prompt(realm_root, a.id, j.id)
    _run = jc.get("run")
    if isinstance(_run, list):                        # command jobs may store an argv list
        _run = " ".join(str(x) for x in _run)
    prompt = E(jc.get("prompt") or _run or "(no prompt)")
    created = _job_created(realm_root, a.id, j.id, jc)
    on = j.enabled
    jcad = _cadence_bucket(j.cadence)
    jruns = [ev for ev in runs_all if ev.get("task") == j.id]
    tok, nruns = _job_token_estimate(jruns)
    cost_pill = _job_cost_pill(j.kind, tok, nruns)
    # Kind only earns a column where a list mixes owners. On one agent's page the inline tag says
    # the same thing in less space.
    kind_tag = ('<span class="tag mc-frame" style="font-size:9.5px;padding:0 5px;margin-left:5px">cmd</span>'
                if (j.kind == "command" and not show_owner) else "")
    # Next run, not last run: the last one is already in the week strip and in the history below,
    # whereas when it fires next is the thing the row could not tell you at all.
    _nd = None
    if not on:
        nxt_txt, nxt_style = "off", "color:var(--text-muted)"
    elif j.id in running:
        nxt_txt, nxt_style = "running now", f"color:{_RUNNING_COLOR}"
    else:
        _nd = _job_next_dt(j.cadence, now.replace(tzinfo=None))
        if _nd:
            nxt_txt = f"{_nd:%a} {_nd.month}/{_nd.day}, {_nd:%H:%M}"
            nxt_style = "color:var(--text-strong)"
        else:
            nxt_txt, nxt_style = "on demand", "color:var(--text-muted)"
    week7 = _job_health7(jruns, j.cadence, now, j.id in running,
                         since=_job_created_ts(realm_root, a.id, j.id, jc))
    week = "".join(_health_square(label, _health_tip(day, dt, label, wknd))
                   for day, dt, label, wknd in week7)
    # The filter reads the same strip the row draws, rather than last_status — see
    # _week_filter_bucket for what that mismatch did.
    jstatus = _week_filter_bucket(week7)
    toggle = (f'<label class="mc-toggle" onclick="event.stopPropagation()" '
              f'title="{"On — click to stop it running on its schedule" if on else "Off — click to let it run again"}">'
              f'<input type="checkbox" {"checked" if on else ""} '
              f'onchange="mcJobEnable(this,{_J(a.id)},{_J(j.id)})">'
              f'<span class="mc-toggle-sl"></span></label>')
    owner_cells = ""
    if show_owner:
        owner_cells = (f'<span style="font-size:11.5px;color:var(--text-dim)">'
                       f'{"cmd" if j.kind == "command" else "agent"}</span>'
                       f'<span style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                       f'{E(a.display)}</span>')
    summary_row = (
        f'<summary style="display:grid;{grid};gap:8px;align-items:center;padding:9px 10px;cursor:pointer;'
        f'list-style:none">'
        f'<span style="min-width:0">'
        f'<span style="display:flex;align-items:baseline;gap:6px">'
        # chevron-right, the same glyph the capability rows use. CHEVR is the up/down "unfold"
        # pair and was never the disclosure icon on either page.
        f'<span class="mc-jcaret" style="display:inline-flex;flex:none;align-self:center;'
        f'color:var(--text-muted)">{_icon("chevron-right", 14)}</span>'
        f'<span style="font-family:var(--font-heading);font-weight:600;font-size:14px">{E(j.name)}</span>'
        f'{kind_tag}</span>'
        # The summary sits under the title rather than beside it: the row already spends its width
        # on cadence, cost and next-run, and a sentence competing with three columns is what made
        # the name column feel cramped.
        + (f'<span style="display:block;margin-left:18px;font-size:11.5px;line-height:1.4;'
           f'color:var(--text-muted)">{E(j.summary)}</span>'
           if j.summary else "")
        + f'</span>{owner_cells}'
        f'<span class="mono" style="font-size:11.5px;color:var(--text-dim)">'
        f'{_humanize(j.cadence)}</span>'
        f'<span>{cost_pill}</span>'
        f'<span style="font-size:12px;white-space:nowrap;{nxt_style}">{E(nxt_txt)}</span>'
        f'<span style="white-space:nowrap">{week}</span>'
        f'<span style="display:flex;gap:6px;align-items:center;justify-self:end">{toggle}</span></summary>')
    # The last seven runs, newest first — a plain log, not the week strip again. The strip in the
    # collapsed row answers "how has the schedule been going" and already has a Missed square for a
    # day nothing ran; repeating it here said the same thing twice and said nothing about the runs
    # themselves. Fewer than seven rows means the job has run fewer than seven times.
    hist_rows = [ev for ev in jruns][-_RUN_LOG_ROWS:][::-1]
    hist = "".join(f'<tr><td class="mono" style="font-size:11px">{E(_fmt_ts(ev.get("ts","")))}</td>'
                   f'<td style="color:{status.color(ev.get("status",""))};font-size:11.5px">'
                   f'{E(str(ev.get("status","")))}</td>'
                   f'<td style="font-size:11.5px">{E(str(ev.get("summary",""))[:90])}</td></tr>'
                   for ev in hist_rows) \
           or '<tr><td colspan=3 style="font-size:11.5px;color:var(--text-muted)">no runs yet</td></tr>'
    # The prompt is shown, not offered for editing. A read-only <textarea> still looks exactly like
    # a field you can type in — people tried, and nothing happened. A <pre> reads as content;
    # resize:vertical + overflow:auto keep the drag handle and the scroll.
    body = (f'<div style="padding:4px 10px 16px 28px">'
            f'<pre class="mc-prompt" style="width:100%;min-height:120px;max-height:420px;resize:vertical;'
            f'overflow:auto;margin:0;background:color-mix(in srgb,var(--color-text) 3%,transparent);'
            f'border:1px solid var(--color-divider);border-left:3px solid var(--color-sand-500);'
            f'border-radius:var(--r);padding:10px 12px;white-space:pre-wrap;word-break:break-word;'
            f'font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;line-height:1.55;'
            f'color:color-mix(in srgb,var(--color-text) 85%,transparent)">{prompt}</pre>'
            # Run now is dead while the job is off. The switch says "this job does not run"; a live
            # button beside it that runs the job says otherwise, and one of the two has to be wrong.
            # Switching it back on is one click away, which is what the tooltip says.
            f'<div style="margin:8px 0;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" style="color:#fff;font-size:12px;padding:5px 11px;'
            f'display:inline-flex;align-items:center;gap:5px'
            f'{"" if on else ";opacity:.45;cursor:not-allowed"}" '
            f'{"" if on else "disabled "}'
            f'title="{"Run this job now" if on else "This job is switched off — switch it on to run it"}" '
            f'onclick="mcRun({_J(a.id)},{_J(j.id)},\'claude\',this)">{_icon("play",12)}Run now</button>'
            f'<a href="/job/{E(a.id)}/{E(j.id)}" class="btn btn-secondary" style="font-size:12px;padding:5px 11px;'
            f'text-decoration:none;display:inline-flex;align-items:center;gap:5px">{_icon("edit",12)}Edit job</a>'
            # Delete sits beside Edit, inside the expanded view: it belongs with the other things
            # you do to a job you have opened and read, not one stray click away in a collapsed row
            # you were only scrolling past.
            f'<button class="btn btn-secondary" onclick="mcDeleteJob(this,{_J(a.id)},{_J(j.id)},{_J(j.name)})" '
            f'style="font-size:12px;padding:5px 11px;color:var(--status-bad);'
            f'display:inline-flex;align-items:center;gap:5px">{_icon("trash",12)}Delete job</button>'
            f'<span class="mc-runmsg" style="font-size:12px;color:var(--text-muted)"></span></div>'
            f'<pre class="mc-out" style="display:none;background:var(--color-sand-100);'
            f'border:1px solid var(--color-sand-300);color:var(--color-text);border-radius:var(--r);'
            f'padding:10px;white-space:pre-wrap;max-height:320px;overflow:auto;resize:vertical;'
            f'font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px"></pre>'
            + f'<div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;'
            f'color:var(--text-faint);margin:12px 0 4px">'
            f'Last {_RUN_LOG_ROWS} runs</div>'
            f'<table class="table">'
            f'<thead><tr><th>When</th><th>Status</th><th>Summary</th></tr></thead>'
            f'<tbody>{hist}</tbody></table></div>')
    is_open = " open" if (open_job and j.id == open_job) else ""
    off_cls = "" if on else " mc-job-off"
    # Two sets of attributes: sort keys (what the column shows) and filter buckets (what the
    # dropdowns offer). Cost and next-run sort numerically — zero-padded so a string compare is a
    # number compare — because "≈14k / run" and "Mon 9/21, 20:00" do not sort as themselves.
    return (f'<details class="mc-job{off_cls}" id="job-{E(j.id)}" data-jid="{E(j.id)}" '
            f'data-name="{E(j.name.lower())}" data-cadence="{E(_humanize(j.cadence))}" '
            f'data-created="{E(created)}" data-status="{E((j.last_status or "zzz").lower())}" '
            f'data-cost="{tok:012d}" data-next="{E(_nd.isoformat() if _nd else "zzzz")}" '
            f'data-kind="{"cmd" if j.kind == "command" else "agent"}" '
            f'data-owner="{E(a.id)}" data-ownername="{E(a.display.lower())}" '
            f'data-jstatus="{jstatus}" data-jcad="{jcad}" '
            f'style="border-bottom:1px solid var(--color-divider)"{is_open}>{summary_row}{body}</details>')


def _job_list(realm, realm_root, pairs, today, now, show_owner: bool = False,
              list_id: str = "mc-joblist", open_job: str = "") -> str:
    """Header + rows for a set of (agent, job) pairs. `pairs` rather than one agent so the realm
    page can pour every agent's jobs into the same list."""
    rows = ""
    cache: dict[str, tuple] = {}
    for a, j in pairs:
        if a.id not in cache:
            cache[a.id] = (_runs(realm_root, a.id), _running_jobs(realm_root, a.id))
        runs_all, running = cache[a.id]
        rows += _job_row(realm_root, a, j, now, runs_all, running, show_owner, open_job)
    return (f'<div id="{list_id}" class="mc-joblist mc-frame" style="border-radius:var(--r);overflow:hidden">'
            f'{_job_list_header(today, show_owner, list_id)}{rows}</div>')


def _realm_jobs(realm, realm_root, today) -> str:
    from .. import scheduler as S
    try:
        now = S.now_in(S._load_json(Path(realm_root) / "realm.json"))
    except Exception:  # noqa — fall back to OS-local time
        swallowed(log, '_realm_jobs: failed; using a default')
        now = clock.now()
    today = now.date()
    owners = []            # (id, display) for agents that own ≥1 job — populates the Owner filter
    pairs = []
    for a in realm.agents:
        if not a.jobs:
            continue
        owners.append((a.id, a.display))
        pairs += [(a, j) for j in a.jobs]
    # The same list an agent's own Jobs tab shows, plus Kind and Owner. Expanding stays on this
    # page; Edit goes to the job's page, exactly as it does from the agent.
    table = _job_list(realm, realm_root, pairs, today, now, show_owner=True,
                      list_id="mc-jobstable")
    n = sum(len(a.jobs) for a in realm.agents)
    filters = _jobs_filter_bar(owners, n, now, lead=_jobs_view_toggle()) if n else ""
    legend = (f'<div style="display:flex;justify-content:flex-end;margin:0 0 8px">{_status_legend()}</div>' if n else "")
    # the calendar simply replaces the list; filters + legend stay above both. No bottom legend
    # on the calendar here — the status legend already shows above it.
    list_view = f'<div class="mc-jobs-list">{table}</div>'
    cal_view = (f'<div class="mc-jobs-cal" style="display:none;height:72vh">'
                f'{_jobcal(realm, realm_root, today, legend=False, widget=False, fpfx="jf")}</div>'
                if n else "")
    proposals = _job_proposals_block(realm, realm_root)
    # User / System tabs, mirroring Capabilities. Proposals and approvals stay under User: they're
    # about your agents, not about the app keeping itself current.
    tabs = ('<div style="display:flex;gap:2px;border-bottom:1px solid var(--color-divider);'
            'margin:10px 0 16px">'
            '<a id="jobs-tab-user" class="mc-captab" onclick="mcJobsTab(\'user\')">User</a>'
            '<a id="jobs-tab-system" class="mc-captab" onclick="mcJobsTab(\'system\')">System</a></div>')
    user_pane = (f'<div id="jobs-pane-user" class="mc-jobspane">{proposals}{filters}{legend}{list_view}{cal_view}</div>')
    sys_pane = (f'<div id="jobs-pane-system" class="mc-jobspane" style="display:none">'
                f'{_system_jobs_pane(realm, realm_root, today, now)}</div>')
    tab_js = _JOBSTAB_JS
    return (f'<div style="padding:18px 24px 24px">{_page_title("Jobs", f"{n} across the realm")}'
            f'{_hold_banner(realm_root)}{tabs}{user_pane}{sys_pane}'
            f'{_FDROP_JS}{_JOBS_FILTER_JS}{_JOBCAL_JS}{_JOBS_SORT_JS}</div>'
            f'{tab_js}{_health_styles_js()}{_SYSJOBS_JS}')


def _hold_banner(realm_root) -> str:
    """Why this realm's scheduled jobs aren't running, where the owner looks for them.

    A held scheduler used to be visible only in a preflight summary after saving a setting — "my jobs
    stopped" with nothing on the Jobs page to say why. For an adopted realm (5.8c) it also lists
    every command job verbatim, because that list is what the owner is being asked to allow."""
    from .. import preflight
    why = preflight.hold_reason(realm_root)
    if not why:
        return ""
    rv = preflight.adopt_review(realm_root)
    box = ("margin:0 0 14px;padding:12px 14px;border:1px solid var(--status-warn);border-radius:var(--r);"
           "background:var(--status-warn-16)")
    head = (f'<div style="display:flex;align-items:center;gap:10px"><b style="font-size:13px">'
            f'Scheduled jobs are paused</b><span style="font-size:12.5px;color:var(--text-dim)">{E(why)}</span>')
    if not rv:
        return (f'<div style="{box}">{head}</div>'
                '<div style="font-size:12px;color:var(--text-muted);margin-top:4px">Fix it under '
                'Settings → Realm; the jobs resume on their own once it passes.</div></div>')
    rows = "".join(
        f'<li style="margin:4px 0"><b>{E(c.get("name") or c.get("job"))}</b> '
        f'<span style="color:var(--text-muted)">({E(c.get("agent"))})</span>'
        f'<pre style="margin:3px 0 0;padding:6px 8px;background:var(--color-bg);border:1px solid '
        f'var(--color-divider);border-radius:var(--r);font-size:11.5px;white-space:pre-wrap;'
        f'word-break:break-all">{E(c.get("run"))}</pre></li>'
        for c in (rv.get("command_jobs") or []))
    n_ag = int(rv.get("agent_jobs") or 0)
    body = ('<div style="font-size:12.5px;margin-top:8px">This realm was added from an existing '
            'folder, so it hasn’t run here before. Nothing runs until you allow it.</div>'
            + (f'<div style="font-size:12.5px;margin-top:8px">Commands it will run on this computer:'
               f'<ul style="margin:4px 0 0;padding-left:18px">{rows}</ul></div>' if rows else "")
            + (f'<div style="font-size:12.5px;margin-top:6px">Plus {n_ag} agent job'
               f'{"s" if n_ag != 1 else ""} (prompts its agents run with their tools).</div>' if n_ag else "")
            + '<div style="margin-top:10px"><button class="btn btn-primary" style="color:#fff;'
              'font-size:12.5px;padding:6px 14px" onclick="mcAdoptRelease(this)">Review done — '
              'let them run</button></div>')
    return f'<div style="{box}">{head}</div>{body}</div>{_ADOPT_JS}'


_SYSJOB_COST_FILTERS = [("free", "Free"), ("quota", "Uses your quota")]


def _system_jobs_pane(realm, realm_root, today, now) -> str:
    """The System tab: the same list and calendar views as User jobs, over ARMADA's own upkeep work.

    The one deliberate difference is the first filter dropdown — system jobs all have the same
    owner (the app), so it filters on cost instead, which is the thing you actually want to slice
    them by."""
    table, n = _system_jobs_table(realm_root, now)
    explainer = ('<div style="font-size:13px;color:var(--text-muted);line-height:1.6;max-width:1100px;'
                 'margin:0 0 14px">'
                 '<div>Recurring work ARMADA does to keep itself current — refreshing the model '
                 'catalogue, checking capabilities for updates, pruning old history.</div>'
                 '<div>System jobs ship inside the app and can\'t be edited or deleted, but you can '
                 'switch one off or run it now. Each says what it costs.</div></div>')
    if not n:
        return explainer + '<div style="font-size:12.5px;color:var(--text-muted)">No system jobs in this build.</div>'
    filters = _jobs_filter_bar(_SYSJOB_COST_FILTERS, n, now, lead=_jobs_view_toggle(), pfx="sf",
                               table="mc-sysjobstable", f1key="cost", f1_label="Any cost")
    legend = f'<div style="display:flex;justify-content:flex-end;margin:0 0 8px">{_status_legend()}</div>'
    cal_note = ('<div style="font-size:11.5px;color:var(--text-muted);margin-top:8px">'
                'Shows recorded runs and upcoming due times. Jobs that run more often than hourly '
                'aren\'t plotted, and days before this realm started keeping system-job history '
                'stay blank rather than being guessed.</div>')
    cal_view = (f'<div class="mc-jobs-cal" style="display:none">'
                f'<div style="height:72vh">{_jobcal(realm, realm_root, today, legend=False, widget=False, scope="system", fpfx="sf", title="System job calendar")}</div>'
                f'{cal_note}</div>')
    return f'{explainer}{filters}{legend}<div class="mc-jobs-list">{table}</div>{cal_view}'


def _jobs_filter_bar(owners, n: int, now, lead: str = "", pfx: str = "jf",
                     table: str = "mc-jobstable", f1key: str = "owner",
                     f1_label: str = "All owners") -> str:
    """Owner · Last-run · Cadence dropdowns above a Jobs table (client-side filtering), plus an
    'as of' timestamp and a refresh button. `lead` is placed at the very start of the row (used
    for the list/calendar view selector). Dropdowns match the realm switcher style.

    The bar is self-describing so the User and System panes can each have one: `pfx` namespaces
    the control ids, `table` names the table it filters, and `f1key` is the row data-attribute the
    first dropdown matches on — owner for user jobs, cost for system jobs, which have one owner
    (the app) and so would get a pointless one-item list otherwise."""
    f1_opts = [("", f1_label, "")] + [(oid, disp, "") for oid, disp in owners]
    status_opts = [("", "All statuses", "")] + [(v, lbl, _STATUS_FILTER_COLOR.get(v, "")) for v, lbl in _STATUS_FILTERS]
    cad_opts = [("", "All cadences", "")] + [(v, lbl, "") for v, lbl in _CADENCE_FILTERS]
    asof = now.strftime("%a %H:%M")
    muted = "var(--text-soft)"
    refresh = (f'<div style="margin-left:auto;display:flex;align-items:center;gap:6px">'
               f'<span style="font-size:11.5px;color:{muted}">Status as of {E(asof)}</span>'
               f'<button onclick="mcJobsRefresh(this)" title="Force a status update for all jobs" '
               f'style="border:0;background:transparent;cursor:pointer;padding:4px 6px;border-radius:var(--r);'
               f'display:inline-flex;align-items:center;line-height:1;'
               f'color:var(--text-muted)">{_ICON_REFRESH}</button></div>')
    faint = "var(--text-faint)"
    search = (f'<div style="position:relative;flex:0 0 200px">'
              f'<span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);display:flex;color:{faint}">{_icon("search",14)}</span>'
              f'<input id="{pfx}-search" placeholder="Search jobs…" oninput="mcJobsFilter()" '
              f'style="{_FIELD};padding-left:30px;padding-right:26px">'
              f'<span id="{pfx}-search-x" onclick="mcJobsSearchClear(this)" title="Clear" style="display:none;position:absolute;'
              f'right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:{faint}">{_icon("x",14)}</span></div>')
    return (f'<div class="mc-jobsbar" data-pfx="{pfx}" data-table="{table}" data-f1key="{f1key}" '
            f'style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 12px">'
            f'{lead}{search}'
            f'<span style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;'
            f'color:var(--text-faint)">Filter</span>'
            f'{_filter_dropdown(f"{pfx}-f1", f1_label, f1_opts, width="150px")}'
            f'{_filter_dropdown(f"{pfx}-status", "All statuses", status_opts, width="140px")}'
            f'{_filter_dropdown(f"{pfx}-cad", "All cadences", cad_opts, width="140px")}'
            f'<button id="{pfx}-clear" onclick="mcJobsFilterClear(this)" style="display:none;align-items:center;gap:4px;'
            f'border:0;background:transparent;cursor:pointer;font-size:12px;color:var(--color-accent);padding:6px 4px">'
            f'{_icon("x",12)}Clear</button>'
            f'<span id="{pfx}-count" style="font-size:11.5px;color:{muted}">{n} of {n}</span>'
            f'{refresh}</div>')
