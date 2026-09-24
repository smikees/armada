"""Agent frame (Phase 3 split of agentpages): agent header/body + the Jobs/Inbox/Configure sub-tabs, avatar + appoint modals."""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import clock
from .. import goals as goalsmod
from ..icons import ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR
from ._base import (E, _J, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _chip, _pill, _tone, _poss,
                    _REVEAL_JS)
# Externalized inline <script> blocks (Phase 2, 2.1) — bodies live in webui/static/js/.
from ..assets import (MDFIELD_JS as _MDFIELD_JS_ASSET, A2A_TOGGLE_JS as _A2A_TOGGLE_JS,
                      JOBOPEN_JS as _JOBOPEN_JS)
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _job_next_dt, _ordinal, _next_hint, _fmt_ts)
from .agentbits import _coord_mark
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)
from .threadsview import (_agent_model_label, _chat_center, _ordered_threads, _sub, _tab_threads,
    _thread_title, _user_avatar, _user_avatar_file, _mark_thread_unread, _clear_thread_unread)
from .widgets import (_RUNNING_COLOR, _UNSCHEDULED_COLOR, _HEALTH_STYLES, _health_legend_chips, _jobcal)
from .goalsview import _tab_goals
# Shared with the realm Jobs page so the two lists compute health identically — a second
# implementation is how the same job comes to show a different week in two places.
from .realmpages import (_health_square, _health7_header, _job_health7, _status_legend,
                         _job_list, _job_cost_pill, _job_token_estimate)
from .memoryview import _tab_memory, _agent_memory
from .capabilities import (_tab_skills, _agent_toolkit, _realm_toolkit, _cap_manage_btn,
    _tool_group, _tool_row, _toolkit_from)
from ..assets import (AGENT_COLOR_JS as _AGENT_COLOR_JS, APPOINT_JS as _APPOINT_JS,
    ARTEFACTS_JS as _ARTEFACTS_JS, AUTONOMY_JS as _AUTONOMY_JS, FDROP_JS as _FDROP_JS,
    JOB_PROPOSAL_JS as _JOB_PROPOSAL_JS, JOBCAL_JS as _JOBCAL_JS, JOBS_FILTER_JS as _JOBS_FILTER_JS,
    JOBS_SORT_JS as _JOBS_SORT_JS, NEW_JS as _NEW_JS, TABLE_SORT_JS as _TABLE_SORT_JS)
from .agentcommon import (_AGENT_PALETTE, _EFFORTS, _STATUS_FILTER_COLOR, _agent_color_control, _art_meta, _autonomy_control, _effort_options, _filter_dropdown, _gather_artifacts, _job_created, _job_created_ts, _job_prompt, _job_proposals_block, _model_options, _realm_artefacts, _running_jobs)


def _agent_default_color(realm, agent_id: str) -> str:
    """The palette colour an agent falls back to (stable by its position in the realm)."""
    agents = ([realm.coordinator] if realm.coordinator else []) + list(realm.members)
    for i, a in enumerate(agents):
        if a.id == agent_id:
            return _AGENT_PALETTE[i % len(_AGENT_PALETTE)]
    return _AGENT_PALETTE[0]


def _read_md(realm_root: Path, agent_id: str, fname: str) -> str:
    f = realm_root / "agents" / agent_id / fname
    return f.read_text(encoding="utf-8-sig") if f.exists() else ""


