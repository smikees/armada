"""ARMADA page entrypoints (render_*), carved out of _core.py in Phase 3.

These are the top-of-stack renderers called by serve.py. They are pure leaves — nothing in
_core calls them — so they live here and pull every helper/constant they need from _core via
the namespace mirror below (so call sites like _nav(...) / _page_shell(...) are unchanged).
"""
from __future__ import annotations

from .. import clock
from . import _core
from . import layout as _layout
# Phase 2, 2.1: scripts local to pages.py's own renderers (not re-exported via _core).
from ..assets import (INBOX_JS as _INBOX_JS_ASSET, STA2A_TOGGLE_JS as _STA2A_TOGGLE_JS,
    ADDSECTION_JS as _ADDSECTION_JS, EDITSECTION_JS as _EDITSECTION_JS, SNAP_JS as _SNAP_JS,
    DOCSEARCH_JS as _DOCSEARCH_JS)
# Mirror _core's namespace (helpers, constants, imports) so the moved render_* functions resolve
# their names exactly as they did inside _core.
globals().update({k: v for k, v in vars(_core).items() if not k.startswith('__')})
from ._base import _J, _pill, _tone, _ask_alexander  # _J: JS-string-in-attribute escaping (5.8)
import logging
from ..util import swallowed
log = logging.getLogger(__name__)

# The "this one is selected" fill on a realm-icon tile. The server marks the realm's current icon
# on load; mcPickSetIcon re-applies the same fill on click. The two must stay identical — a test
# asserts the JS still uses this exact colour.
_SETICON_ON = "background:var(--text-12);"


def render_thread_rail(realm, realm_root, agent_id: str, thread: str) -> str:
    """Entry point for the post-reply rail refresh: render one thread's right rail (or '')."""
    a = next((x for x in realm.agents if x.id == agent_id), None)
    return _thread_rail(realm_root, a, thread) if a else ""


def render_thread_turns(realm, realm_root, agent_id: str, thread: str) -> str:
    """Entry point for the post-reply transcript refresh: render one thread's turns (or '')."""
    a = next((x for x in realm.agents if x.id == agent_id), None)
    return _render_turns(realm_root, a, thread) if a else ""


def render_catalogue_results(realm, realm_root, **kw) -> str:
    """The Catalogue's results area on its own, for the filter/search/page refresh."""
    from .catalogue import _cat_results
    return _cat_results(realm, realm_root, **kw)


