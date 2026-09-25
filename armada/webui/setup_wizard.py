"""The setup wizard (launch plan 6.4): ARMADA's first run, with Alexander as the guide.

Replaces the middle of the 5.3 welcome page. Eight steps in two halves (setupflow explains why):

    welcome · checks · folder · team      — before a realm exists (welcome mode, "/")
    capabilities · first job · tour · done — inside the new realm ("/setup")

Both halves are drawn by the same shell, so crossing from one to the other (creating the realm and
switching the server into it) looks like the next step rather than a new page. Everything Alexander
says comes from armada/alexander/wizard_script.py; nothing here is generated.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import approot, brand, setupflow
from ..alexander import AVATAR, NAME as ALEX, ROLE as ALEX_ROLE, wizard_script as ws
from ..assets import CSS_LINKS, js
from ..icons import _icon
from ._base import E

SETUP_JS = js("setup")

_TPL_ORDER = ("state", "company", "crew", "scratch")
_TPL_LABEL = {"state": "State", "company": "Company", "crew": "Crew", "scratch": "Blank"}
INSTALL_CMD = "irm https://claude.ai/install.ps1 | iex"
INSTALL_DOCS = "https://code.claude.com/docs/en/setup"


def _say(step: str, *keys: str, **vals) -> str:
    """Alexander's lines for a step, as paragraphs; the first is the lede."""
    out = []
    for i, k in enumerate(keys):
        cls = "mc-su-lede" if i == 0 else ""
        out.append(f'<p class="{cls}" data-line="{E(step)}.{E(k)}">{E(ws.line(step, k, **vals))}</p>')
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
            "dot": '<i class="mc-su-dot"></i>'}