def _agent_header(realm, realm_root, a) -> str:
    coord = a.is_coordinator
    ring = ('border:1px solid var(--color-accent-2);background:var(--color-accent-2-100)') if coord else \
           'border:1px solid var(--color-divider);background:var(--color-accent-100)'
    # model + effort: per-agent (agent.json) → realm default
    ac = {}
    aj = realm_root / "agents" / a.id / "agent.json"
    if aj.exists():
        try:
            ac = json.loads(aj.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            pass
    dmodel = getattr(realm, "default_model", "") or "Claude Opus 4.8"
    deffort = getattr(realm, "default_effort", "") or "high"
    model = ac.get("model") or dmodel
    effort = ac.get("effort") or deffort
    is_claude, disp = _model_chip_label(model)
    label = f"{disp} · {effort}"
    pill = ("display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:var(--r);"
            "background:var(--text-7);font-size:11.5px")
    model_pill = (f'<a href="/agent/{E(a.id)}/configure" title="Model &amp; effort — configure" style="{pill};text-decoration:none;color:inherit">'
                  f'{_model_mark(model, 12, effort)}<span>{E(label)}</span></a>') if is_claude else \
                 (f'<span style="{pill}">{E(label)}</span>')
    gear = (f'<a href="/agent/{E(a.id)}/configure" title="Configure {E(a.display)}" style="display:inline-flex;'
            f'align-items:center;padding:5px;border-radius:var(--r);text-decoration:none;'
            f'color:var(--text-dim);background:var(--text-7)">{_icon("settings",16)}</a>')
    role = (f'<span style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--color-accent-700)">{E(a.theme_role)}</span>') if a.theme_role else ""
    profile = (f'<span style="font-size:12.5px;color:var(--text-muted);font-style:italic">{E(a.leader)}</span>') if a.leader else ""
    sep = ' <span style="color:var(--text-30)">·</span> ' if role and profile else ""
    return (f'<div style="display:flex;gap:14px;align-items:center;padding:12px 24px 8px;flex:none">'
            f'<div style="flex:none">{_portrait(realm_root, a, 56, dot=True)}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            f'<span class="mc-h-page is-agent">{E(a.display)}</span>'
            + (_coord_mark(20) if coord else "")
            + f'{_autonomy_badge(_autonomy_of(realm_root, a.id), 16)}{model_pill}{gear}</div>'
            f'<div style="margin-top:3px">{role}{sep}{profile}</div></div></div>')


def _agent_body(realm, realm_root, a, subtab, query=None) -> str:
    today = clock.today()
    query = query or {}
    if subtab == "jobs":
        return _tab_jobs(realm, realm_root, a, today, open_job=query.get("job", ""))
    if subtab == "skills":
        return _tab_skills(realm, realm_root, a)
    if subtab == "goals":
        return _tab_goals(realm, realm_root, a)
    if subtab in ("memory", "memories"):
        return _tab_memory(realm, realm_root, a, focus=query.get("focus", ""))
    if subtab == "inbox":
        return _tab_inbox(realm, realm_root, a)
    if subtab == "threads":
        return _tab_threads(realm, realm_root, a, query.get("thread"))
    if subtab == "configure":
        return _tab_configure(realm, realm_root, a)
    if subtab == "artefacts":
        return _realm_artefacts(realm, realm_root, only_agent=a.id)
    # There is no Overview any more: it was a read-only digest of Mandate, Soul, Jobs, Memory and
    # Skills, and every one of those now has a tab of its own that shows more and lets you edit it.
    # Threads is where you actually arrive when you open an agent, so unknown sub-tabs land there.
    return _tab_threads(realm, realm_root, a, query.get("thread"))


def _tab_jobs(realm, realm_root, a, today, open_job: str = "") -> str:
    now_dt = clock.now()
    legend = (f'<div style="display:flex;justify-content:flex-end;padding:0 10px 10px 28px">'
              f'{_status_legend()}</div>')
    # One renderer, shared with the realm Jobs page, which adds Kind and Owner. This page leaves
    # both out: every job here has the same owner, and the inline cmd tag already says the kind.
    joblist = _job_list(realm, realm_root, [(a, j) for j in a.jobs], today, now_dt,
                        show_owner=False, list_id="mc-joblist", open_job=open_job)
    search_input = (f'<div style="position:relative;flex:0 0 240px;max-width:240px">'
                    f'<span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);display:flex;'
                    f'color:var(--text-faint)">{_icon("search",14)}</span>'
                    f'<input id="mc-jobsearch" placeholder="Search jobs…" oninput="mcJobSearch()" '
                    f'style="{_FIELD};padding-left:30px;padding-right:30px">'
                    f'<span id="mc-jobsearch-x" onclick="mcJobSearchClear()" title="Clear" style="display:none;position:absolute;'
                    f'right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--text-faint)">{_icon("x",14)}</span></div>')
    status_opts = [("", "All statuses", "")] + [(v, lbl, _STATUS_FILTER_COLOR.get(v, "")) for v, lbl in _STATUS_FILTERS]
    cad_opts = [("", "All cadences", "")] + [(v, lbl, "") for v, lbl in _CADENCE_FILTERS]
    toolbar = (f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">{search_input}'
               f'{_filter_dropdown("ajf-status", "All statuses", status_opts, width="140px", onpick="mcAgentJobFilter")}'
               f'{_filter_dropdown("ajf-cad", "All cadences", cad_opts, width="140px", onpick="mcAgentJobFilter")}'
               f'<button id="ajf-clear" onclick="mcFDClear([\'ajf-status\',\'ajf-cad\'],\'mcAgentJobFilter\')" '
               f'style="display:none;align-items:center;gap:4px;border:0;background:transparent;cursor:pointer;'
               f'font-size:12px;color:var(--color-accent);padding:6px 4px">{_icon("x",12)}Clear</button></div>')
    return (f'<div style="padding:18px 24px 24px"><div style="display:flex;align-items:center;margin-bottom:8px">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:17px">'
            f'Jobs <span class="mc-eyebrow" style="margin-left:6px">· <span data-active-jobs>{sum(1 for x in a.jobs if x.enabled)}</span>'
            f' active · {E(a.display)} owns</span></div>'
            f'<a href="/new/job?agent={E(a.id)}" class="btn btn-secondary btn-sm" style="margin-left:auto;text-decoration:none">{_icon("plus", 14)}New job</a></div>'
            f'{_job_proposals_block(realm, realm_root, only_agent=a.id)}'
            f'{toolbar}{legend}{joblist}{_FDROP_JS}{_JOBS_SORT_JS}'
            + (_JOBOPEN_JS + f'<script>mcOpenJobFocus("job-{E(open_job)}")</script>' if open_job else "")
            + '</div>')






def _inbox_msgs(realm_root, agent_id: str) -> list[dict]:
    """Messages to this agent: agents/<id>/inbox/*.md files and/or inbox.md, newest first."""
    d = Path(realm_root) / "agents" / agent_id / "inbox"
    out = []
    files = list(d.glob("*.md")) if d.is_dir() else []
    single = Path(realm_root) / "agents" / agent_id / "inbox.md"
    if single.exists():
        files.append(single)
    for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
        txt = f.read_text(encoding="utf-8-sig").strip()
        status = "new"
        for line in txt.splitlines():
            if line.lower().startswith("status:"):
                status = line.split(":", 1)[1].strip()
                break
        frm = f.stem if f.name != "inbox.md" else "inbox"
        out.append({"from": frm, "status": status, "text": txt, "when": datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()})
    return out


def _tab_inbox(realm, realm_root, a) -> str:
    """This agent's slice of the realm inbox — what it's been asked to do and what it has asked of
    others. Renders through the same view as the realm page (scoped by agent) rather than a second
    implementation, so the two can't drift apart.

    Replaces an earlier placeholder that read loose `inbox/*.md` files; real messages are structured
    JSON under `inbox/pending|running|done`, so that view would now always have been empty.
    """
    from . import pages as _pages
    from .. import inbox as _inbox
    cad = _inbox.cadence(realm_root, a.id)
    acc = _inbox.accepts_from(realm_root, a.id)
    every = {"minute": "every minute", "hour": "hourly", "day": "daily",
             "off": "never — inbox reading is off"}.get(cad, cad)
    counts = _inbox.counts(realm_root, a.id)
    waiting = counts["pending"] + counts["running"]
    meta = (f'<span style="font-size:11.5px;color:var(--text-muted)">reads {E(every)} · '
            f'accepts from {E(_inbox.ACCEPTS.get(acc, acc).lower())} · set in Configure</span>')
    head = (f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:12px">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:17px">Inbox</div>'
            + (_pill(f"{waiting} waiting", "warn") if waiting else "")
            + meta + '</div>')
    return (f'<div style="padding:18px 24px 24px;max-width:900px">{head}'
            f'{_pages.inbox_view(realm, realm_root, agent_id=a.id)}</div>')


_SECTION_H = ("font-family:var(--font-heading);font-weight:600;font-size:15px")


def _a2a_box(on: bool, freq_opts: str, accepts_opts: str, field: str, lbl: str) -> str:
    """Agent-to-agent communication: one master switch with the two settings it governs beneath it.

    Those two only mean anything when the agent is part of the delegation network at all, so they
    grey out together rather than staying live and quietly doing nothing. The switch covers both
    directions — off means this agent neither receives delegated work nor hands any out."""
    return (f'<div style="margin-top:30px;border-top:1px solid var(--color-divider);padding-top:16px">'
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<span style="{_SECTION_H}">Agent-to-agent communication</span>'
            f'<label class="mc-toggle" title="{"On — this agent can exchange tasks with teammates" if on else "Off — this agent is out of the delegation network"}">'
            f'<input type="checkbox" id="c-a2a" {"checked" if on else ""} onchange="mcA2AToggle()">'
            f'<span class="mc-toggle-sl"></span></label></div>'
            f'<div style="font-size:12px;color:var(--text-muted);line-height:1.5;margin-top:5px;max-width:620px">'
            f'Whether teammates can hand this agent work, and it them. Switched off, nothing can be '
            f'queued for it and it can\'t delegate either — the realm-wide switch in Settings turns '
            f'this off for everyone at once.</div>'
            f'<div id="c-a2a-fields" style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;'
            f'align-items:start;margin-top:4px{"" if on else ";opacity:.45;pointer-events:none"}">'
            f'<div><label style="{lbl}">Inbox reading</label><select id="c-freq" style="{field}">{freq_opts}</select>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">How soon this agent '
            f'acts on a task a teammate sends it. Checking costs nothing — it only runs when '
            f'something is waiting.</div></div>'
            f'<div><label style="{lbl}">Accepts tasks from</label>'
            f'<select id="c-accepts" style="{field}">{accepts_opts}</select>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Who may assign it '
            f'work. Enforced when a task is picked up, not only when it\'s sent.</div></div>'
            f'</div></div>'
            + _A2A_TOGGLE_JS)


def _agent_manage_box(realm, a) -> str:
    """Retire and Delete, ordered harmless-to-irreversible and described that way — the same shape
    as Manage this realm in Settings, because it is the same decision one level down.

    Retire is the one that should feel available: nothing is deleted, the folder simply moves out
    of the realm, and the agent comes back with its jobs, threads, memories and grants intact. The
    text says so, because an owner who thinks retiring might lose a year of an agent's memory will
    reach for neither button and just leave the agent sitting there instead.
    """
    role = (realm.theme_coordinator if a.is_coordinator else realm.theme_agent).lower()
    nm = E(a.display)

    def act(label, desc, btn, onclick, danger=False):
        col = "var(--status-bad)" if danger else "var(--color-text)"
        return (f'<div style="display:grid;grid-template-columns:1fr auto;gap:14px;align-items:center;'
                f'padding:10px 0;border-top:1px solid var(--color-divider)">'
                f'<div><div style="font-size:12.5px;font-weight:600;color:{col}">{E(label)}</div>'
                f'<div style="font-size:11.5px;color:var(--text-muted);margin-top:2px;line-height:1.45">{desc}</div></div>'
                f'<button type="button" class="btn btn-secondary btn-sm" style="'
                f'white-space:nowrap{";color:var(--status-bad);border-color:var(--status-bad)" if danger else ""}" '
                f'onclick="{onclick}">{E(btn)}</button></div>')
    # The coordinator can't go: every agent's briefing names it and goals are assigned through it.
    # Said here rather than only in the error, so the button isn't a trap.
    if a.is_coordinator:
        return (f'<div style="margin-top:22px;padding-top:14px;border-top:1px solid var(--color-divider)">'
                f'<div style="font-size:12.5px;font-weight:600;margin-bottom:4px">Manage this {E(role)}</div>'
                f'<div style="font-size:11.5px;color:var(--text-muted);line-height:1.5;max-width:560px">'
                f'{nm} is this realm\'s coordinator and can\'t be retired or deleted — every agent\'s '
                f'briefing names the coordinator, and goals are assigned through it. Appoint another '
                f'coordinator first if you want to stand {nm} down.</div></div>')
    return (f'<div style="margin-top:22px;padding-top:14px;border-top:1px solid var(--color-divider)">'
            f'<div style="font-size:12.5px;font-weight:600">Manage this {E(role)}</div>'
            + act("Retire " + a.display,
                  f'Take {nm} out of the realm without deleting anything. The jobs stop running and '
                  f'{nm} disappears from the register, goals and delegation — but the folder, the '
                  f'threads, the memories, the run history and the capability grants all stay exactly '
                  f'as they are. Reinstate from Appoint a new {E(role)} to bring {nm} back unchanged.',
                  "Retire…", f"mcAgentRetire(this,'{E(a.id)}','{nm}')")
            + act("Delete " + a.display,
                  f'Delete {nm}\'s folder and everything in it — jobs, threads, memories, run history. '
                  f'On Windows it goes to the Recycle Bin, so it can be recovered from there, but '
                  f'nothing inside ARMADA will bring it back. You\'ll be asked to type “{nm}” to confirm.',
                  "Delete…", f"mcAgentDelete(this,'{E(a.id)}','{nm}')", danger=True)
            + f'<div id="c-manage-msg" style="font-size:11.5px;color:var(--text-muted);margin-top:8px"></div>'
            f'</div>')


def _agent_advanced_box(fallback_opts: str, maxbudget: str, field: str, lbl: str,
                        manage: str = "") -> str:
    """Advanced, last on the page and with a heading you can actually see. It used to be a small
    uppercase line wedged between two field groups, which read as a label rather than a section.

    Being last also means opening it usually reveals content below the fold, so it scrolls itself
    into view — enough to bring its end into the viewport, or, if it is ever taller than the
    viewport, its heading to the top. Either way you are looking at what you just opened.
    """
    return (f'<details id="c-advanced" ontoggle="mcRevealSection(this)" '
            f'style="margin-top:30px;border-top:1px solid var(--color-divider);padding-top:16px">'
            f'<summary style="cursor:pointer;{_SECTION_H};list-style:none;display:flex;align-items:center;gap:6px">'
            f'<span class="mc-adv-caret" style="display:inline-flex;color:var(--text-muted)">{_icon("chevron-right",14)}</span>'
            f'Advanced</summary>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;align-items:start;margin-top:10px">'
            f'<div><label style="{lbl};margin-top:0">Fallback model</label><select id="c-fallback" style="{field}">{fallback_opts}</select>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Switches to this model if the primary is overloaded or unavailable. Inherit = the realm default (or none).</div></div>'
            f'<div><label style="{lbl};margin-top:0">Max budget — USD per run</label><input id="c-maxbudget" type="number" min="0" step="0.01" value="{E(maxbudget)}" placeholder="inherit" style="{field}">'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Hard spend ceiling for a single run. Blank = inherit the realm default; 0 = no cap.</div></div>'
            f'</div>{manage}</details>'
            '<style>details[open] .mc-adv-caret svg{transform:rotate(90deg);transition:transform .15s}'
            '.mc-adv-caret svg{transition:transform .15s}summary::-webkit-details-marker{display:none}</style>'
            + _REVEAL_JS)


def _md_field(fid: str, label: str, raw: str, lbl: str, ta: str, min_h: int) -> str:
    """A markdown field that reads as prose and edits as source.

    Soul, Role & Mission and Tenets are written in headings, lists and emphasis — they are meant to
    be read. Shown only as a textarea, the Configure page turned an agent's character into a wall
    of hashes and asterisks, which is also the version you proof-read. So: rendered by default,
    raw only while you are actually editing.

    The textarea stays in the DOM the whole time (hidden), so mcSaveAgent keeps reading the same
    element ids and the save path is untouched.

    The rendered view is itself the edit affordance — clicking the text starts editing, the way you
    would expect of anything that looks like a document. The Edit link stays for discoverability.
    """
    rendered = _md(raw) if raw.strip() else (
        f'<span style="color:var(--text-ghost)">Nothing yet.</span>')
    return (
        f'<div style="margin-top:26px">'
        f'<div style="display:flex;align-items:baseline;gap:10px">'
        f'<label style="{lbl};flex:1;margin:0 0 4px">{label}</label>'
        f'<span id="{fid}-dirty" style="display:none;font-size:11px;font-style:italic;'
        f'color:var(--status-warn);white-space:nowrap">unsaved</span>'
        f'<a id="{fid}-toggle" onclick="mcMdEdit(\'{fid}\',true)" '
        f'style="cursor:pointer;font-size:11px;color:var(--color-accent-2);white-space:nowrap">Edit</a></div>'
        f'<div id="{fid}-view" class="mc-md mc-frame" onclick="mcMdEdit(\'{fid}\',true)" '
        f'title="Click to edit" style="border-radius:var(--r);padding:10px 12px;cursor:text;'
        f'font-size:12.5px;line-height:1.55;min-height:{min_h}px;max-height:340px;overflow:auto;'
        f'background:var(--color-bg)">{rendered}</div>'
        f'<textarea id="{fid}" onblur="mcMdBlur(\'{fid}\')" '
        f'style="{ta};min-height:{min_h}px;display:none">{E(raw)}</textarea></div>')


# Script body lives in webui/static/js/mdfield.js (Phase 2, 2.1).
_MD_FIELD_JS = _MDFIELD_JS_ASSET


def _tab_configure(realm, realm_root, a) -> str:
    agent_dir = realm_root / "agents" / a.id
    ac = json.loads((agent_dir / "agent.json").read_text(encoding="utf-8-sig")) if (agent_dir / "agent.json").exists() else {}
    # Raw, NOT escaped here. _md_field escapes for each destination itself — _md() for the reading
    # view, E() for the textarea. Escaping first meant every apostrophe went through html.escape
    # twice: the view showed "doesn&amp;#x27;t", and the textarea decoded one level, so what you
    # then saved wrote "doesn&#x27;t" into the file. One escape per destination, at the destination.
    mandate = _read_md(realm_root, a.id, "mandate.md").strip()
    soul = _read_md(realm_root, a.id, "soul.md").strip()
    tenets = _read_md(realm_root, a.id, "tenets.md").strip()
    model, effort, autonomy = ac.get("model") or "", ac.get("effort") or "", ac.get("autonomy") or "propose"
    cur_color = ac.get("color") or _agent_default_color(realm, a.id)
    freq = ac.get("inbox_frequency", "every run")
    field = "display:block;width:100%;padding:6px 8px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;font-size:13px"
    lbl = "font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin:20px 0 5px;display:block"
    ta = ("width:100%;resize:vertical;background:var(--color-sand-100);border:1px solid var(--color-sand-500);border-radius:var(--r);"
          "padding:10px;font-size:12.5px;line-height:1.55;color:var(--color-text);font-family:var(--font-body)")
    model_opts = _model_options(realm_root, model, inherit=True)
    effort_opts = _effort_options(realm_root, effort, inherit=True)
    fallback = ac.get("fallback_model") or ""
    fallback_opts = _model_options(realm_root, fallback, inherit=True)   # blank = inherit realm default / none
    maxbudget = ac.get("max_budget_usd")
    maxbudget = "" if maxbudget in (None, "", 0) else str(maxbudget)
    # Inbox reading drives the real cadence now, so the options are the ones dispatch understands.
    # Blank = inherit the realm default, matching how model/effort/fallback already behave here.
    from .. import inbox as _inbox
    cad_cur = (ac.get("inbox") or {}).get("cadence", "")
    acc_cur = (ac.get("inbox") or {}).get("accepts", "")
    freq_opts = ('<option value="">inherit realm default</option>' + "".join(
        f'<option value="{k}" {"selected" if k == cad_cur else ""}>{lab}</option>'
        for k, lab in [("minute", "every minute"), ("hour", "hourly"),
                       ("day", "daily"), ("off", "never — ignore my inbox")]))
    accepts_opts = ('<option value="">inherit realm default</option>' + "".join(
        f'<option value="{k}" {"selected" if k == acc_cur else ""}>{E(lab)}</option>'
        for k, lab in _inbox.ACCEPTS_CHOICES.items()))
    a2a_on = bool((ac.get("inbox") or {}).get("enabled", True))
    from .. import verbosity as _verbosity
    v_cur = _verbosity.normalise(ac.get("verbosity"))
    v_inherit = _verbosity.realm_level(realm_root)
    verb_opts = (f'<option value="" {"selected" if not v_cur else ""}>'
                 f'inherit realm default ({E(_verbosity.label(v_inherit))})</option>' + "".join(
                     f'<option value="{k}" {"selected" if k == v_cur else ""}>{E(lab)} — {E(desc)}</option>'
                     for k, (lab, desc, _p) in _verbosity.LEVELS.items()))
    return (f'<div style="display:flex;gap:20px;align-items:flex-start;padding:18px 24px 24px">'
            f'<div style="flex:1;min-width:0;max-width:820px">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:17px;margin-bottom:6px">Configure</div>'
            f'<div style="display:flex;gap:16px;align-items:flex-start;margin-top:8px">'
            f'<div style="flex:none" id="c-avatar-prev">{_portrait(realm_root, a, 64, color=cur_color)}</div>'
            f'<div style="flex:1"><label style="{lbl};margin-top:0">Avatar</label>'
            f'<div style="display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-secondary btn-sm" onclick="document.getElementById(\'c-avatar\').click()">Choose file…</button>'
            f'<button class="btn btn-secondary btn-sm" onclick="mcAvatarModal(true)">Pick from set</button>'
            + (f'<button class="btn btn-secondary is-danger btn-sm" onclick="mcRemoveAvatar({_J(a.id)})">Remove</button>' if _avatar_file(realm_root, a.id) else "")
            + f'<input type="file" id="c-avatar" accept="image/*" style="display:none" onchange="mcUploadAvatar({_J(a.id)},this)"></div>'
            f'<div id="c-avatarmsg" style="font-size:11.5px;color:var(--text-muted);margin-top:4px">'
            f'Upload a portrait, or pick one from the set. Images are cropped square &amp; optimized.</div></div></div>'
            + _avatar_modal(a.id) +
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px">'
            f'<div><label style="{lbl}">Name {_STAR}</label><input id="c-name" value="{E(a.display)}" style="{field}"></div>'
            f'<div><label style="{lbl}">Role</label><input id="c-role" value="{E(a.theme_role)}" placeholder="E.g. Finance Minister" style="{field}"></div>'
            f'<div style="grid-column:1 / 3"><label style="{lbl}">Profile (optional)</label><input id="c-profile" value="{E(a.leader)}" placeholder="E.g. after Warren Buffett — value discipline, margin of safety…" style="{field}"></div>'
            # Colour sits with the other cosmetic fields (name, role, profile) rather than after
            # the behavioural ones — it belongs to how the agent looks, not how it acts.
            f'<div style="grid-column:1 / 3"><label style="{lbl}">Agent colour — shows up in token usage breakdowns, etc.</label>{_agent_color_control(cur_color, "c-color")}</div>'
            f'<div style="grid-column:1 / 3"><label style="{lbl}">Autonomy</label>{_autonomy_control(autonomy, "c-autonomy")}</div>'
            f'<div><label style="{lbl}">Model</label><select id="c-model" style="{field}">{model_opts}</select></div>'
            f'<div><label style="{lbl}">Effort</label><select id="c-effort" style="{field}">{effort_opts}</select></div>'
            f'<div style="grid-column:1 / 3"><label style="{lbl}">Verbosity</label>'
            f'<select id="c-verbosity" style="{field};max-width:340px">{verb_opts}</select>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">How much this agent '
            f'writes back. It never changes how much work it does, and failures, warnings and '
            f'anything needing your approval are always spelled out in full.</div></div>'
            f'<div style="grid-column:1 / 3"><label style="{lbl}">Relative token consumption '
            f'<span style="text-transform:none;letter-spacing:0;color:var(--text-muted)">· this model, effort &amp; verbosity</span></label>'
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<span id="c-modelmark" class="mc-modelmark" style="display:inline-flex;color:var(--text-muted)">{_icon("claude", 16)}</span>'
            f'<div style="position:relative;flex:1;height:12px;border-radius:6px;background:{_consumption_gradient_css()}">'
            f'<div id="c-consmarker" style="position:absolute;top:-3px;left:0%;transform:translateX(-50%);width:4px;height:18px;'
            f'border-radius:3px;background:var(--color-text);box-shadow:0 0 0 2px var(--color-bg)"></div></div>'
            f'<span style="font-size:10px;color:var(--text-muted);white-space:nowrap">low → high</span></div>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:5px">Where this '
            f'model-effort-verbosity combination sits between the cheapest and most token-hungry '
            f'combination. The icon colour tracks the marker.</div></div>'
            f'</div>'
            + _md_field("c-soul", "Soul (character, voice &amp; traits)", soul, lbl, ta, 80)
            + _md_field("c-mandate", "Role and Mission", mandate, lbl, ta, 130)
            + _md_field("c-tenets", "Tenets — this agent's own rules", tenets, lbl, ta, 80)
            # This box is exactly where someone would otherwise paste the honesty and loyalty rules
            # into all eight agents — the duplication the Covenant exists to prevent. Say so here,
            # where the temptation is, rather than only in the Covenant nobody has opened yet.
            + f'<div style="display:flex;align-items:flex-start;gap:6px;margin-top:6px;font-size:11px;'
            f'color:var(--text-soft);line-height:1.5">'
            f'<span style="display:flex;flex:none;color:var(--color-accent-2);margin-top:1px">{_icon("agreement",13)}</span>'
            f'<span>{E(a.display)} is also bound by the '
            f'<a href="/memory" style="color:var(--color-accent-2);text-decoration:none">realm Covenant</a>'
            f' — honesty, loyalty, confidentiality and the limits on acting. Don\'t repeat any of it '
            f'here; it already applies. These are the rules that are {E(a.display)}\'s alone.</span></div>'
            f'{_a2a_box(a2a_on, freq_opts, accepts_opts, field, lbl)}'
            f'{_agent_advanced_box(fallback_opts, maxbudget, field, lbl, _agent_manage_box(realm, a))}'
            f'</div>'
            + _configure_actions(a)
            + f'</div>'
            + _AUTONOMY_JS + _AGENT_COLOR_JS + _MD_FIELD_JS
            + _consumption_js(realm, verbosity_id="c-verbosity"))


def _configure_actions(a) -> str:
    """Save / Cancel, pinned to the right of the form.

    The page is long — avatar, eleven fields, three documents, two collapsible boxes — and Save sat
    under the last of them, so committing a one-word change to the Name meant scrolling past
    everything you had not touched. Sticky inside .mc-appscroll, which is the element that scrolls.
    """
    return (
        f'<div style="flex:none;width:186px;position:sticky;top:12px;display:flex;'
        f'flex-direction:column;gap:10px">'
        f'<div style="display:flex;gap:8px">'
        f'<button class="btn btn-primary" id="c-save" style="color:#fff;font-size:12.5px;'
        f'padding:7px 4px;flex:1" onclick="mcSaveAgent({_J(a.id)})">Save</button>'
        f'<a href="/agent/{E(a.id)}" class="btn btn-secondary" style="text-decoration:none;'
        f'text-align:center;font-size:12.5px;padding:7px 4px;flex:1">Cancel</a></div>'
        # The "saved" tick lives here rather than replacing the button label, so the button stays
        # where your eye left it and the confirmation appears next to the thing you just pressed.
        f'<div id="c-saved" style="display:none;align-items:center;gap:5px;font-size:12px;'
        f'color:var(--status-ok);font-weight:600">{_icon("circle-check", 14)}<span>Saved</span></div>'
        f'<div id="c-savemsg" style="font-size:11px;color:var(--text-muted);line-height:1.45">'
        f'writes agent.json + mandate.md + soul.md + tenets.md</div></div>')


def _avatar_count() -> int:
    d = Path(__file__).resolve().parent / "static" / "avatars"
    return len(list(d.glob("a*.png"))) if d.is_dir() else 0


def _avatar_modal(agent_id: str) -> str:
    n = _avatar_count()
    tiles = "".join(
        f'<img src="/static/avatars/a{i}.png" width="64" height="64" loading="lazy" '
        f'onclick="mcSetPreset({_J(agent_id)},\'a{i}\')" '
        f'style="width:64px;height:64px;border-radius:50%;cursor:pointer;border:2px solid transparent;background:var(--color-accent-100)"'
        f' onmouseover="this.style.borderColor=\'var(--color-accent)\'" onmouseout="this.style.borderColor=\'transparent\'">'
        for i in range(1, n + 1))
    return (f'<div id="mc-avatar-modal" class="mc-modal-ov" onclick="if(event.target===this)mcAvatarModal(false)">'
            f'<div class="mc-modal-box" style="width:min(560px,92vw);max-height:78vh;overflow:auto">'
            f'<div style="display:flex;align-items:center;margin-bottom:12px"><div style="font-family:var(--font-heading);'
            f'font-weight:600;font-size:16px">Pick an avatar</div>'
            f'<button class="btn btn-secondary btn-sm" style="margin-left:auto" onclick="mcAvatarModal(false)">Close</button></div>'
            f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(64px,1fr));gap:14px;justify-items:center">{tiles}</div>'
            f'<div id="mc-presetmsg" style="font-size:12px;color:var(--text-muted);margin-top:10px"></div></div></div>')