def render_thread_embed(realm, realm_root, agent_id: str, thread: str = "main", dark: bool = False) -> str:
    """Minimal standalone chat pane for embedding a single thread as a dashboard widget (iframe)."""
    realm_root = Path(realm_root)
    a = next((x for x in realm.agents if x.id == agent_id), None)
    body_cls = "armada-dark" if dark else ""
    if not a:
        return (f'<!doctype html><html><head><meta charset="utf-8">'
                f'{_CSS_LINKS}{_theme_style()}</head>'
                f'<body class="{body_cls}"><div style="padding:16px;font-size:13px">No agent \'{E(agent_id)}\'.</div></body></html>')
    names, _ = _ordered_threads(realm_root / "agents" / a.id)
    if thread not in names:
        thread = "main"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{E(a.display)} · {E(thread)}</title>
{_CSS_LINKS}{_theme_style()}
<style>html,body{{height:100%;margin:0;background:var(--color-bg)}}</style></head>
<body class="{body_cls}"><div style="height:100vh;min-height:0">{_chat_center(realm_root, a, thread, embed=True)}</div>{_ICONS_JS}{_CHAT_JS}</body></html>"""


def render_agent(realm, realm_root, agent_id: str, subtab: str = "threads", dark: bool = False, query=None) -> str:
    realm_root = Path(realm_root)
    # Overview is gone — every card it summarised now has its own, richer tab. Old links and
    # bookmarks land on Threads rather than on a page whose crumb names a section that isn't there.
    if subtab == "overview":
        subtab = "threads"
    a = next((x for x in realm.agents if x.id == agent_id), None)
    body_cls = "armada-dark" if dark else ""
    if not a:
        return (f'<!doctype html><html><head><meta charset="utf-8">'
                f'{_CSS_LINKS}{_theme_style()}</head>'
                f'<body class="{body_cls}">{_titlebar(realm)}{_nav(realm)}'
                f'<div style="padding:24px"><a href="/">← {E(realm.name)}</a><p>No agent \'{E(agent_id)}\'.</p></div></body></html>')
    # The Inbox count is what's WAITING, not the total — a sub-tab badge should tell you there's
    # something to look at, not how much history has accumulated.
    try:
        from .. import inbox as _inbox_mod
        _ic = _inbox_mod.counts(realm_root, a.id)
        _inbox_waiting = _ic["pending"] + _ic["running"]
    except Exception:  # noqa — a malformed message must never break the agent page
        swallowed(log, 'render_agent: failed; using a default')
        _inbox_waiting = 0
    # The Capabilities badge counts what this agent may use, across all four kinds — not just its
    # declared skills, which was a different (and much smaller) number wearing the same label.
    try:
        from .. import capabilities as _capsmod
        _ncaps = sum(len(v) for v in _capsmod.usable(realm_root, a.id).values())
    except Exception:  # noqa
        swallowed(log, 'render_agent: failed; using a default')
        _ncaps = 0
    counts = {"Jobs": sum(1 for j in a.jobs if j.enabled), "Capabilities": _ncaps, "Memories": len(_agent_memory(realm_root, a.id)),
              "Inbox": _inbox_waiting,
              "Goals": len(goalsmod.goals_for_agent(realm_root, a.id, is_coord=a.is_coordinator))}
    # Configure is a standalone editor: no agent header / sub-tabs, and it carries its own breadcrumb.
    if subtab == "configure":
        crumb = (f'<div class="mc-crumb" style="padding:8px 24px 0"><a href="/">{E(realm.name)}</a> › '
                 f'<a href="/ministers">{E(realm.theme_agent)}s</a> › '
                 f'<a href="/agent/{E(a.id)}/threads" id="c-crumb-name">{E(a.display)}</a> › <b>Configure</b></div>')
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(a.display)} · Configure</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, realm.theme_agent + "s")}{crumb}
<div class="mc-appscroll" style="flex:1;min-height:0;overflow:auto">{_tab_configure(realm, realm_root, a)}</div>
</div>{_AGENT_JS}{_FORM_JS}</body></html>"""
    _sec_labels = {"threads": "Threads", "goals": "Goals", "jobs": "Jobs", "inbox": "Inbox",
                   "memory": "Memories", "memories": "Memories", "artefacts": "Artefacts",
                   "capabilities": "Capabilities", "skills": "Capabilities"}
    sec = _sec_labels.get(subtab, subtab.capitalize())
    crumb = (f'<div class="mc-crumb" style="padding:8px 24px 0"><a href="/">{E(realm.name)}</a> › '
             f'<a href="/ministers">{E(realm.theme_agent)}s</a> › '
             f'<a href="/agent/{E(a.id)}/threads">{E(a.display)}</a> › <b>{E(sec)}</b></div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(a.display)}</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, realm.theme_agent + "s")}
{crumb}{_agent_header(realm, realm_root, a)}{_sub(subtab.capitalize(), a.id, counts)}
<div class="mc-appscroll" style="flex:1;min-height:0;overflow:auto">{_agent_body(realm, realm_root, a, subtab, query)}</div>
</div>{_ICONS_JS}{_RUN_JS}{_CHAT_JS}{_AGENT_JS}{_FORM_JS}</body></html>"""


def render_job(realm, realm_root, agent_id: str, job_id: str, dark: bool = False) -> str:
    realm_root = Path(realm_root)
    a = next((x for x in realm.agents if x.id == agent_id), None)
    body_cls = "armada-dark" if dark else ""
    jc = _job_prompt(realm_root, agent_id, job_id)
    if not a or not jc:
        return _page_shell(realm, "Jobs", "Job", f'<div style="padding:24px"><a href="/jobs">← Jobs</a><p>No job {E(job_id)}.</p></div>', dark)
    name = jc.get("name", job_id)
    summary = jc.get("summary", "")
    kind = jc.get("kind") or ("command" if (jc.get("run") or jc.get("command")) else "agent")
    _run = jc.get("run")
    if isinstance(_run, list):                       # command jobs may store `run` as an argv list
        _run = " ".join(str(x) for x in _run)
    prompt = E(jc.get("prompt") or _run or "")
    cadence = jc.get("cron") or jc.get("schedule") or "manual"
    is_cron_c = len(str(cadence).split()) == 5
    cron_val = cadence if is_cron_c else ""
    # parse cron time/days for the editor
    hh, mm, sel_days, dom1 = "09", "00", [], False
    if is_cron_c:
        f = str(cadence).split()
        try:
            mm, hh = f"{int(f[0]):02d}", f"{int(f[1]):02d}"
        except ValueError:
            pass
        if f[2] == "1":
            dom1 = True
        if f[4] != "*":
            for part in f[4].split(","):
                if "-" in part:
                    x, y = part.split("-"); sel_days += list(range(int(x), int(y) + 1))
                elif part.isdigit():
                    sel_days.append(int(part))
    model = jc.get("model") or ""
    effort = jc.get("effort") or ""
    thread = jc.get("thread", "main")
    onfail = jc.get("on_failure", "Retry ×3, then alert me")
    budget = jc.get("budget", "")
    allowed = jc.get("allowed_skills") or [s.id for s in a.skills]

    runs = [ev for ev in _runs(realm_root, a.id) if ev.get("task") == job_id][-12:][::-1]
    hist = "".join(f'<tr><td class="mono" style="font-size:11px">{E(_fmt_ts(ev.get("ts","")))}</td>'
                   f'<td style="color:{status.color(ev.get("status",""))};font-size:11.5px">{E(str(ev.get("status","")))}</td>'
                   f'<td style="font-size:11.5px">{E(str(ev.get("summary",""))[:90])}{_ask_alexander(a.id, job_id, ev)}</td>'
                   f'<td class="mono" style="font-size:11px;text-align:right">{(ev.get("tokens") or {}).get("total","") if isinstance(ev.get("tokens"),dict) else ""}</td></tr>' for ev in runs) \
           or '<tr><td colspan=4 style="font-size:11.5px;color:var(--text-muted)">no runs yet</td></tr>'

    day_circles = "".join(
        f'<span class="mc-day" data-dow="{dow}" onclick="mcTglDay(this)" style="width:30px;height:30px;border-radius:50%;'
        f'display:grid;place-items:center;cursor:pointer;font-size:11px;border:1px solid var(--color-divider);'
        f'{"background:var(--color-accent-100);border-color:var(--color-accent-300);color:var(--color-accent-800)" if dow in sel_days else ""}">{lbl}</span>'
        for lbl, dow in _DOWS)
    model_opts = _model_options(realm_root, model, inherit=True)
    effort_opts = _effort_options(realm_root, effort, inherit=True)
    skill_chips = "".join(
        f'<label style="display:inline-flex;gap:5px;align-items:center;margin:0 8px 6px 0;font-size:12px">'
        f'<input type="checkbox" class="mc-skill" value="{E(s.id)}" {"checked" if s.id in allowed else ""}>{E(s.id)}</label>'
        for s in a.skills) or '<span style="font-size:12px;color:var(--text-muted)">no skills granted</span>'

    field = "display:block;width:100%;padding:6px 8px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;font-size:13px"
    lbl = "font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin:12px 0 4px;display:block"

    definition = (
        f'<div class="mc-h-card" style="margin-bottom:6px">Definition</div>'
        f'<label style="{lbl}">Name</label><input id="j-name" value="{E(name)}" style="{field}">'
        f'<label style="{lbl}">Summary</label>'
        f'<input id="j-summary" value="{E(summary)}" maxlength="120" '
        f'placeholder="One line: what this job does" style="{field}">'
        f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Shown beside the job '
        f'name in the list, so the page says what each job does without opening it.</div>'
        f'<label style="{lbl}">Prompt</label>'
        f'<textarea id="j-prompt" style="width:100%;min-height:180px;resize:vertical;background:var(--color-sand-100);'
        f'border:1px solid var(--color-sand-500);border-radius:var(--r);padding:10px;font-family:ui-monospace,Menlo,Consolas,monospace;'
        f'font-size:11.5px;line-height:1.55;color:var(--color-text)">{prompt}</textarea>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
        f'<div><label style="{lbl}">Kind</label><select id="j-kind" style="{field}">'
        f'<option value="agent" {"selected" if kind=="agent" else ""}>Agent · prompt</option>'
        f'<option value="command" {"selected" if kind=="command" else ""}>Command · script</option></select></div>'
        f'<div><label style="{lbl}">Target thread</label><input id="j-thread" value="{E(thread)}" style="{field}"></div>'
        f'<div><label style="{lbl}">Model</label><select id="j-model" style="{field}">{model_opts}</select></div>'
        f'<div><label style="{lbl}">Effort</label><select id="j-effort" style="{field}">{effort_opts}</select></div></div>'
        f'<label style="{lbl};display:inline-flex;align-items:center;gap:5px">Cadence'
        f'<span onclick="mcCronHelp(true)" title="What is cron?" style="cursor:pointer;display:inline-flex;'
        f'color:var(--text-faint)">{_icon("info",13)}</span></label>'
        f'<div class="mc-frame" style="padding:10px;border-radius:var(--r)">'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">'
        + "".join(f'<span class="btn btn-secondary btn-sm" onclick="mcPreset(\'{p}\')">{p.title()}</span>'
                  for p in ["daily", "weekdays", "weekly", "monthly", "on demand"])
        + f'</div><div style="display:flex;gap:6px;margin-bottom:8px">{day_circles}</div>'
        f'<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">'
        f'<label style="font-size:12px">Time <input id="j-time" type="time" value="{hh}:{mm}" style="padding:4px 6px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text)" oninput="mcCron()"></label>'
        f'<label style="font-size:12px"><input id="j-dom1" type="checkbox" {"checked" if dom1 else ""} onchange="mcCron()"> 1st of month</label>'
        f'<label style="font-size:12px">cron <input id="j-cron" value="{E(cron_val)}" placeholder="0 9 * * *" style="width:130px;padding:4px 6px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font-family:ui-monospace,monospace;font-size:11.5px" oninput="mcCronManual()"></label></div>'
        f'<div id="j-next" style="font-size:11px;color:var(--text-muted);margin-top:6px"></div></div>'
        f'<label style="{lbl}">Allowed skills</label><div>{skill_chips}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
        f'<div><label style="{lbl}">On failure</label><input id="j-onfail" value="{E(onfail)}" style="{field}"></div>'
        f'<div><label style="{lbl}">Budget / run</label><input id="j-budget" value="{E(budget)}" placeholder="8k tokens" style="{field}"></div></div>'
        )

    # Run history leads this column. It used to sit under a Run-now button and an output pane that
    # is empty on arrival, so the thing you came to read started below the fold on a page whose
    # other half is a form.
    execution = (
        f'<div class="mc-h-card" style="margin-bottom:6px">Run history</div>'
        f'<table class="table" style="font-size:12px"><thead><tr><th>When</th><th>Status</th><th>Summary</th><th style="text-align:right">Tokens</th></tr></thead>'
        f'<tbody>{hist}</tbody></table>'
        f'<pre id="j-out" style="display:none;margin-top:10px;background:var(--color-sand-100);border:1px solid var(--color-sand-300);color:var(--color-text);'
        f'border-radius:var(--r);padding:10px;white-space:pre-wrap;max-height:300px;overflow:auto;resize:vertical;font-size:11.5px"></pre>')

    # Every action on one bar at the foot of the page, rather than Save buried mid-form and Run at
    # the top of the other column — the two things you do when you are finished were the two
    # furthest apart on the page. Sized exactly like the buttons in an expanded job row, because
    # these are the same four actions and the two views should not look like two products. Delete
    # sits in the line with the rest rather than pushed to the far edge: it reads as one of the
    # things you can do here, and it asks twice before it does anything.
    actions = (
        f'<div style="display:flex;gap:8px;align-items:center;margin-top:20px;padding-top:14px;'
        f'border-top:1px solid var(--color-divider)">'
        f'<button class="btn btn-primary btn-sm" '
        f'onclick="mcSaveJob({_J(a.id)},{_J(job_id)})">Save</button>'
        f'<button class="btn btn-secondary btn-sm" '
        f'onclick="mcRunJob({_J(a.id)},{_J(job_id)},\'claude\')">'
        f'{_icon("play",12)}Run now</button>'
        f'<a href="/agent/{E(a.id)}/jobs" class="btn btn-secondary btn-sm" style="text-decoration:none">'
        f'Back to jobs</a>'
        f'<button class="btn btn-secondary is-danger btn-sm" '
        f'onclick="mcDeleteJobPage(this,{_J(a.id)},{_J(job_id)},{_J(name)})">'
        f'{_icon("trash",12)}Delete job</button>'
        f'<span id="j-savemsg" style="font-size:12px;color:var(--text-muted)"></span></div>')

    crumb = (f'<div class="mc-crumb" style="padding:8px 24px 0"><a href="/">{E(realm.name)}</a> › '
             f'<a href="/ministers">{E(realm.theme_agent)}s</a> › <a href="/agent/{E(a.id)}">{E(a.display)}</a> › '
             f'<a href="/agent/{E(a.id)}/jobs">Jobs</a> › <b>{E(name)}</b></div>')
    header = (f'<div style="padding:10px 24px 10px;display:flex;align-items:baseline;gap:10px;border-bottom:1px solid var(--color-divider)">'
              f'<span style="font-family:var(--font-heading);font-weight:600;font-size:26px">{E(name)}</span>'
              f'<span class="tag mc-frame" style="font-size:10.5px;padding:1px 7px">{E(kind)} job</span>'
              # Created moved here from a column on the Jobs list. It is worth knowing once, when
              # you are looking at this job; it was not worth a column on a page you scan.
              f'<span style="font-size:12px;color:var(--text-muted)">owned by {E(a.display)} · '
              f'{_humanize(cadence)} · → {E(thread)}'
              + (f' · created {E(_job_created(realm_root, agent_id, job_id, jc))}'
                 if _job_created(realm_root, agent_id, job_id, jc) else "")
              + f'</span></div>')
    body = (f'{crumb}{header}<div class="mc-appscroll" style="flex:1;min-height:0;overflow:auto;padding:8px 24px 24px">'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">'
            f'<div>{definition}</div><div>{execution}</div></div>{actions}</div>{_CRON_HELP}')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(name)}</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, "Jobs")}{body}</div>{_JOB_JS}{_FORM_JS}</body></html>"""


def render_new_agent(realm, realm_root, dark: bool = False) -> str:
    cancel = '<a href="/ministers" class="btn btn-secondary" style="text-decoration:none">Cancel</a>'
    body = (f'<div style="padding:18px 24px 24px;max-width:760px">{_page_title("Appoint a " + realm.theme_agent.lower())}'
            f'{_new_agent_form(realm, cancel)}</div>')
    return (_page_shell(realm, realm.theme_agent + "s", "Appoint", body, dark) + _NEW_JS + _AUTONOMY_JS
            + _AGENT_COLOR_JS + _consumption_js(realm, "n-model", "n-effort", "n-consmarker", "#n-cons"))


def render_new_job(realm, realm_root, agent_id: str, dark: bool = False) -> str:
    a = next((x for x in realm.agents if x.id == agent_id), None)
    if not a:
        return _page_shell(realm, "Jobs", "New job", f'<div style="padding:24px">No agent {E(agent_id)}.</div>', dark)
    body = (f'<div style="padding:18px 24px 24px;max-width:760px">{_page_title("New job", "for " + a.display)}'
            f'<input type="hidden" id="j-agent" value="{E(agent_id)}">'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
            f'<div><label class="mc-label">Name {_STAR}</label><input id="j-name" placeholder="E.g. Daily Brief" class="mc-field"></div>'
            f'<div><label class="mc-label">Kind</label><select id="j-kind" class="mc-field">'
            f'<option value="agent">Agent · prompt</option><option value="command">Command · script</option></select></div>'
            f'<div><label class="mc-label">Target thread</label><input id="j-thread" value="main" class="mc-field"></div>'
            f'<div><label class="mc-label">Cadence (cron, blank = on demand)</label><input id="j-cron" placeholder="E.g. 0 9 * * 1-5" class="mc-field"></div></div>'
            f'<label class="mc-label">Prompt (agent) or command (script)</label>'
            f'<textarea id="j-prompt" class="mc-textarea" style="min-height:150px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px"></textarea>'
            f'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" onclick="mcNewJob()">Create job</button>'
            f'<a href="/agent/{E(agent_id)}/jobs" class="btn btn-secondary" style="text-decoration:none">Cancel</a>'
            f'<span id="j-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div>')
    return _page_shell(realm, "Jobs", "New job", body, dark) + _NEW_JS




def _telegram_box() -> str:
    """Connect Telegram: one screen, three states, nothing to configure again afterwards.

    Two credential paths, because two kinds of person arrive here. Someone who already runs a bot
    points ARMADA at the file that holds its token — no second copy of a secret. Someone starting
    from nothing pastes a token from BotFather and ARMADA keeps it, outside every realm folder so a
    realm export can't carry it off. Either way the chat id is discovered rather than typed: you
    message the bot and press a button."""
    from .. import telegram as _tg
    st = _tg.status()
    fld = "font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px"
    intro = ('<div style="font-size:12.5px;color:var(--text-muted);line-height:1.55;margin:-2px 0 10px;'
             'max-width:640px">Message your agents from your phone. Send <code>/warren how exposed '
             'are we to tech?</code> and it lands in Warren\'s main thread — same context, same '
             'autonomy, same capabilities — and the answer comes back to the chat. It\'s a real '
             'thread turn, so it\'s in the app afterwards too.</div>')
    if st["linked"]:
        who = f" · linked to {E(st['chat_name'])}" if st["chat_name"] else ""
        src = {"environment": "from environment variables", "env file": f"reading {E(st['env_file'])}",
               "ARMADA": "token held by ARMADA"}.get(st["source"], st["source"])
        head = (f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
                f'{_pill("connected", "ok")}'
                f'<span style="font-size:12.5px">@{E(st["bot"]) or "your bot"}{who}</span>'
                f'<span style="font-size:11px;color:var(--text-muted)">· {src}</span></div>'
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
                f'<button class="btn btn-secondary btn-sm" '
                f'onclick="mcTgTest(this)">Send a test message</button>'
                f'<button class="btn btn-secondary btn-sm" '
                f'onclick="mcTgLink(this)">Re-link chat</button>'
                f'<button class="btn btn-secondary is-danger btn-sm" '
                f'onclick="mcTgForget(this)">Disconnect</button>'
                f'<span id="st-tg-msg" style="font-size:11.5px;color:var(--text-muted)"></span></div>')
        return intro + head
    # Not connected (or connected but not yet pointed at a chat).
    token_row = (
        f'<div style="margin-bottom:12px"><label class="mc-label" style="margin-top:0">Step 1 — bot token</label>'
        f'<div style="font-size:11px;color:var(--text-muted);margin:0 0 5px">Open Telegram, message '
        f'<b>@BotFather</b>, send <code>/newbot</code>, and paste what it gives you.</div>'
        f'<div style="display:flex;gap:8px;align-items:center">'
        f'<input id="st-tg-token" type="password" placeholder="123456789:AA…" class="mc-field" style="flex:1" '
        f'autocomplete="off" spellcheck="false">'
        f'<button class="btn btn-secondary btn-sm" style="white-space:nowrap" '
        f'onclick="mcTgToken(this)">Save token</button></div></div>')
    env_row = (
        f'<details style="margin-bottom:12px"><summary style="cursor:pointer;font-size:12px;'
        f'color:var(--color-accent)">Already have a bot wired into something else?</summary>'
        f'<div style="font-size:11px;color:var(--text-muted);margin:6px 0 5px;max-width:620px">'
        f'Point ARMADA at the file holding its credentials and it reads them when it needs them. '
        f'The file needs a <code>TELEGRAM_BOT_TOKEN</code> line, and a <code>TELEGRAM_CHAT_ID</code> '
        f'line if you have one. ARMADA stores the path, not the secret.</div>'
        f'<div style="display:flex;gap:8px;align-items:center">'
        f'<input id="st-tg-env" placeholder="D:\\path\\to\\.env" class="mc-field" style="flex:1" spellcheck="false">'
        f'<button class="btn btn-secondary btn-sm" style="white-space:nowrap" '
        f'onclick="mcTgEnv(this)">Use this file</button></div></details>')
    link_row = (
        f'<div style="{"" if st["configured"] else "opacity:.45;pointer-events:none"}">'
        f'<label class="mc-label" style="margin-top:0">Step 2 — link your chat</label>'
        f'<div style="font-size:11px;color:var(--text-muted);margin:0 0 5px;max-width:620px">'
        f'Send your bot any message, then press this. ARMADA reads the chat it came from and will '
        f'only ever listen to that one — a bot is reachable by anyone who knows its name.</div>'
        f'<button class="btn btn-primary" '
        f'onclick="mcTgLink(this)">I\'ve messaged the bot</button></div>')
    return (intro + token_row + env_row + link_row
            + '<div id="st-tg-msg" style="font-size:11.5px;color:var(--text-muted);margin-top:8px"></div>')


def _a2a_defaults_box(realm_root) -> str:
    """The realm-wide agent-to-agent switch and the two defaults every agent inherits.

    This is the other half of the per-agent section on an agent's Configure page: that one says
    "inherit realm default", and this is where the default lives. The realm switch is a harder stop
    than the per-agent one — off means no agent delegates to any other, whatever their own setting
    says — so the per-agent fields grey out but stay readable rather than being hidden."""
    from .. import inbox as _inbox
    cfg = _inbox._realm_cfg(realm_root)
    on = bool(cfg.get("enabled", True))
    cad = cfg.get("cadence") if cfg.get("cadence") in _inbox.CADENCES else _inbox.DEFAULT_CADENCE
    acc = cfg.get("accepts") if cfg.get("accepts") in _inbox.ACCEPTS else _inbox.DEFAULT_ACCEPTS
    cad_opts = "".join(f'<option value="{k}" {"selected" if k == cad else ""}>{E(lab)}</option>'
                       for k, lab in [("minute", "every minute"), ("hour", "hourly"),
                                      ("day", "daily"), ("off", "never — ignore inboxes")])
    acc_opts = "".join(f'<option value="{k}" {"selected" if k == acc else ""}>{E(lab)}</option>'
                       for k, lab in _inbox.ACCEPTS_CHOICES.items())
    return (f'<div style="display:flex;align-items:center;gap:10px;margin:-2px 0 6px">'
            f'<label class="mc-toggle" title="{"On — agents can hand each other tasks" if on else "Off — no agent delegates to any other"}">'
            f'<input type="checkbox" id="st-a2a" {"checked" if on else ""} onchange="mcStA2AToggle()">'
            f'<span class="mc-toggle-sl"></span></label>'
            f'<span style="font-size:12.5px">Let agents hand each other tasks</span></div>'
            f'<div style="font-size:11.5px;color:var(--text-muted);margin:0 0 10px;line-height:1.5;max-width:640px">'
            f'Delegated work is no more privileged than an agent\'s own — anything that changes the '
            f'realm still needs your approval. Switching this off stops it realm-wide, whatever an '
            f'individual agent is set to.</div>'
            f'<div id="st-a2a-fields" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;'
            f'align-items:start{"" if on else ";opacity:.45;pointer-events:none"}">'
            f'<div><label class="mc-label" style="margin-top:0">Default inbox reading</label>'
            f'<select id="st-a2a-cadence" class="mc-field">{cad_opts}</select>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">How soon an agent '
            f'acts on a task a teammate sends it. Checking costs nothing — an agent is only woken '
            f'when something is waiting.</div></div>'
            f'<div><label class="mc-label" style="margin-top:0">Agents accept tasks from</label>'
            f'<select id="st-a2a-accepts" class="mc-field">{acc_opts}</select>'
            f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Who may assign an '
            f'agent work. Any agent can override both of these on its own Configure page.</div></div>'
            f'</div>'
            + _STA2A_TOGGLE_JS)


def _approot_box() -> str:
    """The app root — one folder per machine, the outer boundary for the whole install.

    Lives in App settings rather than Realm settings on purpose: a realm can't choose whether to
    be inside it, only where inside it to sit.
    """
    from .. import approot
    root = approot.root()
    here = approot.exists()
    if root and here:
        note, colour = "Every realm lives in here.", "var(--text-muted)"
    elif root:
        note, colour = f"{root} isn't on this machine — realms can't start.", "var(--status-bad)"
    else:
        note, colour = ("Not set. Pick the folder ARMADA should work in before adding a realm.",
                        "var(--status-warn)")
    return (f'<div style="max-width:520px">'
            f'<label class="mc-label" style="margin-top:0">Root folder</label>'
            f'<div style="display:flex;gap:8px;align-items:center">'
            f'<input id="st-approot" value="{E(root)}" placeholder="D:\\Work2" class="mc-field" style="flex:1">'
            f'<button class="mc-frame" style="padding:7px 12px;border-radius:var(--r);font-size:12px;'
            f'cursor:pointer;white-space:nowrap" onclick="mcRootSave(this)">Save</button></div>'
            f'<div id="st-approot-msg" style="font-size:11px;color:{colour};margin-top:5px">{E(note)}</div>'
            f'<div style="font-size:11.5px;color:var(--text-muted);margin-top:8px;line-height:1.5">'
            f'The one folder on this machine ARMADA works in. Every realm has to live inside it, '
            f'so adding a realm from somewhere else is refused rather than half-working. One folder '
            f'to point at, and one to back up.</div></div>')


def _workspace_box(realm, cfg) -> str:
    """The realm's workspace root, and the state of its portability.

    Shown whether or not it's set, because "no workspace" is only fine if nothing needs one — and
    the box is where you find out which of those two you're in.
    """
    from .. import workspace as ws
    root = str(cfg.get("workspace") or "").strip()
    here = bool(root) and Path(root).is_dir()
    if root and here:
        note, colour = f"Found on this machine.", "var(--text-muted)"
    elif root:
        note, colour = f"Not found on this machine — jobs that use it will fail.", "var(--status-bad)"
    else:
        note, colour = ("Not set. Set this if your jobs read or write files outside the realm.",
                        "var(--text-muted)")
    return (f'<div style="margin-top:14px;max-width:520px">'
            f'<label class="mc-label">Workspace folder</label>'
            f'<div style="display:flex;gap:8px;align-items:center">'
            f'<input id="st-ws" value="{E(root)}" placeholder="D:\\Work" class="mc-field" style="flex:1">'
            f'<button class="mc-frame" style="padding:7px 12px;border-radius:var(--r);font-size:12px;'
            f'cursor:pointer;white-space:nowrap" onclick="mcWsSave(this)">Save</button></div>'
            f'<div id="st-ws-msg" style="font-size:11px;color:{colour};margin-top:5px">{E(note)}</div>'
            f'<div style="font-size:11.5px;color:var(--text-muted);margin-top:8px;line-height:1.5">'
            f'Write <code>{{workspace}}</code> in a job prompt instead of a full path and ARMADA '
            f'fills it in when the job runs. That way the job still works if this realm moves to '
            f'another computer — you set this folder once and every job follows.</div>'
            f'<div style="margin-top:8px">'
            f'<button class="mc-frame" style="padding:6px 11px;border-radius:var(--r);font-size:12px;'
            f'cursor:pointer;display:inline-flex;align-items:center;gap:6px" '
            f'onclick="mcWsMigrate(this)">{_icon("batch-job",18)}Make existing jobs portable…</button>'
            f'<span id="st-ws-mig" style="font-size:11px;color:var(--text-muted);margin-left:8px"></span>'
            f'</div></div>')


def render_settings(realm, realm_root, engine_ok, engine_detail, realms, dark=False) -> str:
    import armada as _m
    realm_root = Path(realm_root)
    cfg = json.loads((realm_root / "realm.json").read_text(encoding="utf-8-sig")) if (realm_root / "realm.json").exists() else {}
    provider = cfg.get("provider", "claude")
    dmodel = cfg.get("default_model", "Claude Opus 4.8")
    deffort = cfg.get("default_effort", "high")
    dfallback = cfg.get("default_fallback_model", "")
    dmaxbudget = cfg.get("default_max_budget_usd")
    dmaxbudget = "" if dmaxbudget in (None, "", 0) else str(dmaxbudget)

    def sect(title, body):
        return (f'<div class="mc-frame" style="border-radius:var(--r);padding:14px 16px;margin-bottom:14px">'
                f'<div class="mc-h-sect" style="margin-bottom:8px">{E(title)}</div>{body}</div>')

    try:
        from .. import telegram as _tgmod
        _tg_ready = _tgmod.ready()
    except Exception:  # noqa — an unreadable credential store must not break Settings
        swallowed(log, 'render_settings: failed; using a default')
        _tg_ready = False

    # --- Notifications: an event × channel grid -------------------------------------------------
    # A list of checkboxes stopped working once there was more than one destination. A grid says
    # the whole thing at a glance — one row per kind, one column per channel — and it's how every
    # tool that solved this problem before us does it.
    from .. import notify as _notify
    _grid = _notify.matrix(realm_root)
    _chans = list(_notify.CHANNELS.items())
    _off_chans = {c for c in _notify.CHANNELS if not _notify.channel_enabled(c)}

    def _hdr():
        cells = ""
        for cid, clab in _chans:
            dim = cid in _off_chans
            note = ('<div style="font-size:9.5px;font-weight:400;color:var(--text-muted)">off</div>'
                    if dim else "")
            cells += (f'<th style="padding:0 4px 7px;font-size:11px;font-weight:600;width:88px;'
                      f'text-align:center;{"opacity:.5;" if dim else ""}">'
                      f'<div style="cursor:pointer" onclick="mcNotifCol(\'{cid}\')" '
                      f'title="Tick or untick this whole column">{E(clab)}</div>{note}</th>')
        return f'<tr><th></th>{cells}</tr>'

    def _row(ev, meta):
        cells = ""
        for cid, _ in _chans:
            on = _grid.get(ev, {}).get(cid, False)
            cells += (f'<td style="text-align:center;padding:5px 4px">'
                      f'<input type="checkbox" class="st-notif" data-ev="{ev}" data-ch="{cid}" '
                      f'{"checked" if on else ""} style="cursor:pointer"></td>')
        return (f'<tr><td style="padding:5px 10px 5px 0;font-size:12.5px;line-height:1.35">'
                f'{E(meta["label"])}</td>{cells}</tr>')

    def _group(gid, title):
        rows = "".join(_row(ev, m) for ev, m in _notify.EVENTS.items() if m["group"] == gid)
        return (f'<tr><td colspan="{len(_chans)+1}" style="padding:12px 0 3px;font-size:10.5px;'
                f'font-weight:700;letter-spacing:.06em;text-transform:uppercase;'
                f'color:var(--text-muted)">{E(title)}</td></tr>{rows}')

    _hint = ("<span style='color:var(--text-muted)'> — switched off for this computer in "
             "App settings</span>") if _off_chans else ""
    _cross_on = _notify.cross_realm(realm_root)
    notif_box = (
        f'<div style="font-size:11.5px;color:var(--text-muted);margin:-2px 0 8px;line-height:1.5">'
        f'Pick what reaches you and where. Click a column heading to tick or untick it all.'
        f'{_hint}</div>'
        f'<table style="border-collapse:collapse">{_hdr()}'
        f'{_group(_notify.AGENTS, "Your agents")}'
        f'{_group(_notify.SYSTEM, "ARMADA itself")}</table>'
        # One test per channel: "does this reach me?" is a different question for each destination,
        # and a single button could only ever answer it for one of them.
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:12px">'
        f'<span style="font-size:11.5px;color:var(--text-muted)">Send a test notification:</span>'
        + "".join(f'<button type="button" class="btn btn-secondary" '
                  f'style="font-size:12px;padding:5px 11px" onclick="mcNotifTest(this,\'{cid}\')"'
                  f'{" disabled" if cid in _off_chans else ""}>{E(clab)}</button>'
                  for cid, clab in _chans)
        + f'</div><span id="st-notif-msg" style="font-size:11.5px;color:var(--text-muted);'
          f'display:inline-block;margin-top:6px"></span>'
        # Jobs fire in every realm whether or not you're looking at it, so by default their
        # notifications follow you out of it. Off means this realm only speaks while you're in it.
        + f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--color-divider)">'
          f'<div style="display:flex;align-items:center;gap:10px">'
          f'<label class="mc-toggle" title="{"On — this realm notifies you wherever you are" if _cross_on else "Off — this realm only notifies you while you are viewing it"}">'
          f'<input type="checkbox" id="st-notif-cross" {"checked" if _cross_on else ""}>'
          f'<span class="mc-toggle-sl"></span></label>'
          f'<span style="font-size:12.5px;font-weight:600">Notify cross-realms</span></div>'
          f'<div style="font-size:11.5px;color:var(--text-muted);margin-top:5px;line-height:1.5;'
          f'max-width:560px">Desktop and Telegram notifications from {E(realm.name)} reach you even '
          f'when you are viewing another realm. Switch it off and they only arrive while this realm '
          f'is the one you are in — the bell keeps every one of them either way, so nothing is lost, '
          f'it just waits for you here.</div></div>')

    # --- Realm settings tab ---
    def _realm_manage_box(realm_obj, root) -> str:
        """Archive / export / delete, ordered from harmless to irreversible and described that way
        — the consequence should be obvious before the click, not after."""
        p = E(str(root))
        nm = E(Path(root).name)

        def act(label, desc, btn, onclick, danger=False):
            col = "var(--status-bad)" if danger else "var(--color-text)"
            return (f'<div style="display:grid;grid-template-columns:1fr auto;gap:14px;'
                    f'align-items:center;padding:10px 0;border-top:1px solid var(--color-divider)">'
                    f'<div><div style="font-size:12.5px;font-weight:600;color:{col}">{E(label)}</div>'
                    f'<div style="font-size:11.5px;color:var(--text-muted);margin-top:2px;'
                    f'line-height:1.45">{E(desc)}</div></div>'
                    f'<button type="button" class="btn btn-secondary btn-sm" style="'
                    f'white-space:nowrap'
                    f'{";color:var(--status-bad);border-color:var(--status-bad)" if danger else ""}" '
                    f'onclick="{onclick}">{E(btn)}</button></div>')
        return (
            f'<div style="font-size:11.5px;color:var(--text-muted);margin:-2px 0 4px">'
            f'<span class="mono">{p}</span></div>'
            # Each row says "realm" outright. "Delete…" on its own, on a page with a dozen other
            # things on it, doesn't tell you what is about to be deleted.
            + act("Export realm", "Write a .zip of every file in this realm — memory, threads, jobs "
                                  "and artefacts. Use it to move to another computer, or as a backup "
                                  "before you change anything big.",
                  "Export realm…", "mcRealmExport(this)")
            + act("Archive realm", "Remove this realm from ARMADA's list without touching a single "
                                   "file. The folder stays where it is and you can add it back at "
                                   "any time.",
                  "Archive realm…", f"mcRealmArchive(this,'{p}')")
            + act("Delete realm", f"Delete the folder and everything in it. On Windows it goes to the "
                            f"Recycle Bin, so it can be recovered — but nothing inside ARMADA will "
                            f"bring it back. You'll be asked to type “{Path(root).name}” "
                            f"to confirm.",
                  "Delete realm…", f"mcRealmDelete(this,'{p}','{nm}')", danger=True))

    realm_opts = "".join(f'<option value="{E(r["path"])}" {"selected" if r["path"]==str(realm_root) else ""}>{E(r["name"])}</option>'
                         for r in realms) or f'<option selected>{E(realm.name)}</option>'
    # Engines a realm can run on. Multi-select now so that adding a second one (Codex, say) is a
    # list entry rather than a reshape of the setting — and so the stored value is already a list.
    _ENGINES = [("claude", "Claude — Max/Pro subscription", True),
                ("codex", "OpenAI Codex", False)]
    _enabled_engines = cfg.get("providers")
    if not isinstance(_enabled_engines, list) or not _enabled_engines:
        _enabled_engines = [provider]            # carry the old single value forward
    _soon_pill = _pill("soon", style="margin-left:2px")

    def _prov_row(v, lab, avail):
        cur = "pointer" if avail else "not-allowed"
        return (f'<label style="display:flex;align-items:center;gap:9px;font-size:12.5px;'
                f'margin:6px 0;cursor:{cur};{"" if avail else "opacity:.5"}">'
                f'<input type="checkbox" class="st-prov" value="{v}" '
                f'{"checked" if v in _enabled_engines else ""}{"" if avail else " disabled"} '
                f'style="cursor:{cur}">{E(lab)}{"" if avail else _soon_pill}</label>')
    prov_opts = "".join(_prov_row(v, lab, avail) for v, lab, avail in _ENGINES)
    model_opts = _model_options(realm_root, dmodel)
    eff_opts = "".join(f'<option {"selected" if e==deffort else ""}>{E(e)}</option>' for e in _EFFORTS)
    fb_opts = '<option value="">None (no fallback)</option>' + _model_options(realm_root, dfallback)
    from .. import verbosity as _verbosity
    _dverb = _verbosity.realm_level(realm_root)
    verb_opts = "".join(
        f'<option value="{k}" {"selected" if k == _dverb else ""}>{E(lab)} — {E(desc)}</option>'
        for k, (lab, desc, _p) in _verbosity.LEVELS.items())
    # Which tile is the realm's current icon, so the choice is visible on load rather than only
    # after you click one. An uploaded image isn't in the set, so nothing is marked in that case.
    _uploaded = any((realm_root / f"icon.{x}").exists() for x in ("png", "jpg", "jpeg", "webp", "svg"))
    _cur_icon = "" if _uploaded else str(getattr(realm, "theme_icon", "") or "")
    icon_tiles = "".join(
        f'<span class="mc-seticon" data-icon="{ic}" onclick="mcPickSetIcon(this)" title="{ic}" '
        f'style="cursor:pointer;padding:4px;border-radius:var(--r);display:inline-flex;'
        f'{_SETICON_ON if ic == _cur_icon else ""}'
        f'color:var(--text-strong)">{_icon(ic,20)}</span>' for ic in _REALM_ICON_NAMES)
    # Realm picker and its icon are the same subject and both narrow, so they share a row.
    realm_tab = (
        sect("Realm",
             f'<div style="display:grid;grid-template-columns:minmax(240px,1fr) minmax(400px,1.3fr);'
             f'gap:22px;align-items:start">'
             f'<div><label class="mc-label" style="margin-top:0">Active realm</label>'
             f'<select id="st-realm" class="mc-field" onchange="if(this.value)location.href=\'/switch?to=/settings&path=\'+encodeURIComponent(this.value)">{realm_opts}</select>'
             # The name, directly under the picker that shows it. It is a label rather than an
             # identity: the folder is what everything else is keyed on, so renaming is free and
             # breaks nothing — no job, memory or run report refers to a realm by name.
             f'<label class="mc-label">Name</label>'
             f'<input id="st-realmname" value="{E(realm.name)}" maxlength="60" '
             f'placeholder="{E(Path(realm_root).name)}" class="mc-field">'
             f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">'
             f'What this realm is called in the switcher, the window and your agents\' briefings. '
             f'The folder it lives in doesn\'t change.</div></div>'
             # Current icon, Upload and the whole tile set on one line — the tiles were a second
             # row of mostly empty space. They wrap only if the column is genuinely too narrow.
             f'<div><label class="mc-label" style="margin-top:0">Realm icon</label>'
             f'<div style="display:flex;gap:2px;align-items:center;flex-wrap:wrap">'
             f'<span id="st-iconcur" style="display:flex;color:var(--text-strong);margin-right:2px">{_realm_icon(realm, 22)}</span>'
             f'<label class="mc-frame" style="cursor:pointer;padding:5px 10px;border-radius:var(--r);font-size:12px;white-space:nowrap;margin-right:4px">'
             f'Upload…<input type="file" accept="image/*" style="display:none" onchange="mcUploadRealmIcon(this)"></label>'
             f'{icon_tiles}</div>'
             f'<span id="ri-msg" style="font-size:11.5px;color:var(--text-muted)"></span></div>'
             f'</div>'
             # Timezone belongs to the realm, not to you: it is what the scheduler runs jobs
             # against, and a realm you keep for work abroad should be able to differ from one
             # you keep at home. It was already stored in realm.json — only the UI filed it
             # under your profile.
             f'<div style="margin-top:14px;max-width:340px">'
             f'<label class="mc-label">Timezone</label>'
             f'<select id="st-tz" onchange="mcTzUpdate()" class="mc-field" style="height:36px">{_tz_options(cfg.get("timezone", ""))}</select>'
             f'<div id="us-tz-time" style="font-size:11px;color:var(--text-muted);margin-top:5px">'
             f'Job schedules in this realm will be based on this time.</div></div>')
        + sect("AI provider & defaults",
               f'<div style="font-size:11.5px;color:var(--text-muted);margin:-2px 0 10px">'
               f'Agents and threads inherit these unless you make specific agent and thread-level settings.</div>'
               f'<label class="mc-label" style="margin-top:0">AI providers</label>'
               f'<div id="st-provider" style="margin:2px 0 4px">{prov_opts}</div>'
               f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
               f'<div><label class="mc-label">Default model</label><select id="st-model" class="mc-field">{model_opts}</select></div>'
               f'<div><label class="mc-label">Default thinking</label><select id="st-effort" class="mc-field">{eff_opts}</select></div></div>'
               f'<div style="margin-top:12px;max-width:420px"><label class="mc-label">Default verbosity</label>'
               f'<select id="st-verbosity" class="mc-field">{verb_opts}</select>'
               f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">How much your agents '
               f'write back. It never changes how much work they do, and failures, warnings and anything '
               f'needing your approval are always spelled out in full.</div></div>'
               f'<div id="st-cons" style="margin-top:12px"><label class="mc-label">Relative token consumption '
               f'<span style="text-transform:none;letter-spacing:0;color:var(--text-muted)">· default model, effort &amp; verbosity</span></label>'
               f'<div style="display:flex;align-items:center;gap:10px">'
               f'<span class="mc-modelmark" style="display:inline-flex;color:var(--text-muted)">{_icon("claude", 16)}</span>'
               f'<div style="position:relative;flex:1;height:12px;border-radius:6px;background:{_consumption_gradient_css()}">'
               f'<div id="st-consmarker" style="position:absolute;top:-3px;left:0%;transform:translateX(-50%);width:4px;height:18px;'
               f'border-radius:3px;background:var(--color-text);box-shadow:0 0 0 2px var(--color-bg)"></div></div>'
               f'<span style="font-size:10px;color:var(--text-muted);white-space:nowrap">low → high</span></div></div>')
        + sect("Agent-to-agent communication", _a2a_defaults_box(realm_root))
        + sect("Notifications", notif_box)
        # Realm management lives INSIDE Advanced — folded away behind a deliberate click, because
        # one of the things in it deletes everything.
        + ('<details class="mc-frame" id="st-advanced" ontoggle="mcRevealSection(this)" '
           'style="border-radius:var(--r);padding:14px 16px;margin-bottom:14px">'
           '<summary style="cursor:pointer;font-family:var(--font-heading);font-weight:600;font-size:15px">Advanced</summary>'
           '<div style="font-size:11.5px;color:var(--text-muted);margin:8px 0 10px">'
           'Optional guardrails passed to Claude Code on every run. Agents inherit these unless overridden per agent.</div>'
           f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
           f'<div><label class="mc-label" style="margin-top:0">Fallback model</label><select id="st-fallback" class="mc-field">{fb_opts}</select>'
           f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Switches to this model if the default is overloaded or unavailable.</div></div>'
           f'<div><label class="mc-label" style="margin-top:0">Max budget — USD per run</label><input id="st-maxbudget" type="number" min="0" step="0.01" value="{E(dmaxbudget)}" placeholder="no cap" class="mc-field">'
           f'<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Hard spend ceiling for a single run. Blank or 0 = no cap.</div></div>'
           '</div>'
           # The one machine-specific thing a realm carries, and the only setting on this page that
           # is about the machine rather than the realm: jobs written against {workspace} follow the
           # realm to another computer, jobs with a drive letter in them don't. It was sitting under
           # Realm identity, where it read as a routine field — it is neither routine nor identity.
           f'<div style="margin-top:20px;padding-top:14px;border-top:1px solid var(--color-divider)">'
           f'<div style="font-family:var(--font-heading);font-weight:600;font-size:14px;'
           f'margin-bottom:2px">Workspace &amp; portability</div>'
           f'{_workspace_box(realm, cfg)}</div>'
           f'<div style="margin-top:20px;padding-top:14px;border-top:1px solid var(--color-divider)">'
           f'<div style="font-family:var(--font-heading);font-weight:600;font-size:14px;'
           f'margin-bottom:2px">Manage this realm</div>'
           f'{_realm_manage_box(realm, realm_root)}</div>'
           '</details>'
           + _REVEAL_JS)
        + f'<button class="btn btn-primary" onclick="mcSaveRealmSettings()">Save realm settings</button>'
          f'<span id="st-msg" style="font-size:12px;margin-left:10px;color:var(--text-muted)"></span>')

    # --- App settings tab ---
    edot = "var(--status-ok)" if engine_ok else "var(--status-bad)"
    engine_short = str(engine_detail).split(" — launcher")[0].split("launcher:")[0].strip(" —")
    ver = _m.__version__
    from .. import updater as _updater
    _installed = _updater.installed()
    _upd_hint = ("New versions are downloaded and checked in the background, and install the next time "
                 "ARMADA starts. Check for updates asks now." if _installed else
                 "Restart reloads the app with the current local code (use after a change). Check for "
                 "updates pulls from git — this is a development copy.")
    version_box = (
        f'<div style="margin-bottom:10px">{brand.WORDMARK_SMALL}</div>'
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
        f'<div style="font-size:12.5px;display:flex;align-items:center;gap:6px"><b>v{ver}</b>{brand.BETA_PILL}</div>'
        f'<button class="btn btn-secondary btn-sm" onclick="mcRestart(this)">{_icon("refresh-cw",13)}Restart</button>'
        f'<button class="btn btn-secondary btn-sm" onclick="mcCheckUpd(this)">{_icon("download",13)}Check for updates</button>'
        f'<a onclick="mcChangelog(true)" style="cursor:pointer;font-size:12px;color:var(--color-accent);display:inline-flex;align-items:center;gap:4px">{_icon("book-open",13)}Changelog</a>'
        f'<span id="mc-updcheck" style="font-size:12px;color:var(--text-muted)"></span></div>'
        # The tick for "Using the latest version" (settings.js copies it; this page has no mcIcon).
        f'<template id="mc-ico-ok">{_icon("circle-check-fill", 13)}</template>'
        f'<div style="font-size:11px;color:var(--text-muted);margin-top:6px">{E(_upd_hint)}</div>'
        f'<div id="mc-updbox" style="display:none;margin-top:10px">'
        f'<button class="btn btn-primary" id="mc-updbtn" onclick="mcUpd(this)">{_icon("download",14)}Update &amp; Restart</button>'
        f'<span id="mc-updmsg" style="font-size:12px;margin-left:10px;color:var(--text-muted)"></span></div>')

    def prov_row(icon, name, detail, status):
        ok = status == "connected"
        lab = "Connected" if ok else "Coming soon"
        return (f'<div style="display:flex;align-items:center;gap:10px;padding:8px 4px;border-bottom:1px solid var(--color-divider)">'
                f'<span style="display:flex;color:var(--text-strong)">{icon}</span>'
                f'<div style="flex:1"><span style="font-size:12.5px;font-weight:600">{E(name)}</span>'
                f'<div style="font-size:11px;color:var(--text-muted)">{E(detail)}</div></div>'
                f'{_pill((_icon("circle-check",11) if ok else _icon("info",11)) + lab, "ok" if ok else "neutral")}</div>')
    engine_box = (
        prov_row(_icon("claude", 16), "Anthropic — Claude", engine_short or "Claude Code", "connected" if engine_ok else "error")
        + prov_row(_icon("zap", 16), "OpenAI — Codex", "GPT engine", "soon"))

    cur_theme = appconfig.get("theme", vtheme.DEFAULT)
    theme_cards = ""
    for _tid, _t in vtheme.THEMES.items():
        _a, _a2 = vtheme.swatch(_tid)
        _sel = _tid == cur_theme
        theme_cards += (
            # Fixed width + a reserved caption line: the card must not resize when it becomes
            # selected, or picking a theme reflows the whole grid under the cursor.
            f'<div class="mc-themecard" onclick="mcSetTheme(\'{_tid}\')" title="{E(_t["name"])}" '
            f'style="cursor:pointer;border:1px solid {"var(--color-accent)" if _sel else "var(--color-divider)"};'
            f'border-radius:var(--r);padding:10px 12px;display:flex;align-items:center;gap:9px;'
            f'width:186px;box-sizing:border-box;flex:none;'
            f'{"background:var(--color-accent-100)" if _sel else ""}">'
            f'<span style="width:30px;height:30px;border-radius:50%;flex:none;'
            f'background:linear-gradient(135deg,{_a} 0 50%,{_a2} 50% 100%)"></span>'
            f'<div style="min-width:0">'
            f'<div style="font-size:12.5px;font-weight:600;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis">{E(_t["name"])}</div>'
            f'<div style="font-size:11px;color:var(--text-muted);white-space:nowrap">'
            f'{"selected" if _sel else "&#8203;"}</div></div></div>')

    _mode = _layout.appearance_mode()
    appearance = (
        f'<label class="mc-label" style="margin-top:0">Colour mode</label>'
        f'<div style="display:flex;gap:8px;align-items:center">'
        + "".join(f'<label class="mc-appmode" style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;'
                  f'border:1px solid var(--color-divider);border-radius:var(--r);padding:7px 12px;font-size:12.5px;line-height:1">'
                  # Checked from the SAVED mode, not from how this page happens to be rendering.
                  # Deriving it from `dark` meant System could never show as selected: it renders
                  # light, so the radio snapped back to Light the moment you chose it.
                  f'<input type="radio" name="mc-mode" value="{v}" style="margin:0" {"checked" if v==_mode else ""} onchange="mcSetMode(\'{v}\')">'
                  f'<span style="display:flex;color:var(--text-dim)">{_icon(ic,15)}</span>{lab}</label>'
                  for v, lab, ic in [("light", "Light", "sun"), ("dark", "Dark", "moon"), ("system", "System", "monitor")])
        + '</div>'
        f'<label class="mc-label">Colour theme</label>'
        f'<div style="display:flex;gap:10px;flex-wrap:wrap">{theme_cards}</div>'
        + _font_picker())

    # Channels live here (per machine); *which events* notify stays with the realm.
    def chan(cid, label, desc, on, disabled=False, soon=False):
        badge = _pill("soon", style="margin-left:7px") if soon else ""
        return (f'<div style="display:flex;align-items:flex-start;gap:10px;margin:9px 0;'
                f'opacity:{".55" if disabled else "1"}">'
                f'<input id="{cid}" type="checkbox" {"checked" if on else ""}'
                f'{" disabled" if disabled else ""} onchange="mcSaveChannels()" '
                f'style="margin-top:2px;cursor:{"not-allowed" if disabled else "pointer"}">'
                f'<label for="{cid}" style="cursor:{"not-allowed" if disabled else "pointer"}">'
                f'<div style="font-size:12.5px;font-weight:600">{E(label)}{badge}</div>'
                f'<div style="font-size:11px;color:var(--text-muted);margin-top:1px">{E(desc)}</div>'
                f'</label></div>')
    channels = (
        chan("st-ch-inapp", "In-app notifications",
             "The bell in the top bar — ARMADA's own record of what happened.",
             _notify.channel_enabled("inapp"))
        + chan("st-ch-desktop", "Desktop notifications",
               "Windows notifications from ARMADA. Nothing leaves this machine.",
               _notify.channel_enabled("desktop"))
        + chan("st-ch-telegram", "Telegram notifications",
               "Send alerts to Telegram, so they reach you away from this computer.",
               _notify.channel_enabled("telegram"),
               disabled=not _tg_ready, soon=False)
        + ("" if _tg_ready else
           '<div style="font-size:11px;color:var(--text-muted);margin:-4px 0 4px 26px">'
           'Connect Telegram above to switch this on.</div>')
        + f'<div style="font-size:11px;color:var(--text-muted);margin-top:8px">'
          f'These switch a whole channel off on this computer. Choose <i>which</i> events go to '
          f'each one under Realm → Notifications.</div>'
        + f'<span id="st-ch-msg" style="font-size:11.5px;color:var(--text-muted)"></span>')

    app_tab = (
        sect("Version", version_box)
        # First, because it's the setting everything else sits inside — and the one a fresh
        # install has to answer before a realm can exist at all.
        + sect("Root folder", _approot_box())
        + sect("About", f'<div style="font-size:12.5px;line-height:1.55">{E(_ABOUT)}</div>'
               f'<div style="font-size:12px;line-height:1.55;margin-top:8px;color:var(--text-muted)">'
               f'{E(brand.LICENCE)} <a href="{E(brand.LICENCE_URL)}" target="_blank" rel="noopener" '
               f'style="color:var(--color-accent)">Licence terms ↗</a> · Third-party notices are in '
               f'<code>THIRD_PARTY_NOTICES.md</code> in the install folder.</div>')
        + sect("Engine", f'<div style="font-size:11.5px;color:var(--text-muted);margin-bottom:6px">'
               f'Per-provider engine status. ARMADA runs on your own subscription.</div>{engine_box}')
        # Telegram sits with Engine: both are "what ARMADA is connected to", and it reads better
        # above Notifications, which refers to it.
        + sect("Telegram", _telegram_box())
        + sect("Notifications", channels)
        + sect("Appearance", appearance)
        + _app_advanced(_updater))

    # --- User settings tab ---
    u = _user(realm_root)
    uav_prev = _user_avatar(realm_root, 64) or _bust(64, False)
    _gsel = u.get("gender", "") or "Prefer not to say"   # default when unset
    gender_opts = "".join(f'<option {"selected" if g == _gsel else ""}>{E(g)}</option>'
                          for g in ["Prefer not to say", "Male", "Female", "Non-binary"])
    ufh = "height:36px"   # one height across name / tz / gender / birthdate
    remove_btn = (f'<button class="btn btn-secondary is-danger btn-sm" onclick="mcRemoveUserAvatar()">Remove</button>'
                  if _user_avatar_file(realm_root) else "")
    user_tab = sect("Your profile",
        f'<div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:6px">'
        f'<div id="us-avatar-prev" style="width:64px;height:64px;border-radius:50%;overflow:hidden;border:1px solid var(--color-divider);background:var(--color-accent-100);flex:none">{uav_prev}</div>'
        f'<div style="flex:1"><label class="mc-label" style="margin-top:0">Avatar (optional)</label>'
        f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
        f'<button class="btn btn-secondary btn-sm" onclick="document.getElementById(\'us-avatar\').click()">Choose file…</button>'
        f'<button class="btn btn-secondary btn-sm" onclick="mcUserAvatarModal(true)">Pick from set</button>'
        f'{remove_btn}'
        f'<input type="file" id="us-avatar" accept="image/*" style="display:none" onchange="mcUploadUserAvatar(this)"></div>'
        f'<div id="us-avatarmsg" style="font-size:11.5px;color:var(--text-muted);margin-top:4px">Shown instead of “You” in threads. Cropped square &amp; optimized.</div></div></div>'
        + _user_avatar_modal() +
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start">'
        f'<div><label class="mc-label">Name</label><input id="us-name" value="{E(u.get("name", ""))}" placeholder="Your name" class="mc-field"></div>'
        f'<div><label class="mc-label">Gender (optional)</label><select id="us-gender" class="mc-field">{gender_opts}</select></div>'
        f'<div><label class="mc-label">Birthdate (optional)</label><input type="date" id="us-bday" min="1930-01-01" max="2020-12-31" value="{E(u.get("birthdate", ""))}" class="mc-field"></div></div>'
        # Free text, because the useful things about a person don't fit in four fields. It lands in
        # the system memory every agent reads, so it's worth saying what that means before they
        # type — this is not a private note.
        f'<div style="margin-top:14px"><label class="mc-label" style="margin-top:0">About you</label>'
        f'<div style="font-size:11.5px;color:var(--text-muted);margin:0 0 5px;line-height:1.5;max-width:640px">'
        f'Anything you want every agent to know about you — how you work, what you care about, how '
        f'to talk to you, constraints they should respect. Every agent in this realm reads it, so '
        f'leave out anything you wouldn\'t want in a prompt.</div>'
        f'<textarea id="us-about" rows="5" placeholder="E.g. I think in writing and prefer a draft I can react to over a list of options. I work in English and Spanish. Don\'t hedge — tell me when something is a bad idea." '
        f'class="mc-textarea" style="min-height:96px">{E(u.get("about", ""))}</textarea></div>'
        f'<div style="margin-top:14px;display:flex;gap:8px;align-items:center">'
        f'<button class="btn btn-primary" onclick="mcSaveUser()">Save user settings</button>'
        f'<span id="us-msg" style="font-size:12px;color:var(--text-muted)">The source of truth — collected at setup, editable here. Saved to the realm and the agents’ core memory.</span></div>')

    # Creating a realm isn't a setting of the realm you're in — it sits with the page, not inside
    # the Realm section where it read as one of that realm's options.
    new_realm_btn = ('<button type="button" class="btn btn-secondary btn-sm" style="white-space:nowrap" '
                     f'onclick="mcNewRealmOpen(event)">{_icon("plus", 14)}New realm</button>')
    # A touch wider than the other pages so the nine realm-icon tiles sit on one line with the
    # current icon and Upload, instead of wrapping onto a row of their own.
    body = (f'<div style="padding:18px 24px 24px;max-width:900px">'
            f'{_page_title("Settings", right_html=new_realm_btn)}'
            f'<div style="border-bottom:1px solid var(--color-divider);margin-bottom:16px">'
            # The same tabs as Capabilities' (DESIGN_SYSTEM §12, UI audit TB1).
            f'<div role="tablist">'
            f'<button type="button" role="tab" id="st-tab-realm" class="mc-captab" aria-selected="true" onclick="mcSetTab(\'realm\')">Realm settings</button>'
            f'<button type="button" role="tab" id="st-tab-user" class="mc-captab" aria-selected="false" onclick="mcSetTab(\'user\')">User settings</button>'
            f'<button type="button" role="tab" id="st-tab-app" class="mc-captab" aria-selected="false" onclick="mcSetTab(\'app\')">App settings</button></div></div>'
            f'<div id="st-realm-pane">{realm_tab}</div>'
            f'<div id="st-user-pane" style="display:none">{user_tab}</div>'
            f'<div id="st-app-pane" style="display:none">{app_tab}</div></div>'
            + _changelog_modal(ver) + _SETTINGS_JS + _USER_JS + _REALM_ICON_JS
            + _consumption_js(realm, "st-model", "st-effort", "st-consmarker", "#st-cons",
                           verbosity_id="st-verbosity"))
    return _page_shell(realm, "", "Settings", body, dark)