def _shell(panes: str, first: str, data: dict, dark: bool, done_upto: int) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Welcome to {brand.NAME}</title>
{CSS_LINKS}</head>
<body class="mc-su-page{' armada-dark' if dark else ''}">
<header class="mc-su-top"><div class="mc-su-brand">{brand.LOGO}{brand.BETA_PILL}</div>
<div class="mc-su-count mc-eyebrow" id="su-count"></div></header>
<main class="mc-su-stage">
<aside class="mc-su-guide">
<div class="mc-su-alex"><img class="mc-su-portrait" src="{AVATAR}" width="84" height="84" alt="">
<div><div class="mc-su-name">{E(ALEX)}</div><div class="mc-eyebrow">{E(ALEX_ROLE)}</div></div></div>
{_rail(first, done_upto)}
</aside>
<section class="mc-su-card" id="su-card" aria-live="polite">{panes}</section>
</main>
<script>window.MC_SU={json.dumps({**data, "first": first, "icons": _icons()}, ensure_ascii=False).replace("</", "<\\/")};</script>
{SETUP_JS}</body></html>"""


# --- the first half: before the realm ------------------------------------------------------------

def _known(realms: list) -> str:
    if not realms:
        return ""
    rows = "".join(
        f'<li><span><b>{E(r.get("name") or Path(r["path"]).name)}</b>'
        f'<span class="mc-hint"> {E(r["path"])}</span></span>'
        f'<a class="btn btn-secondary btn-sm" href="/switch?path={E(_q(r["path"]))}&amp;to=/">Open</a></li>'
        for r in realms)
    return (f'<div class="mc-su-known"><div class="mc-label">Pick up where you left off</div>'
            f'<ul class="mc-su-list">{rows}</ul></div>')


def _q(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(str(s), safe="")


def _tpl_cards() -> str:
    from ..templates import TEMPLATES
    out = []
    for i, k in enumerate(k for k in _TPL_ORDER if k in TEMPLATES):
        th = TEMPLATES[k]["theme"]
        n = len(TEMPLATES[k].get("agents") or [])
        who = (f'{n} {E(th["agent"].lower())}s, led by the {E(th["coordinator"])}' if n
               else "You name every agent")
        out.append(
            f'<label class="mc-su-tpl"><input type="radio" name="su-tpl" value="{E(k)}"'
            f'{" checked" if i == 0 else ""}><span class="mc-su-tplicon">{_icon(th.get("icon") or "compass", 22)}</span>'
            f'<span class="mc-su-tpltext"><span class="mc-h-sect">{E(_TPL_LABEL.get(k, k.title()))}</span>'
            f'<span class="mc-hint">{who}</span></span></label>')
    return "".join(out)


def _presets() -> dict:
    """What the team step shows for each template: names and roles only (the instructions stay on
    the server — see RealmRoutes._wizard_agents)."""
    from ..templates import TEMPLATES
    return {k: {"collective": t["theme"]["collective"], "coordinator": t["theme"]["coordinator"],
                "agent": t["theme"]["agent"],
                "agents": [{"id": a.get("id"), "display": a.get("display"), "role": a.get("role", ""),
                            "coordinator": bool(a.get("coordinator"))} for a in t.get("agents") or []]}
            for k, t in TEMPLATES.items()}


def render_welcome_half(realms: list | None = None, note: str = "", dark: bool = False) -> str:
    root = approot.root()
    from .welcome import suggested_root
    note_html = f'<p class="mc-su-note" role="alert">{E(note)}</p>' if note else ""
    welcome = _pane(
        "welcome", _say("welcome", "intro", "what", "how"),
        note_html + _known(realms or []),
        f'<button type="button" class="btn-link" onclick="mcSuAdopt(this)">I already have a realm folder</button>'
        f'<span class="mc-su-grow"></span>'
        + _btn("Let’s begin", "mcSuGo('checks')") + '<p class="mc-su-msg" id="su-adoptmsg" role="status"></p>')
    checks = _pane(
        "checks", _say("checks", "intro") + '<div class="mc-su-say mc-su-say-more"><p id="su-checkline"></p></div>',
        f'''<ul class="mc-su-checks">
<li class="mc-su-check" id="su-ck-cli"><span class="mc-su-ckicon"></span><span class="mc-su-cktext">
<b>Claude Code</b><span class="mc-hint" id="su-ck-cli-d">Checking…</span></span>
<span class="mc-su-ckact" id="su-ck-cli-a" hidden>{_btn("Install Claude Code", "mcSuInstall(this)", "secondary")}</span></li>
<li class="mc-su-install" id="su-install" hidden><span class="mc-hint">It opens Anthropic’s own installer in a
PowerShell window. Or paste this into PowerShell yourself:</span>
<span class="mc-su-cmd"><code id="su-cmd">{E(INSTALL_CMD)}</code><button type="button" class="mc-iconbtn"
title="Copy" onclick="mcSuCopy(this)">{_icon("copy", 14)}</button></span>
<a class="mc-hint" href="{E(INSTALL_DOCS)}" target="_blank" rel="noopener">Claude Code’s install guide</a></li>
<li class="mc-su-check" id="su-ck-auth"><span class="mc-su-ckicon"></span><span class="mc-su-cktext">
<b>Your Claude account</b><span class="mc-hint" id="su-ck-auth-d">Checking…</span></span>
<span class="mc-su-ckact" id="su-ck-auth-a" hidden>{_btn("Sign in", "mcSuSignIn(this)", "secondary")}</span></li>
<li class="mc-su-check is-info"><span class="mc-su-ckicon">{_icon("calendar-clock", 16)}</span><span class="mc-su-cktext">
<b>The scheduler</b><span class="mc-hint">{E(ws.line("checks", "scheduler"))}</span></span></li>
</ul>''',
        _btn("Back", "mcSuGo('welcome')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Check again", "mcSuCheck(true)", "secondary", "su-recheck")
        + _btn("Continue", "mcSuGo('home')", "primary", "su-checks-next", " disabled"))
    root_val = root or suggested_root()
    home = _pane(
        "home", _say("home", "intro", "realm"),
        f'''<label class="mc-label" for="su-root">{brand.NAME}’s folder</label>
<div class="mc-su-row"><input id="su-root" class="mc-field" value="{E(root_val)}" spellcheck="false">
{_btn("Choose…", "mcSuPick()", "secondary")}</div>
<p class="mc-hint">It’s created if it doesn’t exist.</p>
<div class="mc-su-two"><div><label class="mc-label" for="su-owner">Your name</label>
<input id="su-owner" class="mc-field" maxlength="60" placeholder="What should the team call you?" autocomplete="given-name"></div>
<div><label class="mc-label" for="su-name">Realm name</label>
<input id="su-name" class="mc-field" maxlength="60" placeholder="e.g. Home, or Work"></div></div>
<p class="mc-su-msg" id="su-homemsg" role="status"></p>''',
        _btn("Back", "mcSuGo('checks')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Continue", "mcSuHome(this)", "primary", "su-home-next"))
    team = _pane(
        "team", _say("team", "intro") + '<div class="mc-su-say mc-su-say-more"><p id="su-tplline"></p></div>',
        f'''<div class="mc-su-tpls" role="radiogroup" aria-label="Template">{_tpl_cards()}</div>
<div class="mc-su-teamhead"><span class="mc-label" id="su-teamlabel">Your team</span>
<span class="mc-hint" id="su-pickedline"></span></div>
<div class="mc-su-team" id="su-team"></div>
<button type="button" class="btn-link" id="su-addagent" onclick="mcSuAddAgent()">{_icon("plus", 13)} Add an agent</button>
<p class="mc-su-msg" id="su-teammsg" role="status"></p>''',
        _btn("Back", "mcSuGo('home')", "secondary") + '<span class="mc-su-grow"></span>'
        + _btn("Appoint the team", "mcSuAppoint(this)", "primary", "su-appoint"))
    data = {"half": "welcome", "script": setupflow.script(), "presets": _presets(),
            "haveRoot": approot.exists()}
    return _shell(welcome + checks + home + team, "welcome", data, dark, 0)


# --- the second half: inside the realm -----------------------------------------------------------

def _cap_rows(template: str) -> str:
    from .. import recommended
    recs = setupflow.recommended_for(template)
    out = []
    for gid, gtitle, gline in recommended.GROUPS:
        rows = [r for r in recs if r["group"] == gid]
        if not rows:
            continue
        items = "".join(
            f'''<label class="mc-su-cap" data-key="{E(r["key"])}">
<span class="mc-toggle"><input type="checkbox" class="su-cap"{" checked" if r["on"] else ""}><span class="mc-toggle-sl"></span></span>
<span class="mc-su-captext"><span class="mc-su-capname">{E(r["name"])}
<span class="mc-pill is-ok">Low risk</span></span>
<span class="mc-su-capdoes">{E(r["does"])}</span>
{f'<span class="mc-hint">{E(r["note"])}</span>' if r.get("note") else ""}</span>
<span class="mc-su-capst" aria-live="polite"></span></label>''' for r in rows)
        out.append(f'<div class="mc-su-capgroup"><div class="mc-su-caphead"><span class="mc-h-sect">{E(gtitle)}</span>'
                   f'<span class="mc-hint">{E(gline)}</span></div>{items}</div>')
    return "".join(out)


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
        "capabilities", _say("capabilities", "intro", "curated", **vals),
        f'<div class="mc-su-caps">{_cap_rows(template)}</div>'
        f'<div class="mc-su-aside"><img src="{AVATAR}" width="26" height="26" alt="">'
        f'<div><p>{E(ws.line("capabilities", "who", **vals))}</p>'
        f'<p>{E(ws.line("capabilities", "later", **vals))}</p></div></div>'
        '<p class="mc-su-msg" id="su-capmsg" role="status"></p>',
        f'<button type="button" class="btn-link" onclick="mcSuCapsSkip()">Not now</button>'
        '<span class="mc-su-grow"></span>'
        + _btn("Add these", "mcSuCapsAdd(this)", "primary", "su-caps-add"))
    portrait = _portrait(realm_root, coord, 44) if coord else ""
    first = _pane(
        "first-job", _say("first-job", "intro", "cost", **vals),
        f'''<div class="mc-su-agent">{portrait}<div><div class="mc-su-agentname">{E(cname)}</div>
<div class="mc-eyebrow">{E(ctitle)}</div></div></div>
<div class="mc-su-ask"><div class="mc-label">Sent on your behalf</div>
<p id="su-brief-prompt">{E(setupflow.brief_prompt(owner))}</p></div>
<div class="mc-su-reply" id="su-reply" hidden><div class="mc-su-replyhead"><span class="mc-label">{E(cname)}’s reply</span>
<span class="mc-hint" id="su-replytime"></span></div><div class="mc-md" id="su-replybody"></div></div>
<p class="mc-su-msg" id="su-briefmsg" role="status"></p>''',
        f'<button type="button" class="btn-link" id="su-brief-skip" onclick="mcSuBriefSkip()">Skip for now</button>'
        '<span class="mc-su-grow"></span>'
        + _btn("Run the first brief", "mcSuBrief(this)", "primary", "su-brief-run"))
    tiles = "".join(
        f'<div class="mc-su-tile"><span class="mc-su-tileicon">{ic}</span><div><div class="mc-h-sect">{E(t)}</div>'
        f'<p>{E(ws.line("tour", k))}</p></div></div>'
        for k, t, ic in (("overview", "Overview", _icon("monitor", 20)),
                         ("agents", "Agents", _icon("ai-agent", 20)),
                         ("jobs", "Jobs", _icon("calendar-clock", 20)),
                         ("help", "Help, and me", f'<img src="{AVATAR}" width="22" height="22" alt="">')))
    tour = _pane("tour", _say("tour", "intro"), f'<div class="mc-su-tiles">{tiles}</div>',
                 _btn("Back", "mcSuGo('first-job')", "secondary") + '<span class="mc-su-grow"></span>'
                 + _btn("Continue", "mcSuGo('done')", "primary"))
    done = _pane(
        "done", _say("done", "intro" if owner else "intro_noname", "next", "sign_off", **vals),
        '<ul class="mc-su-summary" id="su-summary"></ul>',
        '<span class="mc-su-grow"></span>'
        + _btn(f"Open {E(realm.name)}", "mcSuFinish(this)", "primary", "su-finish"))
    data = {"half": "realm", "script": setupflow.script(), "vals": vals,
            "coordinator": coord.id if coord else "", "agents": len(realm.agents),
            "briefThread": setupflow.BRIEF_THREAD, "briefTitle": setupflow.BRIEF_TITLE,
            "capsOn": setupflow.caps_on(realm_root),
            "briefDone": setupflow.brief_done(realm_root, coord.id if coord else "")}
    step = step if step in setupflow.REALM_STEPS else setupflow.REALM_STEPS[0]
    return _shell(caps + first + tour + done, step, data, dark, 4)
