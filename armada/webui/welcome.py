"""The first-run page (launch plan 5.3): what the app shows when there is no realm to open.

Before this, `armada app` with nothing to open printed a sentence to a console that pythonw doesn't
have and exited — a new user double-clicked the icon and nothing happened at all. Now the server
starts without a realm ("welcome mode", see serve.Handler._route_welcome_*) and every page is this
one: choose ARMADA's folder, create a first realm or open one you already have, and — because
nothing works without it — the Claude sign-in bar. Creating or opening a realm switches the server
into it; from then on it's the normal app.

Deliberately small. The guided setup (Phase 6) replaces the middle of this page; the page itself —
the mode, the routes it may call, the switch at the end — is what 6 builds on.
"""
from __future__ import annotations

import os
from pathlib import Path

from .. import approot, brand
from ..assets import CSS_LINKS, AUTHBAR_JS, js
from ._base import E

WELCOME_JS = js("welcome")

_TPL_ORDER = ("state", "company", "crew", "scratch")
_TPL_LABEL = {"state": "State", "company": "Company", "crew": "Crew", "scratch": "Blank"}


def suggested_root() -> str:
    """Where to suggest ARMADA's folder when none is set: `ARMADA` in the user's home folder."""
    return str(Path(os.path.expanduser("~")) / brand.NAME)


def _tpl_cards() -> str:
    from ..templates import TEMPLATES
    out = []
    for i, k in enumerate(k for k in _TPL_ORDER if k in TEMPLATES):
        th = TEMPLATES[k]["theme"]
        n = len(TEMPLATES[k].get("agents") or [])
        who = (f'{E(th["collective"])} of {E(th["agent"])}s, led by a {E(th["coordinator"])}'
               if n else "Start empty and add your own")
        out.append(
            f'<label class="mc-wtpl mc-frame"><input type="radio" name="w-tpl" value="{E(k)}"'
            f'{" checked" if i == 0 else ""}><span class="mc-h-sect">{E(_TPL_LABEL.get(k, k.title()))}</span>'
            f'<span class="mc-hint">{who}</span></label>')
    return "".join(out)


def _known_realms(realms: list) -> str:
    if not realms:
        return ""
    rows = "".join(
        f'<li><a class="btn btn-sm" href="/switch?path={E(_q(r["path"]))}&amp;to=/">Open</a>'
        f'<span><b>{E(r.get("name") or Path(r["path"]).name)}</b>'
        f'<span class="mc-hint"> {E(r["path"])}</span></span></li>' for r in realms)
    return (f'<section class="mc-wcard mc-frame"><h2 class="mc-h-card">Pick up where you left off</h2>'
            f'<p class="mc-hint">ARMADA knows these realms but not which one you were using.</p>'
            f'<ul class="mc-wlist">{rows}</ul></section>')


def _q(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(str(s), safe="")


def render_welcome(realms: list | None = None, note: str = "", dark: bool = False) -> str:
    root = approot.root()
    have_root = approot.exists()
    root_val = root if root else suggested_root()
    root_state = (f'<p class="mc-wok">✓ Using <b id="w-rootshown">{E(root)}</b> '
                  f'<button class="btn-link" onclick="mcWelcomeEditRoot()">Change</button></p>'
                  if have_root else "")
    root_form = (
        f'<div id="w-rootform"{" hidden" if have_root else ""}>'
        f'<div class="mc-wrow"><input id="w-root" class="mc-field" value="{E(root_val)}" '
        f'aria-label="ARMADA folder">'
        f'<button class="btn btn-secondary" onclick="mcWelcomePick(\'w-root\')">Choose…</button>'
        f'<button class="btn btn-primary" onclick="mcWelcomeSetRoot(this)">Use this folder</button></div>'
        f'<p class="mc-hint">It will be created if it doesn’t exist.</p></div>')
    note_html = f'<p class="mc-wnote" role="alert">{E(note)}</p>' if note else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Welcome to {brand.NAME}</title>
{CSS_LINKS}</head>
<body class="{'armada-dark' if dark else ''}"><div id="mc-authbar"></div>
<main class="mc-welcome">
<div class="mc-wlogo">{brand.LOGO}{brand.BETA_PILL}</div>
<h1 class="mc-h-page">Welcome to {brand.NAME}</h1>
<p class="mc-wlede">A team of AI agents that work for you on this computer, through your Claude
subscription. Two steps and you’re in.</p>
{note_html}{_known_realms(realms or [])}
<section class="mc-wcard mc-frame"><h2 class="mc-h-card"><span class="mc-wnum">1</span>Choose {brand.NAME}’s folder</h2>
<p class="mc-hint">Everything {brand.NAME} makes lives inside this one folder — every realm, every
agent’s memory, every file they write. It’s the folder to back up.</p>
{root_state}{root_form}<p class="mc-wmsg" id="w-rootmsg" role="status"></p></section>
<section class="mc-wcard mc-frame" id="w-step2"{"" if have_root else ' aria-disabled="true"'}>
<h2 class="mc-h-card"><span class="mc-wnum">2</span>Create your first realm</h2>
<p class="mc-hint">A realm is one team with its own agents, memory and jobs — say one for work and
one for home. The template only sets the words and a starter team; you can change both later.</p>
<label class="mc-label" for="w-name">Name</label>
<input id="w-name" class="mc-field" placeholder="e.g. Personal" maxlength="60">
<label class="mc-label">Template</label><div class="mc-wtpls">{_tpl_cards()}</div>
<div class="mc-wrow mc-wend"><button class="btn btn-primary" id="w-create" onclick="mcWelcomeCreate(this)">Create realm</button></div>
<p class="mc-wmsg" id="w-createmsg" role="status"></p>
<p class="mc-hint mc-wor">Already have a realm — from another computer, or a backup?
<button class="btn-link" onclick="mcWelcomeAdopt(this)">Open a realm folder…</button></p>
<p class="mc-wmsg" id="w-adoptmsg" role="status"></p></section>
<p class="mc-hint mc-wfoot">{brand.NAME} runs every agent through Claude Code, signed in with your
Claude account. It never sees your password.</p>
</main>{AUTHBAR_JS}{WELCOME_JS}</body></html>"""
