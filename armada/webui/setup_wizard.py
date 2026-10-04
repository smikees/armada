"""The setup wizard (launch plan 6.4): ARMADA's first run, with Alexander as the guide.

Replaces the middle of the 5.3 welcome page. Nine steps in two halves (setupflow explains why):

    welcome · checks · folder · naming · team — before a realm exists (welcome mode, "/")
    capabilities · first job · tour · done — inside the new realm ("/setup")

Both halves are drawn by the same shell, so crossing from one to the other (creating the realm and
switching the server into it) looks like the next step rather than a new page. Everything Alexander
says comes from armada/alexander/wizard_script.py; nothing here is generated.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import approot, brand, setupflow, covenant
from ..alexander import AVATAR, NAME as ALEX, ROLE as ALEX_ROLE, wizard_script as ws
from ..assets import CSS_LINKS, CSSV, js
from ..icons import _icon
from ._base import E, _md
from .provider_settings import connections

SETUP_JS = js("setup") + js("setup_team")

_TPL_ORDER = ("state", "company", "crew", "scratch")
_TPL_LABEL = {"state": "State", "company": "Company", "crew": "Ship", "scratch": "Blank"}


def _say(step: str, *keys: str, **vals) -> str:
    """Alexander's lines for a step, as paragraphs; the first is the lede."""
    out = []
    for i, k in enumerate(keys):
        cls = "mc-su-lede" if i == 0 else ""
        text = E(ws.line(step, k, **vals))
        if step == "welcome" and k == "intro":
            text = f"<strong>{text}</strong>"
        out.append(f'<p class="{cls}" data-line="{E(step)}.{E(k)}">{text}</p>')
    return f'<div class="mc-su-say">{"".join(out)}</div>'


def _rail(current: str, done_upto: int) -> str:
    items = []
    for i, (sid, title) in enumerate(ws.STEPS):
        state = "is-done" if i < done_upto else ("is-current" if sid == current else "")
        items.append(f'<li class="mc-su-rstep {state}" data-step="{E(sid)}"><span class="mc-su-rdot">'
                     f'<span class="mc-su-rnum">{i + 1}</span>{_icon("check", 12)}</span>'
                     f'<span class="mc-su-rlabel">{E(title)}</span></li>')
    return f'<ol class="mc-su-rail" aria-label="Setup steps">{"".join(items)}</ol>'


def _pane(step: str, say: str, body: str, foot: str) -> str:
    return (f'<div class="mc-su-pane" data-step="{E(step)}" hidden>{say}'
            f'<div class="mc-su-body">{body}</div><div class="mc-su-foot">{foot}</div></div>')


def _btn(label: str, onclick: str, kind: str = "primary", id_: str = "", extra: str = "") -> str:
    idattr = f' id="{E(id_)}"' if id_ else ""
    return (f'<button type="button" class="btn btn-{kind}"{idattr} onclick="{E(onclick)}"{extra}>'
            f'{label}</button>')


def _icons() -> dict:
    return {"ok": _icon("circle-check-fill", 16), "bad": _icon("circle-x", 16),
            "warn": _icon("warning-tri", 16), "laurel": _icon("laurel", 15), "x": _icon("x", 13),
            "info": _icon("info-circle", 15), "agreement": _icon("agreement", 18), "external": _icon("external-link", 13), "refresh": _icon("refresh-cw", 14),
            "dot": '<i class="mc-su-dot"></i>'}