def _font_picker() -> str:
    """Appearance → Fonts (temporary, v0.99.62; becomes part of themes/skins). A face applies the
    moment it's picked — loaded first, then swapped, so nothing flashes — and is saved per machine."""
    from .. import fonts
    def sel(role, label):
        opts = "".join(f'<option value="{E(k)}"{" selected" if k == fonts.selected(role) else ""}>{E(v)}</option>'
                       for k, v in fonts.CHOICES.items())
        fams = E(json.dumps({k: fonts.family(role, k) for k in fonts.CHOICES}))
        return (f'<label class="mc-fontpick"><span class="mc-hint">{label}</span>'
                f'<select class="mc-field" data-role="{role}" data-families="{fams}" '
                f'onchange="mcSetFont(this)">{opts}</select></label>')
    return (f'<label class="mc-label">Fonts <span style="text-transform:none;letter-spacing:0">'
            f'(trial — these will become part of themes)</span></label>'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end">'
            f'{sel("heading", "Headings")}{sel("body", "Body text")}'
            f'<span id="mc-font-msg" class="mc-hint"></span></div>'
            f'<div class="mc-fontsample mc-frame"><div class="mc-h-card" style="margin:0 0 4px">'
            f'The quick brown fox · Overview · Jobs</div>'
            f'<div style="font-size:12.5px">Agents, memories and scheduled jobs — 0123456789. '
            f'<b>Bold</b>, <span style="font-weight:500">medium</span>, regular.</div></div>')


def render_new_realm(realm, dark=False, embed=False) -> str:
    from ..templates import TEMPLATES
    presets = {k: {"icon": t["theme"]["icon"], "collective": t["theme"]["collective"],
                   "agent": t["theme"]["agent"], "coordinator": t["theme"]["coordinator"],
                   "agents": [{"id": a.get("id", ""), "display": a["display"], "role": a.get("role", ""),
                               "leader": a.get("leader", ""), "coordinator": bool(a.get("coordinator")),
                               "mandate": a.get("mandate", ""), "voice": a.get("voice", ""),
                               "skills": a.get("skills", [])} for a in t["agents"]]}
               for k, t in TEMPLATES.items()}
    tpl_labels = {"state": "State", "company": "Company", "crew": "Crew", "scratch": "Scratch"}
    cards = "".join(
        f'<div class="mc-tplcard mc-frame" data-tpl="{k}" onclick="mcPickTpl(this)" style="cursor:pointer;'
        f'border-radius:var(--r);padding:12px;text-align:center;flex:1">'
        f'<div style="display:flex;justify-content:center;color:var(--color-accent)">{_icon(TEMPLATES[k]["theme"]["icon"],26)}</div>'
        f'<div style="font-family:var(--font-heading);font-weight:600;font-size:14px;margin-top:6px">{tpl_labels.get(k,k.title())}</div>'
        f'<div style="font-size:10.5px;color:var(--text-muted)">{E(TEMPLATES[k]["theme"]["collective"])} · {E(TEMPLATES[k]["theme"]["agent"])}s</div></div>'
        for k in TEMPLATES)
    icon_pick = "".join(f'<span class="mc-iconpick" data-icon="{ic}" onclick="mcPickIcon(this)" title="{ic}" '
                        f'style="cursor:pointer;padding:6px;border-radius:var(--r);display:inline-flex;'
                        f'color:var(--text-strong)">{_icon(ic,22)}</span>' for ic in _REALM_ICON_NAMES)
    icon_pick += ('<label class="mc-frame" style="cursor:pointer;padding:6px 10px;border-radius:var(--r);font-size:11.5px;'
                  'display:inline-flex;align-items:center;gap:5px;margin-left:6px">Upload…'
                  '<input type="file" id="r-iconfile" accept="image/*" style="display:none" onchange="mcWizIcon(this)"></label>'
                  '<span id="r-iconprev" style="margin-left:6px;display:inline-flex;vertical-align:middle"></span>')

    step1 = (f'<div id="wiz-1"><label class="mc-label">Mode</label>'
             f'<select id="r-mode" class="mc-field" onchange="mcMode()"><option value="create">Create new</option>'
             f'<option value="adopt">Adopt an existing folder</option></select>'
             f'<label class="mc-label">Name {_STAR}</label><input id="r-name" placeholder="E.g. Personal / Business" class="mc-field">'
             f'<div id="r-createonly"><label class="mc-label">Template</label>'
             f'<div style="display:flex;gap:10px">{cards}</div>'
             f'<label class="mc-label">Icon</label><div style="display:flex;flex-wrap:wrap;gap:2px">{icon_pick}</div></div>'
             f'<label class="mc-label">Folder (absolute path) {_STAR}</label>'
             f'<div style="display:flex;gap:8px"><input id="r-path" placeholder="E.g. D:\\Work\\MyRealm" class="mc-field" style="flex:1">'
             f'<button class="btn btn-secondary" style="white-space:nowrap" onclick="mcBrowse()">Browse…</button></div>'
             f'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
             f'<button class="btn btn-primary" onclick="mcNext()">Next →</button>'
             f'<button type="button" class="btn btn-secondary" style="cursor:pointer" onclick="mcWizCancel()">Cancel</button>'
             f'<span id="r-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div>')

    step2 = (f'<div id="wiz-2" style="display:none"><div id="r-agents-intro" style="font-size:12.5px;'
             f'color:var(--text-dim);margin-bottom:8px"></div>'
             f'<div id="r-agents"></div>'
             f'<button class="btn btn-secondary btn-sm" style="margin-top:8px" onclick="mcAddAgentRow()">+ Add your own</button>'
             f'<div style="margin-top:12px;font-size:11.5px;color:var(--text-muted)">These and other settings can be '
             f'made/edited later in the Settings &rsaquo; Realm section.</div>'
             f'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
             f'<button class="btn btn-secondary" onclick="mcBack()">← Back</button>'
             f'<button class="btn btn-primary" onclick="mcFinish()">Create realm</button>'
             f'<span id="r-msg2" style="font-size:12px;color:var(--text-muted)"></span></div></div>')

    # step indicator (1/2 · 2/2) — mcWizStep() highlights the current one as the wizard advances
    stepbar = ('<div id="wiz-steps" style="display:flex;gap:8px;margin-bottom:16px">'
               '<div class="wiz-step" data-s="1" onclick="mcWizStepClick(1)" style="flex:1;padding:7px 10px;border-radius:var(--r);'
               'font-size:12px;font-weight:600;text-align:center;cursor:pointer">Step 1 of 2 · Realm</div>'
               '<div class="wiz-step" data-s="2" onclick="mcWizStepClick(2)" style="flex:1;padding:7px 10px;border-radius:var(--r);'
               'font-size:12px;font-weight:600;text-align:center;cursor:pointer">Step 2 of 2 · Staff</div></div>')
    intro = (f'<div style="font-size:12.5px;color:var(--text-dim);margin-bottom:12px">'
             f'Create a fresh realm from a template — pick a model, then choose who staffs it — or adopt an existing folder.</div>')
    scripts = f'<script>const MC_PRESETS={json.dumps(presets)};</script>' + _WIZ_JS
    if embed:                                        # chrome-less body for the dashboard modal iframe
        inner = f'<div style="padding:16px 20px 22px">{stepbar}{intro}{step1}{step2}</div>{scripts}'
        body_cls = "armada-dark" if dark else ""
        return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">{_CSS_LINKS}{_theme_style()}'
                f'<style>html,body{{margin:0;background:var(--color-bg)}}</style></head>'
                f'<body class="{body_cls}">{inner}{_FORM_JS}</body></html>')
    body = (f'<div style="padding:18px 24px 24px;max-width:760px">{_page_title("New realm")}'
            f'{stepbar}{intro}{step1}{step2}</div>{scripts}')
    return _page_shell(realm, "", "New realm", body, dark)