def _shell(panes: str, first: str, data: dict, dark: bool, done_upto: int) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Welcome to {brand.NAME}</title>
{CSS_LINKS}</head>
<body class="mc-su-page{' is-intro' if first == 'intro' else ''}{' armada-dark' if dark else ''}">
<header class="mc-su-top"><div class="mc-su-brand">{brand.LOGO}</div>
<div class="mc-su-count mc-eyebrow" id="su-count"></div></header>
<main class="mc-su-stage">
<aside class="mc-su-guide">
<div class="mc-su-alex"><img class="mc-su-portrait" src="{AVATAR}{CSSV}" width="84" height="84" alt="Alexander">
<div><div class="mc-su-name">{E(ALEX)}</div><div class="mc-eyebrow">YOUR GUIDE</div></div></div>
{_rail(first, done_upto)}
</aside>
<section class="mc-su-card" id="su-card" aria-live="polite">{panes}</section>
</main>
<script>window.MC_SU={json.dumps({**data, "first": first, "icons": _icons()}, ensure_ascii=False).replace("</", "<\\/")};</script>
{SETUP_JS}</body></html>"""


# --- the first half: before the realm ------------------------------------------------------------

def _known(realms: list, title: str = "Pick up where you left off") -> str:
    if not realms:
        return ""
    rows = "".join(
        f'<li><span><b>{E(r.get("name") or Path(r["path"]).name)}</b>'
        f'<span class="mc-hint"> {E(r["path"])}</span></span>'
        f'<a class="btn btn-secondary btn-sm" href="/switch?path={E(_q(r["path"]))}&amp;to=/">Open</a></li>'
        for r in realms)
    return (f'<div class="mc-su-known"><div class="mc-label">{E(title)}</div>'
            f'<ul class="mc-su-list">{rows}</ul></div>')


def _q(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(str(s), safe="")


def _tpl_cards() -> str:
    from ..templates import TEMPLATES
    from ..starter_profiles import roster
    out = []
    for i, k in enumerate(k for k in _TPL_ORDER if k in TEMPLATES):
        th = TEMPLATES[k]["theme"]
        n = len(roster(k))
        who = (f'{n} {E(th["agent"].lower())}s, led by the {E(th["coordinator"])}' if n
               else "You name every agent")
        out.append(
            f'<div class="mc-su-tpl-wrap"><label class="mc-su-tpl"><input type="radio" name="su-tpl" value="{E(k)}"'
            f'{" checked" if i == 0 else ""}><span class="mc-su-tplicon">{_icon(th.get("icon") or "compass", 22)}</span>'
            f'<span class="mc-su-tpltext"><span class="mc-h-sect">{E(_TPL_LABEL.get(k, k.title()))}</span>'
            f'<span class="mc-hint">{who}</span></span></label>'
            f'<button type="button" class="btn-link mc-su-covenant-link" data-template="{E(k)}" onclick="mcSuCovenant(this.dataset.template)">{_icon("agreement", 12)} {E(covenant.title(k))}</button></div>')
    return "".join(out)


def _presets() -> dict:
    """Read-only starter profiles; owner substitution is escaped by the client after Markdown."""
    from ..templates import TEMPLATES
    from ..starter_profiles import roster
    return {k: {"covenantTitle": covenant.title(k), "covenantHTML": _md(covenant.starter(k).split("\n", 1)[1]), "collective": t["theme"]["collective"], "coordinator": t["theme"]["coordinator"],
                "agent": t["theme"]["agent"],
                "agents": [{**a, "html": {f: _md(a.get(f, "")) for f in ("mandate", "voice", "tenets")}}
                           for a in roster(k)]}
            for k, t in TEMPLATES.items()}


def _opening_panes(note_html: str = "") -> tuple[str, str, str]:
    intro = _pane("intro", "",
        f'<div class="mc-su-intro-logo">{brand.WORDMARK}</div>'
        '<p class="mc-su-tagline">Create, empower and control your army of agents.</p>',
        _btn("Start setup", "mcSuGo('welcome')"))
    welcome = _pane("welcome", _say("welcome", "intro", "what", "how"), "",
        _btn("Back", "mcSuGo('intro')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Continue", "mcSuGo('checks')"))
    checks = _pane(
        "checks", _say("checks", "intro") + '<div class="mc-su-say mc-su-say-more"><p id="su-checkline"></p></div>',
        note_html + connections(setup=True) + '<section class="mc-su-runtime mc-hint"><h3>Included with Armada</h3>'
        '<ul id="su-runtime" role="status"><li>Checking dependencies…</li></ul></section><p class="mc-hint" id="su-check-feedback" role="status"></p>',
        _btn("Back", "mcSuGo('welcome')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn(_icon("refresh-cw", 14) + " Check again", "mcSuCheck(true)", "secondary", "su-recheck")
        + _btn("Continue", "mcSuGo('home')", "primary", "su-checks-next", " disabled"))
    return intro, welcome, checks


def _team_pane() -> str:
    team = _pane(
        "team", '<div class="mc-su-say"><p class="mc-su-lede">Choose or create the profiles for your agents.</p></div>',
        f'''<fieldset id="su-team-builder"><legend class="mc-su-sr-only">Choose your realm and agents</legend>
<div class="mc-su-tpls" role="radiogroup" aria-label="Template">{_tpl_cards()}</div>
<p class="mc-hint" id="su-tplline"></p>
<div class="mc-su-rosters" id="su-rosters"><section><h2>Available profiles</h2><p class="mc-hint">Drag into your team or create a new profile.</p>
<div id="su-roster"></div></section>
<section id="su-team-drop"><div class="mc-su-team-heading"><h2 id="su-teamlabel">Your team (0 members)</h2>
<button type="button" class="btn btn-secondary btn-sm" id="su-addagent" onclick="mcSuAddAgent()">{_icon("plus", 13)} Create new profile</button></div>
<p class="mc-hint" id="su-pickedline" role="status"></p><div id="su-team"></div></section></div></fieldset>
<p class="mc-su-msg" id="su-teammsg" role="status"></p>''',
        _btn("Back", "mcSuGo('naming')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Appoint the team", "mcSuAppoint(this)", "primary", "su-appoint", " disabled"))
    return team


def _naming_pane() -> str:
    return _pane("naming", _say("naming", "intro"),
        '''<div class="mc-su-two"><div><label class="mc-label" for="su-owner">Your name</label>
<input id="su-owner" class="mc-field" maxlength="60" placeholder="What should the team call you?" autocomplete="given-name" required></div>
<div><label class="mc-label" for="su-name">Realm name</label>
<input id="su-name" class="mc-field" maxlength="60" placeholder="e.g. Home, Work or ACME Company" required></div></div>
<p class="mc-su-msg" id="su-namingmsg" role="status"></p>''',
        _btn("Back", "mcSuGo('home')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Continue", "mcSuNaming()", "primary", "su-naming-next"))


def render_welcome_half(realms: list | None = None, note: str = "", dark: bool = False) -> str:
    root = approot.root()
    from .welcome import suggested_root
    note_html = f'<p class="mc-su-note" role="alert">{E(note)}</p>' if note else ""
    intro, welcome, checks = _opening_panes(note_html)
    root_val = root or suggested_root()
    home = _pane(
        "home", _say("home", "intro"),
        f'''<label class="mc-label" for="su-root">{brand.NAME}’s folder</label>
<div class="mc-su-row"><input id="su-root" class="mc-field" value="{E(root_val)}" spellcheck="false">
{_btn("Choose…", "mcSuPick()", "secondary")}</div>
<p class="mc-hint">It’s created if it doesn’t exist.</p>
{_known(realms or [])}
<button type="button" class="btn-link" onclick="mcSuAdopt(this)">I already have a realm folder</button>
<p class="mc-su-msg" id="su-adoptmsg" role="status"></p>
<p class="mc-su-msg" id="su-homemsg" role="status"></p>''',
        _btn("Back", "mcSuGo('checks')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Continue", "mcSuHome(this)", "primary", "su-home-next"))
    team = _team_pane()
    data = {"half": "welcome", "script": setupflow.script(), "presets": _presets(),
            "haveRoot": approot.exists()}
    dialog = '<dialog id="su-profile-dialog" class="mc-su-profile-dialog" aria-labelledby="su-profile-title"><div id="su-profile-content"></div></dialog>'
    return _shell(intro + welcome + checks + home + _naming_pane() + team + dialog, "intro", data, dark, 0)


# --- the second half: inside the realm -----------------------------------------------------------

def _cap_rows(template: str, realm_root=None) -> str:
    """Use User capability cards with separate enabled and inclusion controls."""
    from .. import catalogue, capabilities
    from .capabilities import _cap_card, _cap_legend, _CAP_DESC
    saved = {i.get("catalogue_key"): i for _, i in capabilities.catalogue_flat(realm_root)} if realm_root else {}
    out = ['<details class="mc-su-cap-legend"><summary>Risk levels and ability icons</summary>' + _cap_legend() + '</details>']
    recs = sorted(setupflow.recommended_for(template), key=lambda r: not bool(saved.get(r["key"], {}).get("enabled") if r["key"] in saved else r["on"]))
    for kind in ("skills", "connectors", "extensions"):
        cards = []
        for r in recs:
            entry = setupflow._entry_for(r)
            if entry["kind"] != kind:
                continue
            look = catalogue.inspect(entry)
            it = saved.get(r["key"]) or {"id": r["id"], "name": r["name"], "description": entry["description"],
                "source": "catalogue", "catalogue_key": r["key"], "url": entry["homepage"],
                "made_by": entry["author"], "curated": entry["curated"], "runs": look["runs"],
                "touch": look["touch"], "inspected": look["inspected"], "inspect_note": look["detail"],
                "setup_guide": entry.get("setup_guide"), "setup_required": entry.get("setup_required"),
                "status": "planned", "preview": True}
            it = {**it, "preview": True}
            already = bool(saved.get(r["key"]))
            selected = bool(it.get("enabled")) if already else r["on"]
            toggle = (f'<label class="mc-toggle" onclick="event.stopPropagation()" title="Enable {E(r["name"])}">'
                      f'<input type="checkbox" class="su-cap-enabled" aria-label="Enable {E(r["name"])}"'
                      f'{" checked" if selected else ""}><span class="mc-toggle-sl"></span></label>')
            if kind != "skills":
                toggle = '<span class="mc-hint">Setup required</span>' + toggle
            toggle += (f'<input type="checkbox" class="su-cap" aria-label="Add {E(r["name"])} to realm"'
                       f' aria-describedby="su-cap-selection-help" checked onclick="event.stopPropagation()">')
            cards.append(f'<div class="mc-su-cap-choice" data-key="{E(r["key"])}">'
                         + _cap_card(it, kind=kind, selection=toggle)
                         + '<span class="mc-su-capst mc-hint" role="status"></span></div>')
        if cards:
            out.append(f'<section class="mc-cap-grp"><div class="mc-su-cap-heading"><h3>{kind.title()}</h3></div><p class="mc-hint mc-su-cap-subtitle">{E(_CAP_DESC[kind])}</p><div class="mc-su-cap-columns mc-hint"><span>Enable</span><span>Add</span></div>' + ''.join(cards) + '</section>')
    return ''.join(out)


def _saved_start(realm, realm_root, owner: str) -> str:
    """Earlier steps remain reachable after creation without resubmitting a new realm."""
    from ..realm_registry import load as _reg_load
    intro, welcome, checks = _opening_panes()
    others = [r for r in _reg_load() if r.get('path') and Path(r['path']).resolve() != Path(realm_root).resolve()]
    home = _pane("home", _say("home", "intro"),
        f'<label class="mc-label" for="su-root">Realm folder</label>'
        f'<div class="mc-su-row"><input id="su-root" class="mc-field" value="{E(str(realm_root))}" spellcheck="false">'
        + _btn("Choose…", "mcSuPick()", "secondary") + '</div>'
        '<p class="mc-hint">Choose a new or empty folder. Your existing realm, agents and their work move together.</p>'
        + _known(others, "Other realms on this computer")
        + '<p class="mc-su-msg" id="su-homemsg" role="status"></p>',
        _btn("Back", "mcSuGo('checks')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Continue", "mcSuHome(this)", "primary", "su-home-next"))
    dialog = '<dialog id="su-profile-dialog" class="mc-su-profile-dialog" aria-labelledby="su-profile-title"><div id="su-profile-content"></div></dialog>'
    return intro + welcome + checks + home + _naming_pane() + _team_pane() + dialog



def render_realm_half(realm, realm_root, step: str = "capabilities", dark: bool = False) -> str:
    from .agentbits import _portrait
    coord = realm.coordinator or (realm.members[0] if realm.members else None)
    cname = coord.display if coord else "Your coordinator"
    ctitle = coord.theme_role if coord else ""
    owner = setupflow.owner_of(realm_root)
    template = setupflow.template_of(realm_root)
    vals = {"coordinator": cname, "owner": owner, "realm": realm.name,
            "collective": realm.theme_collective or "team"}
    caps = _pane(
        "capabilities", _say("capabilities", "intro", "curated", "who", **vals),
        '<p class="mc-hint" id="su-cap-selection-help">Checkboxes add capabilities to your realm. Toggles choose which start enabled. Connections still need authentication before they can be used.</p>'
        f'<div class="mc-su-caps">{_cap_rows(template, realm_root)}</div>'
        '<p class="mc-su-msg" id="su-capmsg" role="status"></p>',
        _btn("Back", "mcSuGo('team')", "secondary")
        + '<span class="mc-su-grow"></span>'
        + '<button type="button" class="btn-link" onclick="mcSuCapsSkip()">I’ll do this later</button>'
        + _btn("Add and continue", "mcSuCapsAdd(this)", "primary", "su-caps-add"))
    from .threadsview import _turn
    portrait = _portrait(realm_root, coord, 28) if coord else ""
    prompt = setupflow.brief_prompt(owner)
    prompt_turn = _turn('user', prompt, '', 0, False, '', '', cname, True, actions=False)
    reply_turn = _turn('assistant', '', '', 1, False, '', '', cname, True, av=portrait, actions=False)
    reply_turn = reply_turn.replace('class="mc-body mc-md"', 'class="mc-body mc-md" id="su-replybody"')
    first = _pane(
        "first-job", _say("first-job", "intro", "cost", **vals),
        f'''<div class="mc-su-thread"><div id="su-brief-prompt">{prompt_turn}</div>
<div id="su-reply" hidden>{reply_turn}</div></div>
<span class="mc-hint" id="su-replytime"></span>
<p class="mc-su-msg" id="su-briefmsg" role="status"></p>''',
        _btn("Back", "mcSuGo('capabilities')", "secondary")
        + '<span class="mc-su-grow"></span>'
        + '<button type="button" class="btn-link" id="su-brief-skip" onclick="mcSuBriefSkip()">Skip for now</button>'
        + _btn("Run the first brief", "mcSuBrief(this)", "primary", "su-brief-run"))
    tiles = "".join(
        f'<div class="mc-su-tile"><span class="mc-su-tileicon">{ic}</span><div><div class="mc-h-sect">{E(t)}</div>'
        f'<p>{E(ws.line("tour", k))}</p></div></div>'
        for k, t, ic in (("overview", "Overview", _icon("monitor", 20)),
                         ("agents", "Agents", _icon("ai-agent", 20)),
                         ("jobs", "Jobs", _icon("calendar-clock", 20)),
                         ("help", "Support - I'll always be here if you need me", _icon("support-ai", 22))))
    tour = _pane("tour", _say("tour", "intro"), f'<div class="mc-su-tiles">{tiles}</div>',
                 _btn("Back", "mcSuGo('first-job')", "secondary") + '<span class="mc-su-grow"></span>'
                 + _btn("Continue", "mcSuGo('done')", "primary"))
    done = _pane(
        "done", _say("done", "intro" if owner else "intro_noname", "next", "sign_off", **vals),
        '<ul class="mc-su-summary" id="su-summary"></ul>'
        f'<p class="mc-su-next-action">{_icon("telegram-logo", 18)} <span>After setup, connect Telegram to get updates and reach your agents away from this computer in Settings &gt; App settings.</span></p>'
        '<p class="mc-su-msg" id="su-donemsg" role="status"></p>',
        _btn("Back", "mcSuGo('tour')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn(f"Open {E(realm.name)}", "mcSuFinish(this)", "primary", "su-finish")
        + _btn("Open and connect Telegram now", "mcSuFinish(this,'/settings?tab=app#st-telegram')", "secondary"))
    from .. import setupteam
    data = {"half": "realm", "presets": _presets(), "savedTeam": setupteam.draft(realm_root), "script": setupflow.script(), "vals": vals,
            "coordinator": coord.id if coord else "", "agents": len(realm.agents),
            "briefThread": setupflow.BRIEF_THREAD, "briefTitle": setupflow.BRIEF_TITLE,
            "briefPrompt": prompt,
            "capsOn": setupflow.caps_on(realm_root),
            "briefDone": setupflow.brief_done(realm_root, coord.id if coord else "")}
    step = step if step in setupflow.ALL_STEPS else setupflow.REALM_STEPS[0]
    return _shell(_saved_start(realm, realm_root, owner) + caps + first + tour + done, step, data, dark, 0)