def render_add_section(realm, dark=False) -> str:
    body = (f'<div style="padding:18px 24px 24px;max-width:680px">{_page_title("Add a section")}'
            f'<div style="font-size:12.5px;color:var(--text-dim);margin-bottom:12px">'
            f'Promote a page or artifact to the top menu — e.g. your Daily Digest or State of the Realm. '
            f'Point it at a file in the realm (HTML/Markdown) or a URL.</div>'
            f'<label class="mc-label">Name {_STAR}</label><input id="s-name" placeholder="E.g. Daily Digest" class="mc-field">'
            f'<label class="mc-label">Source (file path in the realm, or https URL) {_STAR}</label>'
            f'<input id="s-src" placeholder="E.g. shared/digest.html  ·  or  ·  https://digest.stamih.com" class="mc-field">'
            f'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" onclick="mcAddSection()">Add</button>'
            f'<a href="/" class="btn btn-secondary" style="text-decoration:none">Cancel</a>'
            f'<span id="s-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div>'
            + _ADDSECTION_JS)
    return _page_shell(realm, "", "Add section", body, dark)


def render_edit_section(realm, idx: int, dark=False) -> str:
    sections = getattr(realm, "sections", None) or []
    if idx < 0 or idx >= len(sections):
        return _page_shell(realm, "", "Edit section", '<div style="padding:24px">No such section.</div>', dark)
    s = sections[idx]
    name = s.get("name", "") if isinstance(s, dict) else str(s)
    src = (s.get("path") or s.get("url") or "") if isinstance(s, dict) else ""
    body = (f'<div style="padding:18px 24px 24px;max-width:680px">{_page_title("Edit section")}'
            f'<label class="mc-label">Name {_STAR}</label><input id="s-name" value="{E(name)}" class="mc-field">'
            f'<label class="mc-label">Source (file path in the realm, or https URL) {_STAR}</label>'
            f'<input id="s-src" value="{E(src)}" class="mc-field">'
            f'<div style="margin-top:16px;display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-primary" onclick="mcUpdSection({idx})">Save</button>'
            f'<a href="/section/{idx}" class="btn btn-secondary" style="text-decoration:none">Cancel</a>'
            f'<button class="btn btn-secondary is-danger" style="margin-left:auto" onclick="mcDelSection({idx})">{_icon("trash",13)}Delete section</button>'
            f'<span id="s-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div>'
            # in-app delete confirmation modal
            f'<div id="sec-del-modal" class="mc-modal-ov" onclick="if(event.target===this)mcSecDelClose()">'
            f'<div class="mc-modal-box" style="width:min(420px,92vw)">'
            f'<div class="mc-h-card" style="margin-bottom:6px">Delete “{E(name)}”?</div>'
            f'<div style="font-size:12.5px;color:var(--text-dim);margin-bottom:12px">This removes the section from your top menu. This cannot be undone.</div>'
            f'<div style="display:flex;gap:8px;align-items:center">'
            f'<button class="btn btn-secondary btn-sm" onclick="mcSecDelClose()">Cancel</button>'
            f'<button class="btn btn-danger btn-sm" onclick="mcSecDelGo({idx})">Delete</button>'
            f'<span id="sec-del-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div></div>'
            + _EDITSECTION_JS)
    return _page_shell(realm, name, "Edit section", body, dark, sec_edit=True)


def render_section(realm, idx: int, dark=False) -> str:
    sections = getattr(realm, "sections", None) or []
    if idx < 0 or idx >= len(sections):
        return _page_shell(realm, "", "Section", '<div style="padding:24px">No such section.</div>', dark)
    s = sections[idx]
    name = s.get("name") if isinstance(s, dict) else str(s)
    widget = s.get("widget") if isinstance(s, dict) else ""
    if widget:                                   # a dashboard widget promoted to its own page
        return _render_widget_section(realm, Path(realm.root), name, widget, dark)
    url = s.get("url") if isinstance(s, dict) else ""
    snapshot = s.get("snapshot") if isinstance(s, dict) else ""
    assets = s.get("assets") if isinstance(s, dict) else ""
    # From the content origin, sandboxed (5.8a): a section is someone's HTML and JavaScript — a
    # mini-site, a mirrored page, a live site — and must not share the app's origin or steer its window.
    from .. import origins as _origins
    iframe = (f'<iframe src="{E(_origins.content_url(f"/section-raw/{idx}"))}" title="{E(name)}" '
              f'sandbox="{_origins.FRAME_SANDBOX}" '
              f'style="width:100%;height:100%;border:0;background:#fff"></iframe>')
    if assets and (s.get("entry") if isinstance(s, dict) else ""):
        # 'app section' — renders its own header/controls; ARMADA adds only a slim strip with a live link
        openbtn = (f'<a href="{E(url)}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;font-size:12px;'
                   f'color:var(--color-accent)">Open published ↗</a>') if url else ""
        bar = (f'<div style="display:flex;align-items:center;gap:12px;padding:5px 14px;border-bottom:1px solid var(--color-divider);'
               f'background:var(--color-surface);font-size:11.5px;color:var(--text-muted)">'
               f'<span>Local · {E(name)}</span><span style="margin-left:auto">{openbtn}</span></div>') if url else ""
        body = f'<div style="height:100%;display:flex;flex-direction:column;min-height:0">{bar}<div style="flex:1;min-height:0">{iframe}</div></div>'
        body_cls = "armada-dark" if dark else ""
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(name)}</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, name)}<div style="flex:1;min-height:0">{body}</div></div></body></html>"""
    if snapshot:
        # mirrored section: render the local copy (no firewall/iframe issues); refresh from source; link the live URL
        snap_f = Path(realm.root) / snapshot
        when = _fmt_ts(datetime.datetime.fromtimestamp(snap_f.stat().st_mtime).isoformat()) if snap_f.exists() else "not yet"
        openbtn = (f'<a href="{E(url)}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;font-size:12px;'
                   f'color:var(--color-accent);display:inline-flex;align-items:center;gap:4px">Open published ↗</a>') if url else ""
        bar = (f'<div style="display:flex;align-items:center;gap:12px;padding:7px 14px;border-bottom:1px solid var(--color-divider);'
               f'background:var(--color-surface);font-size:12px">'
               f'<span style="color:var(--text-muted)">Local copy · updated {E(when)}</span>'
               f'<button onclick="mcSnap({idx},this)" class="btn btn-secondary btn-sm">{_icon("refresh-cw",12)}Refresh</button>'
               f'<span style="margin-left:auto">{openbtn}</span></div>')
        body = (f'<div style="height:100%;display:flex;flex-direction:column;min-height:0">{bar}'
                f'<div style="flex:1;min-height:0">{iframe}</div></div>'
                + _SNAP_JS)
        body_cls = "armada-dark" if dark else ""
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(name)}</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, name)}<div style="flex:1;min-height:0">{body}</div></div></body></html>"""
    if url:
        # External sites can't always be embedded (host firewalls / X-Frame-Options / a JS
        # "verifying your browser" challenge that never completes inside a cross-origin frame),
        # so always offer a first-party open — that path works even when the inline preview is blocked.
        host = E(url.split("//", 1)[-1].split("/", 1)[0])
        bar = (f'<div style="display:flex;align-items:center;gap:10px;padding:7px 14px;border-bottom:1px solid var(--color-divider);'
               f'background:var(--color-surface);font-size:12px">'
               f'<span style="color:var(--text-muted)">Live site · {host}</span>'
               f'<a href="{E(url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary" '
               f'style="margin-left:auto;color:#fff;text-decoration:none;font-size:12px;padding:4px 12px;display:inline-flex;align-items:center;gap:5px">'
               f'Open in browser ↗</a></div>'
               f'<div style="padding:0;flex:1;min-height:0;position:relative">{iframe}'
               f'<div style="position:absolute;left:0;right:0;bottom:0;padding:5px 14px;font-size:11px;text-align:center;'
               f'color:var(--text-soft);pointer-events:none">'
               f'If this stays on “verifying…”, use <b>Open in browser</b> above — some sites block embedding.</div></div>')
        body = f'<div style="height:100%;display:flex;flex-direction:column;min-height:0">{bar}</div>'
    else:
        body = iframe
    body_cls = "armada-dark" if dark else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(name)}</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, name)}<div style="flex:1;min-height:0">{body}</div></div></body></html>"""


def render_approvals(realm, realm_root, dark=False) -> str:
    realm_root = Path(realm_root)
    adir = realm_root / "approvals"
    items = []
    if adir.is_dir():
        for f in sorted(adir.glob("*.json")):
            try:
                items.append(json.loads(f.read_text(encoding="utf-8-sig")))
            except json.JSONDecodeError:
                pass
    if items:
        rows = "".join(f'<div class="mc-frame" style="padding:10px 12px;border-radius:var(--r);margin-bottom:8px">'
                       f'<div style="font-size:12.5px">{E(str(it.get("text","")))}</div>'
                       f'<div style="font-size:11px;color:var(--text-muted);margin-top:2px">'
                       f'{E(str(it.get("agent","")))} · {E(str(it.get("kind","")))}</div></div>' for it in items)
    else:
        rows = ('<div style="font-size:12.5px;color:var(--text-muted)">'
                'No approvals waiting. When an agent proposes an irreversible or outbound action '
                '(a send, a purchase, a trade) it will queue here for your approve/deny.</div>')
    return _page_shell(realm, "", "Approvals", f'<div style="padding:18px 24px 24px;max-width:720px">{_page_title("Approvals inbox")}{rows}</div>', dark)


# The user docs (launch plan 3.1/3.3) are Markdown in armada/docs/user/, rendered here with the same
# safe _md() the rest of the app uses; index.md's table is the table of contents. They live INSIDE
# the package since v0.99.72: the installer and the updater ship armada/ only, so at the repo root
# (docs/user) Help was empty on every installed copy. Alexander reads the same pages.
_DOCS_USER = Path(__file__).resolve().parents[1] / "docs" / "user"
_DOC_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _doc_toc() -> list:
    """[(slug, title, blurb)] from the index page's table, in its order."""
    try:
        text = (_DOCS_USER / "index.md").read_text(encoding="utf-8")
    except OSError:
        log.debug("_doc_toc: no docs/user/index.md", exc_info=True)
        return []
    return [(m.group(2), m.group(1), m.group(3).strip())
            for m in re.finditer(r"^\|\s*\[([^\]]+)\]\(([a-z0-9-]+)\.md\)\s*\|\s*(.*?)\s*\|\s*$", text, re.M)]


def _doc_html(md_text: str) -> str:
    """_md() plus what in-app docs need: page links stay in the app (and in this window), and
    headings get ids so `page#section` links land."""
    md_text = re.sub(r"\]\(([a-z0-9-]+)\.md(#[\w-]+)?\)", r"](/docs/\1\2)", md_text)
    out = _md(md_text)
    out = re.sub(r'<a href="(/docs/[^"]*)" target="_blank" rel="noopener noreferrer">', r'<a href="\1">', out)

    def _hid(m):
        text = re.sub(r"<[^>]+>", "", m.group(2))
        slug = re.sub(r"[^a-z0-9]+", "-", html.unescape(text).lower()).strip("-")
        return f'<h{m.group(1)} id="{slug}">{m.group(2)}</h{m.group(1)}>'
    return re.sub(r"<h([1-4])>(.*?)</h\1>", _hid, out)


def render_docs(realm, realm_root, dark=False, slug: str = "") -> str:
    """Help: the index (searchable across every page's text) or one page of docs/user/."""
    toc = _doc_toc()
    if not toc:
        body = ('<div style="padding:18px 24px 24px;max-width:820px">'
                f'{_page_title("Documentation", "help")}<div style="font-size:13px;color:var(--text-muted)">'
                'The help pages aren\u2019t installed with this copy of ARMADA.</div></div>')
        return _page_shell(realm, "", "Documentation", body, dark)
    nav = "".join(
        f'<a href="/docs/{s}" style="display:block;padding:5px 10px;border-radius:var(--r);font-size:13px;'
        f'text-decoration:none;color:{"var(--color-text);font-weight:600;background:var(--text-8)" if s == slug else "var(--text-dim)"}">'
        f'{E(t)}</a>' for s, t, _b in toc)
    nav = (f'<nav style="flex:none;width:200px;position:sticky;top:0;align-self:flex-start">'
           f'<a href="/docs" style="display:block;padding:5px 10px;font-size:13px;text-decoration:none;'
           f'color:{"var(--color-text);font-weight:600" if not slug else "var(--text-dim)"}">Help home</a>{nav}</nav>')
    if slug:
        if not _DOC_SLUG.match(slug) or not (_DOCS_USER / f"{slug}.md").is_file():
            main = '<div style="font-size:13px;color:var(--text-muted)">No such help page.</div>'
            title = "Documentation"
        else:
            main = f'<div class="mc-md" style="font-size:14px;line-height:1.6;max-width:760px">{_doc_html((_DOCS_USER / f"{slug}.md").read_text(encoding="utf-8"))}</div>'
            title = next((t for s, t, _b in toc if s == slug), "Documentation")
        body = (f'<div style="padding:18px 24px 24px;display:flex;gap:28px">{nav}'
                f'<div style="min-width:0;flex:1">{main}</div></div>')
        return _page_shell(realm, "", title, body, dark)
    # The index: a card per page, each carrying its page's text (hidden) so search finds words
    # inside pages, not just in titles.
    cards = ""
    for s, t, b in toc:
        try:
            full = (_DOCS_USER / f"{s}.md").read_text(encoding="utf-8")
        except OSError:
            log.debug("render_docs: missing %s.md", s, exc_info=True)
            full = ""
        cards += (f'<a class="mc-docitem" href="/docs/{s}" style="display:block;text-decoration:none;color:inherit;'
                  f'padding:12px 14px;border-radius:var(--r);margin-bottom:8px;background:var(--color-sand-100);'
                  f'border:1px solid var(--color-divider)">'
                  f'<div style="display:flex;align-items:center;gap:8px">'
                  f'<span style="display:flex;flex:none;color:var(--color-accent)">{_icon("documentation",16)}</span>'
                  f'<span style="font-size:13.5px;font-weight:600">{E(t)}</span></div>'
                  f'<div style="font-size:12px;color:var(--text-muted);margin-top:4px">{_md_inline(E(b))}</div>'
                  f'<span style="display:none">{E(full)}</span></a>')
    search = (
        '<div style="max-width:520px;margin:0 0 16px"><div style="position:relative">'
        f'<span style="position:absolute;left:10px;top:50%;transform:translateY(-50%);display:flex;color:var(--text-muted);pointer-events:none">{_icon("search", 14)}</span>'
        '<input id="doc-search" oninput="mcDocSearch()" placeholder="Search help…" '
        'style="width:100%;box-sizing:border-box;padding:7px 30px 7px 32px;border:1px solid var(--color-divider);'
        'border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;font-size:13px">'
        f'<span id="doc-search-x" onclick="mcDocSearchClear()" title="Clear" style="display:none;position:absolute;'
        f'right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--text-muted);padding:2px">{_icon("x", 13)}</span></div></div>')
    empty = ('<div id="mc-docempty" style="display:none;font-size:12.5px;color:var(--text-muted);padding:8px 2px">'
             'Nothing in the help matches that.</div>')
    try:
        intro_md = (_DOCS_USER / "index.md").read_text(encoding="utf-8").split("| Page |")[0]
        intro = f'<div class="mc-md" style="font-size:13.5px;line-height:1.6;max-width:760px;margin:0 0 14px">{_doc_html(re.sub(r"^# .*$", "", intro_md, count=1, flags=re.M))}</div>'
    except OSError:
        log.debug("render_docs: no intro", exc_info=True)
        intro = ""
    body = (f'<div style="padding:18px 24px 24px;max-width:820px">{_page_title("Documentation", "help")}'
            f'{intro}{search}{cards}{empty}</div>{_DOCSEARCH_JS}')
    return _page_shell(realm, "", "Documentation", body, dark)


def _realm_inbox(realm, realm_root) -> str:
    return (f'<div style="padding:18px 24px 24px">'
            f'{_page_title("Inbox", "tasks your agents have handed each other")}'
            f'{inbox_view(realm, realm_root)}</div>')


def inbox_view(realm, realm_root, agent_id: str = None) -> str:
    """Tasks agents have handed each other. Waiting and recently-handled are what you care about;
    everything older is folded into an archive.

    Shared by the realm-wide Inbox page and an agent's own Inbox tab — `agent_id` narrows it to
    messages that agent sent or received, so the per-agent view is the same thing scoped, not a
    second implementation that can drift.
    """
    from .. import inbox as _inbox
    data = _inbox.all_messages(realm_root, recent_hours=24)
    if agent_id:
        def mine(m):
            return m.get("agent") == agent_id or m.get("from") == agent_id
        data = {k: [m for m in v if mine(m)] for k, v in data.items()}
    names = {a.id: a.display for a in realm.agents}

    def who(aid):
        return E(names.get(aid, aid))

    def when(m):
        ts = m.get("finished") or m.get("started") or m.get("created") or ""
        return _fmt_ts(ts) if ts else ""

    def card(m, archived=False, depth=0):
        state = m.get("state", "")
        pending = state in (_inbox.PENDING, _inbox.RUNNING)
        running = state == _inbox.RUNNING
        reply = bool(m.get("reply"))
        ok = m.get("ok")
        if pending:
            tag, col = ("Running" if running else "Pending"), "var(--status-warn)"
        elif reply:
            tag, col = "Reply", "var(--text-muted)"
        elif ok is False:
            tag, col = "Failed", "var(--status-bad)"
        else:
            tag, col = "Done", "var(--status-ok)"
        detail = str(m.get("detail") or "")
        ctx = str(m.get("context") or "")
        ask = str(m.get("ask", ""))
        aid, mid = E(m.get("agent", "")), E(m.get("id", ""))
        # A message that's been dealt with recedes: everything greys except its status pill, which
        # keeps its colour so you can still pick a failure out of a column of finished work.
        read = not pending
        body_col = "var(--text-muted)" if read else "var(--color-text)"
        # Title is the first line (or a trimmed first sentence) — full text lives in the expansion,
        # because a delegated task can carry long instructions nobody wants unrolled by default.
        stripped = ask.strip()
        first = stripped.splitlines()[0] if stripped else "(no instruction)"
        truncated = len(first) > 110
        title = first if not truncated else first[:107] + "…"
        # Expandable whenever there's anything the summary line doesn't already show — including a
        # single long line, which the title elides. Previously a one-line ask counted as "nothing
        # more to see", so the full text was unreachable: the ellipsis led nowhere.
        has_more = truncated or len(stripped) > len(first) or bool(ctx) or bool(detail)
        acts = ""
        if pending and not reply:
            acts += (f'<a class="mc-cap-ico" title="Process now — don\'t wait for the next run" '
                     f'data-act="process" data-agent="{aid}" data-id="{mid}">{_icon("zap",15)}</a>')
        # Re-running a reply makes no sense — it's a note, not a task.
        if not reply and not pending:
            acts += (f'<a class="mc-cap-ico" title="Mark unread — run it again next pass" '
                     f'data-act="unread" data-agent="{aid}" data-id="{mid}">{_icon("mark-unread",16)}</a>')
        acts += (f'<a class="mc-cap-ico" title="Delete this task" '
                 f'data-act="delete" data-agent="{aid}" data-id="{mid}" '
                 f'style="color:var(--text-muted)">{_icon("trash",15)}</a>')
        # Filtering is client-side off these attributes, so it stays instant and needs no round-trip.
        status_key = ("waiting" if pending else
                      "reply" if reply else "failed" if ok is False else "done")
        hay = " ".join(str(x) for x in (ask, ctx, detail, names.get(m.get("from", ""), ""),
                                        names.get(m.get("agent", ""), ""))).lower()
        # Level with the sender → recipient line, which is the card's first row.
        expand = (f'<span class="mc-cap-caret" style="display:inline-flex;flex:none;'
                  f'color:var(--text-muted);margin-top:1px">{_icon("chevron-right",13)}</span>'
                  if has_more else '<span style="width:13px;flex:none"></span>')
        body = ""
        if has_more:
            # Always the full instruction, verbatim — this is exactly what the agent was asked to
            # do, and an expansion that still truncates is worse than no expansion at all.
            body = (f'<div class="mc-inbox-body" style="margin-top:7px;padding-top:8px;'
                    f'border-top:1px solid var(--color-divider)">'
                    + (f'<div style="font-size:12.5px;line-height:1.5;white-space:pre-wrap;'
                       f'color:{body_col}">{E(stripped)}</div>' if stripped else "")
                    + (f'<div style="font-size:11.5px;color:var(--text-muted);margin-top:6px;'
                       f'line-height:1.45;white-space:pre-wrap"><b>Context:</b> {E(ctx)}</div>' if ctx else "")
                    + (f'<div style="font-size:11.5px;margin-top:6px;line-height:1.45;'
                       f'white-space:pre-wrap;'
                       f'color:{"var(--status-bad)" if ok is False else "var(--text-muted)"}">'
                       f'<b>Outcome:</b> {E(detail)}</div>' if detail else "")
                    + '</div>')
        return (
            f'<details class="mc-frame mc-inbox-msg" data-agent="{aid}" data-id="{mid}" '
            f'data-from="{E(m.get("from",""))}" data-to="{E(m.get("agent",""))}" '
            f'data-status="{status_key}" data-search="{E(hay)}" '
            # A reply is indented under the message it answers, with a lighter left rule, so it
            # reads as an answer rather than a separate item competing for attention.
            f'style="border-radius:var(--r);padding:10px 8px;margin-bottom:8px;'
            f'{f"margin-left:26px;" if depth else ""}'
            f'border-left:3px solid {col}{";opacity:.8" if archived else ""}">'
            f'<summary style="list-style:none;cursor:{"pointer" if has_more else "default"};'
            f'display:grid;grid-template-columns:13px 1fr auto;gap:7px;align-items:start">'
            f'{expand}'
            f'<div style="min-width:0">'
            f'<div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:11.5px;'
            f'color:var(--text-muted)">'
            f'<span style="font-weight:600;color:{body_col}">{who(m.get("from",""))}</span>'
            f'<span>→</span>'
            f'<span style="font-weight:600;color:{body_col}">{who(m.get("agent",""))}</span>'
            f'{_pill(tag, _tone(col))}<span>{E(when(m))}</span></div>'
            f'<div style="font-size:12.5px;line-height:1.45;margin-top:3px;color:{body_col}">'
            f'{E(title)}</div></div>'
            f'<div style="display:flex;align-items:center;gap:8px;white-space:nowrap">{acts}</div>'
            f'</summary>{body}</details>')

    def section(title, note, items, archived=False):
        body = ("".join(card(m, archived, d) for m, d in _inbox.threaded(items)) if items else
                '<div class="mc-inbox-empty" style="font-size:12.5px;color:var(--text-muted)">'
                'Nothing here.</div>')
        return (f'<div class="mc-inbox-sec" style="margin-bottom:22px">{_sec_head(title, note)}'
                f'<div class="mc-inbox-list">{body}</div>'
                f'<div class="mc-inbox-none" style="display:none;font-size:12.5px;'
                f'color:var(--text-muted)">Nothing matches these filters.</div></div>')

    # --- filters -----------------------------------------------------------------------------
    involved = sorted({m.get("from", "") for v in data.values() for m in v} |
                      {m.get("agent", "") for v in data.values() for m in v})
    involved = [x for x in involved if x]

    # The app's own dropdowns (UI audit FI2), like every other list's filter bar — the Inbox was
    # the last page on the browser's native <select>.
    def opts(label, pool=None):
        return [("", label, "")] + [(x, names.get(x, x), "")
                                    for x in (pool if pool is not None else involved)]
    # On an agent's own tab every message already concerns that agent, so a "to" filter would be a
    # control that does nothing — the sender is the only axis worth narrowing.
    from_pool = [x for x in involved if x != agent_id] if agent_id else involved
    to_filter = ("" if agent_id else
                 f'<span style="color:var(--text-muted);font-size:12px">→</span>'
                 + _filter_dropdown("ib-to", "Anyone", opts("Anyone"), width="150px", onpick="mcInboxFilter"))
    from_label = "From anyone" if agent_id else "Anyone"
    filters = (
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 16px">'
        + _filter_dropdown("ib-from", from_label, opts(from_label, from_pool), width="150px", onpick="mcInboxFilter")
        + to_filter
        + _filter_dropdown("ib-status", "Any status",
                           [("", "Any status", ""), ("waiting", "Pending", ""), ("done", "Done", ""),
                            ("failed", "Failed", ""), ("reply", "Replies", "")],
                           width="130px", onpick="mcInboxFilter")
        + '<button type="button" class="btn-link" onclick="mcInboxClear()">Clear</button></div>'
        + _FDROP_JS)

    enabled = _inbox.enabled(realm_root)
    off_note = ("" if enabled else
                '<div style="font-size:12.5px;padding:9px 13px;margin-bottom:16px;border-radius:var(--r);'
                'background:color-mix(in srgb,var(--status-warn) 12%,var(--color-bg));'
                'border:1px solid color-mix(in srgb,var(--status-warn) 35%,transparent)">'
                'Agent-to-agent tasks are switched off for this realm — nothing here will be acted '
                'on. Turn them back on in Settings → Realm.</div>')
    # The archive is always present, even when empty — a section that only appears once it has
    # content reads as a missing feature rather than an empty one.
    arch = data["archive"]
    arch_body = ("".join(card(m, True, d) for m, d in _inbox.threaded(arch)) if arch else
                 '<div style="font-size:12.5px;color:var(--text-muted)">'
                 'Nothing archived yet. Exchanges older than 24 hours move here.</div>')
    arch_search = (
        f'<div style="position:relative;max-width:320px;margin:10px 0 12px">'
        f'<span style="position:absolute;left:10px;top:50%;transform:translateY(-50%);display:flex;'
        f'color:var(--text-muted);pointer-events:none">{_icon("search",14)}</span>'
        f'<input id="ib-arch-q" oninput="mcInboxFilter()" placeholder="Search the archive…" '
        f'style="width:100%;box-sizing:border-box;padding:7px 10px 7px 32px;border:1px solid '
        f'var(--color-divider);border-radius:var(--r);background:var(--color-bg);'
        f'color:var(--color-text);font:inherit;font-size:13px"></div>') if arch else ""
    archive_block = (
        f'<details id="ib-archive" style="margin-top:6px">'
        f'<summary style="cursor:pointer;font-family:var(--font-heading);font-weight:600;'
        f'font-size:14px">Task archive '
        f'<span style="font-weight:400;font-size:12px;color:var(--text-muted)">'
        f'· {len(arch)} older task{"" if len(arch) == 1 else "s"}</span></summary>'
        f'{arch_search}'
        f'<div class="mc-inbox-sec"><div class="mc-inbox-list">{arch_body}</div>'
        f'<div class="mc-inbox-none" style="display:none;font-size:12.5px;color:var(--text-muted)">'
        f'Nothing in the archive matches.</div></div></details>')
    n_new = len(data["waiting"])
    new_title = f"New tasks ({n_new})" if n_new else "New tasks"
    return (f'{off_note}<div style="max-width:900px">{filters}'
            f'{section(new_title, "waiting to be picked up on the next inbox run", data["waiting"])}'
            f'{section("Processed in the last 24h", "", data["recent"])}'
            f'{archive_block}</div>{_INBOX_JS}')


def _sec_head(title, note="") -> str:
    return (f'<div style="display:flex;align-items:baseline;gap:9px;margin:0 0 9px">'
            f'<span class="mc-h-sect">{E(title)}</span>'
            + (f'<span style="font-size:12px;color:var(--text-muted)">{E(note)}</span>' if note else "")
            + '</div>')


# Script body lives in webui/static/js/inbox.js (Phase 2, 2.1).
_INBOX_JS = _INBOX_JS_ASSET


def render_realm_page(realm, realm_root, page: str, dark: bool = False) -> str:
    realm_root = Path(realm_root)
    today = clock.today()
    if page == "ministers":
        return _page_shell(realm, realm.theme_agent + "s", realm.theme_agent + "s", _realm_ministers(realm, realm_root, today), dark)
    if page == "jobs":
        return _page_shell(realm, "Jobs", "Jobs", _realm_jobs(realm, realm_root, today), dark)
    if page == "goals":
        return _page_shell(realm, "Goals", "Goals", _realm_goals(realm, realm_root), dark)
    if page == "memory":
        return _page_shell(realm, "Memory", "Memory", _realm_memory(realm, realm_root), dark)
    if page == "skills":
        return _page_shell(realm, "Capabilities", "Capabilities", _realm_skills(realm, realm_root), dark)
    if page == "artefacts":
        return _page_shell(realm, "Artefacts", "Artefacts", _realm_artefacts(realm, realm_root), dark)
    if page == "inbox":
        return _page_shell(realm, "Inbox", "Inbox", _realm_inbox(realm, realm_root), dark)
    return _page_shell(realm, "Overview", page, f'<div style="padding:24px">Unknown page: {E(page)}</div>', dark)


def _addon_widgets(realm_root) -> list:
    try:
        from .. import addons
        return addons.load(realm_root).get("widgets")
    except Exception:  # noqa — an add-on problem must never cost the Overview
        swallowed(log, '_addon_widgets: failed; none shown')
        return []


def _addon_widget(w: dict) -> str:
    """One add-on widget: a markdown body or a list of links, in the dashboard's widget chrome."""
    if w.get("kind") == "links":
        inner = "".join(
            f'<li><a href="{E(ln["url"])}"{"" if ln["url"].startswith("/") else " target=_blank rel=noopener"}>'
            f'{E(ln["label"])}</a></li>' for ln in w.get("links") or [])
        inner = f'<ul class="mc-addon-links">{inner}</ul>'
    else:
        # A checklist is the most-asked-for widget; "- [ ]" reads as a box, not as brackets.
        body = re.sub(r"(?m)^(\s*[-*] )\[[xX]\] ", "\\1\u2611 ", w.get("body") or "")
        body = re.sub(r"(?m)^(\s*[-*] )\[ \] ", "\\1\u2610 ", body)
        inner = f'<div class="mc-md mc-addon-md">{_md(body)}</div>'
    return (f'<div class="mc-widget" style="height:100%;display:flex;flex-direction:column;overflow:hidden">'
            f'{_wid_header(w["title"], "add-on", widget_id="addon:" + w["qid"])}'
            f'<div class="mc-scroll" style="flex:1;min-height:0;overflow:auto;padding:10px 14px">{inner}</div></div>')


def render_dashboard(realm, realm_root, dark: bool = False) -> str:
    realm_root = Path(realm_root)
    today = clock.today()
    body_cls = "armada-dark" if dark else ""
    addicon = _icon("plus", 14, "vertical-align:-2px")
    widgets = [("register", 10, _register(realm, realm_root, today)),
               ("usage", 10, _usage(realm, realm_root, today)),
               ("jobcal", 10, _jobcal(realm, realm_root, today))]
    # Add-on widgets (the add-on surface's first consumer, ADR-012): data an add-on declared, drawn
    # here by the app's own code. Hidden and shown like the built-in ones.
    addon_w = []
    for w in _addon_widgets(realm_root):
        widgets.append((f"addon:{w['qid']}", w.get("default_span") or 6, _addon_widget(w)))
        addon_w.append({"id": f"addon:{w['qid']}", "label": w["title"],
                        "desc": f"From the add-on {w['addon']}."})
    cells = "".join(
        f'<div class="mc-w" data-id="{wid}" data-span="{span}" style="grid-column:span {span};grid-row:span 19;min-height:0;position:relative">{html}</div>'
        for wid, span, html in widgets)
    grid = (f'<div id="mc-grid" class="mc-appscroll" data-realm="{E(realm.name)}" style="flex:1;min-height:0;display:grid;'
            f'grid-template-columns:repeat(20,1fr);grid-auto-rows:10px;gap:14px;overflow:auto;'
            # Bottom padding belongs to the scroller, not to the block around it. On the block it
            # was a solid band that cut the last line of content in half wherever you stopped; here
            # it is scrollable room, so the fade below can never be the reason you cannot read
            # something — scroll to the end and the last row clears it.
            f'padding-top:14px;padding-bottom:22px">{cells}</div>')
    # dot=True: the thread widget's header used to carry a separate status dot beside the title.
    # It's on the avatar now, like everywhere else.
    agents_json = json.dumps([{"id": a.id, "display": a.display, "icon": _portrait(realm_root, a, 22, dot=True)}
                              for a in (([realm.coordinator] if realm.coordinator else []) + list(realm.members))])
    grip_json = json.dumps(GRIP)
    dash_json = json.dumps(_load_dashboard(realm_root))
    modal = (
        '<div id="mc-wmodal" style="display:none;position:fixed;inset:0;z-index:60;background:rgba(0,0,0,.32);'
        'align-items:center;justify-content:center" onclick="if(event.target===this)mcWModalClose()">'
        '<div style="background:var(--color-bg);border:1px solid var(--color-divider);border-radius:14px;'
        'box-shadow:var(--shadow-md);width:540px;max-width:94vw;max-height:82vh;display:flex;flex-direction:column">'
        '<div style="display:flex;align-items:center;padding:16px 20px 12px;border-bottom:1px solid var(--color-divider)">'
        '<span style="font-family:var(--font-heading);font-weight:600;font-size:17px">Select the widgets to be shown on the dashboard</span>'
        '<button type="button" class="mc-x" onclick="mcWModalClose()" title="Close" aria-label="Close">'
        '×</button></div>'
        '<div id="mc-wmodal-body" style="overflow:auto;padding:14px 20px 20px"></div>'
        '</div></div>')
    ren_modal = (
        '<div id="mc-twren-modal" class="mc-modal-ov" style="z-index:250" onclick="if(event.target===this)mcTWRenClose()">'
        '<div class="mc-modal-box" style="width:min(440px,92vw)">'
        '<div class="mc-h-card">Rename thread</div>'
        '<input type="hidden" id="twren-id"><input type="hidden" id="twren-agent"><input type="hidden" id="twren-thread">'
        '<input id="twren-title" style="display:block;width:100%;padding:7px 9px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;font-size:14px">'
        '<div style="margin-top:12px;display:flex;gap:8px;align-items:center;justify-content:flex-end">'
        '<span id="twren-msg" style="margin-right:auto;font-size:12px;color:var(--text-muted)"></span>'
        '<button class="btn btn-secondary" onclick="mcTWRenClose()">Cancel</button>'
        '<button class="btn btn-primary" onclick="mcTWRenSave()">Save</button>'
        '</div></div></div>')
    del_modal = (
        '<div id="mc-twdel-modal" class="mc-modal-ov" style="z-index:250" onclick="if(event.target===this)mcTWDelClose()">'
        '<div class="mc-modal-box" style="width:min(420px,92vw)">'
        '<input type="hidden" id="twdel-id">'
        '<div class="mc-h-card" style="margin-bottom:6px">Remove widget?</div>'
        '<div style="font-size:12.5px;color:var(--text-dim);margin-bottom:14px">'
        'Remove <b id="twdel-name"></b> from your dashboard. The thread and its messages are kept — you can re-add it anytime.</div>'
        '<div style="display:flex;gap:8px;justify-content:flex-end">'
        '<button class="btn btn-secondary" onclick="mcTWDelClose()">Cancel</button>'
        '<button class="btn btn-danger" onclick="mcTWDelConfirm()">Remove</button>'
        '</div></div></div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(realm.name)}</title>
{_CSS_LINKS}{_theme_style()}
</head><body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}
{_nav(realm, "Overview")}
<!-- No bottom padding: a solid band below the scroller cut the last row of content off mid-glyph,
     which reads as a rendering fault rather than as "there is more down there". The grid now runs
     to the window edge and the strip at the end of this block fades it out instead. -->
<div style="flex:1;min-height:0;padding:16px 0 0 24px;display:flex;flex-direction:column;gap:0;position:relative">
 <!-- The header's shadow is its edge, so the box has to reach both window edges or the shadow
      stops short on one side. The parent indents by 24px on the left, so this pulls back out and
      re-pays the same 24px as padding: content unmoved, shadow symmetric. -->
 <!-- Fixed height. Everything in this bar except the title arrives after the page does — the KPI
      values come from a usage fetch, the limit bars from another — so the bar grew as each landed
      and shoved the grid down under it, twice, a second or two apart. Pinning it means the late
      content fills a space that was already the right size. -->
 <div id="mc-ovh" style="display:flex;align-items:flex-start;gap:24px;padding:0 24px 14px;margin-left:-24px;height:76px;box-sizing:border-box;position:relative;z-index:2;transition:box-shadow .18s ease">
  <div style="display:flex;flex-direction:column;line-height:1.05">
   <h2 style="font-family:var(--font-heading);font-size:28px;margin:0">Overview</h2>
   <span style="font-family:var(--font-body);font-weight:400;font-size:11px;letter-spacing:.08em;
    text-transform:uppercase;color:var(--text-soft);margin-top:3px">Dashboard</span></div>
  {_kpis(realm, *_totals_30d(realm, realm_root, clock.today()))}
  <!-- Wide enough for the longest row this can hold: "Current session · 5h … 47% · resets in
       5d 12h". The label column inside is a FIXED width rather than a shrinking one, so the bars
       and everything after them line up between the two rows instead of starting wherever the
       label happened to end. -->
  <!-- flex-start, not center. Both this and a KPI cell are 62px tall, but a KPI stacks its
       caption and value from the top while this was centring its whole block — which put
       "CLAUDE SUBSCRIPTION LIMITS" a few pixels below every other caption on the row. -->
  <div id="mc-hdr-limits" style="display:flex;flex-direction:column;justify-content:flex-start;
   min-width:340px;max-width:430px;height:62px;overflow:hidden"></div>
  <div style="margin-left:auto;display:flex;gap:8px">
   <button id="mc-addwidget" class="btn btn-secondary" onclick="mcAddWidget()">{addicon}&nbsp;Manage widgets</button></div>
 </div>
 {grid}
 <div style="position:absolute;left:0;right:0;bottom:0;height:22px;pointer-events:none;z-index:1;
  background:linear-gradient(to bottom,transparent,var(--color-bg))"></div>
</div></div>{modal}{ren_modal}{del_modal}{_appoint_modal(realm)}
<script>window.MC_AGENTS={agents_json};window.MC_GRIP={grip_json};window.MC_DASH={dash_json};window.MC_ADDON_W={json.dumps(addon_w).replace("</", "<\\/")};</script>{_ICONS_JS}{_DASH_JS}{_LAYOUT_JS}{_JOBCAL_JS}{_USAGE_JS}{_NEW_JS}{_AUTONOMY_JS}{_AGENT_COLOR_JS}{_FORM_JS}{_APPOINT_JS}{_consumption_js(realm, "n-model", "n-effort", "n-consmarker", "#n-cons")}</body></html>"""


def _app_advanced(updater) -> str:
    """Settings → App → Advanced: the automatic-updates switch (5.4, decided in ADR-005)."""
    on = updater.auto_enabled()
    note = ("" if updater.installed() else
            '<div style="font-size:11px;color:var(--text-muted);margin-top:6px">This is a development '
            'copy, so it never updates itself; the switch applies once ARMADA is installed.</div>')
    return ('<details class="mc-frame" id="st-app-advanced" style="border-radius:var(--r);padding:14px 16px;margin-bottom:14px">'
            '<summary style="cursor:pointer;font-family:var(--font-heading);font-weight:600;font-size:15px">Advanced</summary>'
            '<div style="margin-top:12px;display:flex;align-items:flex-start;gap:12px">'
            f'<label class="mc-toggle" title="{"On" if on else "Off"}">'
            f'<input type="checkbox" id="st-update-auto" {"checked" if on else ""} onchange="mcUpdAuto(this)">'
            '<span class="mc-toggle-sl"></span></label>'
            '<div><div style="font-size:12.5px;font-weight:600">Update automatically</div>'
            '<div style="font-size:11.5px;color:var(--text-muted);line-height:1.5;margin-top:2px">'
            'ARMADA checks for a new version twice a day. Each one is checked against ARMADA\'s '
            'release signature before anything is installed, and goes in the next time ARMADA starts '
            '(or straight away when the window is closed and nothing is running). Your realms and '
            'settings are never touched. Off: nothing is checked or downloaded until you use Check '
            'for updates.</div>'
            '<span id="mc-updauto-msg" style="font-size:11.5px;color:var(--text-muted)"></span>'
            f'{note}</div></div></details>')
