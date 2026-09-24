"""Capabilities / connectors / skills rendering (Layer 2, Phase 3).

Imports lower layers (never _core); _core re-imports these names.

The Catalogue tab's own rendering (search results, the bring-a-link review report, the info box)
moved to catalogue.py in this package (Phase 2, 2.4) — a pure move, no behaviour change. What
stays here is the User tab, the System tab, the cross-cutting trust-model helpers both tabs'
cards are built from, and _realm_skills, the page that stitches all three tabs together.
"""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status, sysskills
from .. import goals as goalsmod
from ..icons import ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR
from ._base import (E, _J, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _mini_pill, _poss)
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _ordinal, _next_hint, _fmt_ts)
# Externalized inline <script> blocks (Phase 2, 2.1) — bodies live in webui/static/js/.
from ..assets import (FDROP_JS as _FDROP_JS, CAPHELP_JS as _CAPHELP_JS,
                      CAPEDIT_JS as _CAPEDIT_JS, CONNMODAL_JS as _CONNMODAL_JS,
                      CAPFILTER_JS as _CAPFILTER_JS, CAPANIM_JS as _CAPANIM_JS,
                      CAPTAB_JS as _CAPTAB_JS, CAPDRAG_JS as _CAPDRAG_JS)
from .agentbits import (_activity_dot, _agent_activity, _agent_busy, _agent_has_unread,
    _agent_model_effort, _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust,
    _goals_cell, _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta, _filter_dropdown,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


def _cap_manage_btn() -> str:
    return (f'<button class="btn btn-secondary" style="font-size:12px;padding:5px 11px;display:inline-flex;'
            f'align-items:center;gap:5px" onclick="mcCapHelp(true)">{_icon("settings",13)}Manage</button>')


_CAP_HELP = (
    '<div id="mc-caphelp" class="mc-modal-ov" onclick="if(event.target===this)mcCapHelp(false)">'
    '<div class="mc-modal-box" style="padding:20px;width:min(560px,92vw);max-height:82vh;overflow:auto">'
    '<div style="display:flex;align-items:center;margin-bottom:12px"><div style="font-family:var(--font-heading);'
    'font-weight:600;font-size:17px">Managing capabilities</div>'
    '<button class="btn btn-secondary" style="margin-left:auto;font-size:12px;padding:4px 10px" onclick="mcCapHelp(false)">Close</button></div>'
    '<div style="font-size:12.5px;line-height:1.6;background:var(--color-sand-100);border:1px solid var(--color-sand-300);'
    'border-radius:var(--r);padding:10px 12px;margin-bottom:14px">'
    'ARMADA runs on <b>your own Claude</b>. A connector, skill, or plugin has to be added and authorised in '
    'Claude first — then it becomes available to your agents here. ARMADA shows what’s wired up and lets you '
    'scope it per agent; it doesn’t install or hold credentials itself.<br><br>'
    'The type (below) is how Claude names things. What actually decides trust is shown on every item as three '
    'signals: <b>who made it</b>, whether it <b>runs code on your machine</b>, and <b>what it can touch</b> '
    '(files · network · shell · connectors). Expand any item to see where it came from and what a content scan '
    'found. Treat a third-party item that runs code like installing an app from the internet.</div>'
    '<div style="display:flex;flex-direction:column;gap:10px;font-size:12.5px;line-height:1.55">'
    '<div style="display:flex;gap:10px"><span style="display:flex;color:var(--color-accent);margin-top:1px">'
    + _icon("cap-connector", 16) + '</span>'
    '<div><b>Connector</b> — a <b>remote</b> link to an outside service (a broker, Google Drive, Telegram, a data '
    'feed). A hosted integration an agent uses to read or send real data.</div></div>'
    '<div style="display:flex;gap:10px"><span style="display:flex;color:var(--color-accent);margin-top:1px">'
    + _icon("puzzle", 16) + '</span>'
    '<div><b>Extension</b> — a <b>local</b> tool running on this machine (local files, a private script, a '
    'developer tool). Like a connector, but it stays on your computer rather than calling out to the cloud.</div></div>'
    '<div style="display:flex;gap:10px"><span style="display:flex;color:var(--color-accent);margin-top:1px">'
    + _icon("cap-skill", 16) + '</span>'
    '<div><b>Skill</b> — a packaged instruction set that teaches an agent a repeatable way of doing something '
    '(a house writing style, a review checklist, a workflow).</div></div>'
    '<div style="display:flex;gap:10px"><span style="display:flex;color:var(--color-accent);margin-top:1px">'
    + _icon("cap-plugin", 16) + '</span>'
    '<div><b>Plugin</b> — a bundle that can bring several skills and connectors together, installed as one unit.</div></div>'
    '</div></div></div>'
    + _CAPHELP_JS)


_CAP_EDIT_MODAL = (
    '<div id="mc-cap-modal" class="mc-modal-ov" style="z-index:210" onclick="if(event.target===this)mcCapClose()">'
    '<div class="mc-modal-box" style="padding:20px;width:min(500px,92vw)">'
    '<div style="display:flex;align-items:center;margin-bottom:8px"><div id="mc-cap-title" style="font-family:var(--font-heading);'
    'font-weight:600;font-size:17px">Add capability</div></div>'
    '<div id="mc-cap-note" style="font-size:12px;color:var(--text-dim);margin-bottom:10px">'
    'Capabilities you define yourself. Anything from a published source is added from the '
    '"Add a capability" tab, and anything wired up in Claude appears here on its own.</div>'
    '<input type="hidden" id="mc-cap-scope"><input type="hidden" id="mc-cap-kind"><input type="hidden" id="mc-cap-id">'
    f'<label style="{_LBL};margin-top:0">Name {_STAR}</label><input id="mc-cap-name" placeholder="E.g. Weekly report template" style="{_FIELD}">'
    f'<label style="{_LBL}">Description</label><input id="mc-cap-descr" placeholder="E.g. house format for the Monday note" style="{_FIELD}">'
    f'<label style="{_LBL}">Status</label><select id="mc-cap-status" style="{_FIELD}"><option value="connected">Connected</option><option value="planned">Planned</option></select>'
    '<div style="margin-top:14px;display:flex;gap:8px;align-items:center">'
    '<button class="btn btn-primary" style="color:#fff;font-size:12.5px;padding:6px 14px" onclick="mcCapSave()">Save</button>'
    '<button class="btn btn-secondary" style="font-size:12.5px;padding:6px 14px" onclick="mcCapClose()">Cancel</button>'
    '<span id="mc-cap-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div></div>'
    # delete-confirm modal
    '<div id="mc-cap-del" class="mc-modal-ov" style="z-index:211" onclick="if(event.target===this)mcCapDelClose()">'
    '<div class="mc-modal-box" style="width:min(400px,92vw)">'
    '<div style="font-family:var(--font-heading);font-weight:600;font-size:16px;margin-bottom:6px">Remove capability?</div>'
    '<div id="mc-capdel-note" style="font-size:12.5px;color:var(--text-dim);margin-bottom:12px"></div>'
    '<input type="hidden" id="mc-capdel-scope"><input type="hidden" id="mc-capdel-kind"><input type="hidden" id="mc-capdel-id">'
    '<div style="display:flex;gap:8px;align-items:center">'
    '<button class="btn btn-secondary" style="font-size:12px;padding:5px 12px" onclick="mcCapDelClose()">Cancel</button>'
    '<button class="btn btn-primary" style="background:var(--status-bad);border-color:var(--status-bad);color:#fff;font-size:12px;padding:5px 12px" onclick="mcCapDelGo()">Remove</button>'
    '<span id="mc-capdel-msg" style="font-size:12px;color:var(--text-muted)"></span></div></div></div>'
    + _CAPEDIT_JS)


_CONNECTOR_MODAL = (
    '<div id="mc-conn-modal" class="mc-modal-ov" style="z-index:210" onclick="if(event.target===this)mcConnClose()">'
    '<div class="mc-modal-box" style="padding:20px;width:min(500px,92vw)">'
    '<div style="display:flex;align-items:center;margin-bottom:10px"><div style="font-family:var(--font-heading);'
    'font-weight:600;font-size:17px">Add a connector</div>'
    '<button class="btn btn-secondary" style="margin-left:auto;font-size:12px;padding:4px 10px" onclick="mcConnClose()">Close</button></div>'
    '<div style="font-size:12.5px;line-height:1.6">Connectors are enabled in <b>Claude</b>, not here — that is where the sign-in '
    'and credentials live. Add or authorise the connector in your Claude connector settings (or via <span class="mono">claude mcp</span>), '
    'then come back and hit the <b>refresh</b> icon next to Connectors to pull it in.</div>'
    '<div style="margin-top:14px;display:flex;gap:8px;align-items:center">'
    '<button class="btn btn-primary" style="color:#fff;font-size:12.5px;padding:6px 14px;display:inline-flex;align-items:center;gap:6px" onclick="mcConnClose();mcConnectorRefresh(this)">Refresh from Claude</button>'
    '<button class="btn btn-secondary" style="font-size:12.5px;padding:6px 12px" onclick="mcConnClose()">OK</button></div></div></div>'
    + _CONNMODAL_JS)


def _tab_skills(realm, realm_root, a) -> str:
    """One agent's capabilities: what it can use, and what the realm has that it can't.

    This page used to say realm-wide tools were inherited by every agent and then list the whole
    catalogue. That was true before grants and is now the opposite of true — and it was the worse
    kind of wrong, because the realm page and this one disagreed about the same fact. The realm
    catalogue plus the grant list is the source of truth; this reads from it.
    """
    from .. import capabilities as _caps
    # By id, not a synthesised dict: capabilities._agent() trusts a dict it's handed, so a partial
    # one (id + coordinator, no toolkit) reports zero grants and the page quietly shows an agent as
    # having nothing. Pass the id and let it read the real agent.json.
    usable = _caps.usable(realm_root, a.id)
    rest = _caps.requestable(realm_root, a.id)

    if a.is_coordinator:
        why = (f'As {E(realm.theme_coordinator)}, {E(a.display)} can use every capability in the '
               f'realm. That follows the role — there is no per-capability list to manage here.')
    else:
        n = sum(len(v) for v in usable.values())
        why = (f'{E(a.display)} can use only what you have given them: '
               f'<b>{n}</b> of <b>{n + sum(len(v) for v in rest.values())}</b> in the realm. '
               f'Give or remove access on the <a href="/skills" style="color:var(--color-accent-2);'
               f'text-decoration:none">Capabilities page</a>, by dragging an agent onto a '
               f'capability there.')

    # This page answers one question — what can this agent use — and every control that belongs to
    # the catalogue (Manage, the connector refresh, updates) lives on the realm page. Repeating
    # them here gave two places to do one job, and the copies here were the ones that misbehaved.
    def groups(inv, manage):
        return (f'{_tool_group("Connectors", "cap-connector", inv["connectors"], manage=manage)}'
                f'<div style="height:20px"></div>'
                f'{_tool_group("Extensions", "puzzle", inv["extensions"], manage=manage)}'
                f'<div style="height:20px"></div>'
                f'{_tool_group("Skills", "cap-skill", inv["skills"], manage=manage)}'
                f'<div style="height:20px"></div>'
                f'{_tool_group("Plugins", "cap-plugin", inv["plugins"], manage=manage)}')

    # Read-only, manage=None: with a scope passed, each card grew its own enable/edit/delete acting
    # on this agent's toolkit — a third place to change a capability, next to a sentence saying the
    # Capabilities page is where you change capabilities. The add/edit modals go with them; without
    # those controls nothing could open them anyway.
    # The same key the realm page carries, in the same rail. The cards here are the realm page's
    # cards — same tier stripe, same ability icons — so reading them needed the same legend, and
    # not having it here meant learning the colours on one page to use them on another.
    return (f'<div style="display:flex;gap:32px;align-items:flex-start;padding:18px 24px 24px">'
            f'<div style="flex:1;min-width:0;max-width:820px">'
            f'<div style="margin-bottom:4px">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:17px">Capabilities</div>'
            f'<div style="font-size:11.5px;color:var(--text-muted);line-height:1.5">{why}</div></div>'
            f'<div style="height:10px"></div>'
            f'{groups(usable, None)}'
            f'{_CAP_HELP}</div>'
            f'<div style="flex:none;width:390px">'
            f'<div style="position:sticky;top:16px">{_cap_legend()}</div></div></div>')


def _toolkit_from(js: dict) -> dict:
    tk = js.get("toolkit") or {}
    return {"connectors": tk.get("connectors", []) or [],
            "extensions": tk.get("extensions", []) or [],
            "skills": tk.get("skills", []) or [],
            "plugins": tk.get("plugins", []) or []}


def _realm_toolkit(realm_root) -> dict:
    p = Path(realm_root) / "realm.json"
    return _toolkit_from(json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {})


def _agent_toolkit(realm_root, aid: str) -> dict:
    p = Path(realm_root) / "agents" / aid / "agent.json"
    return _toolkit_from(json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {})


# ---- trust model (cross-cutting signals shown on every capability, any bucket) -------------------
# Riskiest first. The order here is the order the legend and the filter dropdown render in, and a
# risk scale reads top-down from the thing you need to look at.
_TIER_META = {"red": ("var(--status-bad)", "Caution"),
              "amber": ("var(--status-warn)", "Review"),
              "green": ("var(--status-ok)", "Trusted")}
_RUNS_META = {"reads": ("reads only", "var(--color-accent-2)"),
              "code": ("runs code here", "var(--status-warn)"),
              "service": ("outside service", "var(--status-warn)")}
_SCOPE_CLR = {"files": "var(--color-accent)", "network": "var(--status-warn)",
              "connectors": "var(--status-ok)", "shell": "var(--status-bad)",
              "hooks": "var(--status-bad)"}
_RUNS_ICON = {"reads": "cap-reads", "code": "cap-code", "service": "cap-service"}
_SCOPE_ICON = {"files": "cap-files", "network": "cap-network", "shell": "terminal",
               "connectors": "cap-connector", "hooks": "zap"}
_RUNS_DESC = {"reads": "Reads only — uses instructions and data only; runs no code",
              "code": "Runs code here — runs code on your computer, with your permissions",
              "service": "Outside service — exchanges data with a remote service (sign-in)"}
_SCOPE_DESC = {"files": "Files — can create, edit and delete files on your computer",
               "network": "Network — can make internet requests to external services",
               "shell": "Shell — can run terminal commands on your computer",
               "connectors": "Connectors — can call your other connected services",
               # Hooks are the one ability that doesn't wait to be used. Everything else here is
               # something an agent can reach FOR; a hook runs on its own, on the engine's
               # lifecycle events, whether or not any agent asked for anything.
               "hooks": "Hooks — runs its own code automatically on the engine's events"}


# Per-ability risk colour — the icon's own tint (independent of the card tier): reads=safe(green),
# code/shell=high(red), everything else notable(amber). Used on the cards AND the legend, so shell
# is always red, reads-only always green, etc.
_ABILITY_CLR = {"reads": "var(--status-ok)", "code": "var(--status-bad)", "service": "var(--status-warn)",
                "files": "var(--status-warn)", "network": "var(--status-warn)",
                "connectors": "var(--status-warn)", "shell": "var(--status-bad)",
                "hooks": "var(--status-bad)"}


def _cap_iconcluster(it: dict) -> str:
    """Labelled Runs + Can-touch sections (small caption over its icons, per-ability risk colour),
    shown inline on the right of the title row."""
    def section(label, icons):
        return (f'<span style="display:flex;flex-direction:column;gap:2px;align-items:flex-start">'
                f'<span style="font-size:8.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:700;line-height:1">{label}</span>'
                f'<span style="display:flex;gap:8px;align-items:center">{icons}</span></span>')
    secs = ""
    runs = (it.get("runs") or "").lower()
    if runs in _RUNS_ICON:
        c = _ABILITY_CLR.get(runs, "var(--text-muted)")
        secs += section("Runs", f'<span title="{E(_RUNS_META[runs][0])}" style="display:flex;color:{c}">'
                                f'{_icon(_RUNS_ICON[runs], 16)}</span>')
    # Riskiest first, so the leading icon is the one that set the card's stripe. Sorted here
    # rather than trusted from the file: the order a capability happens to list its abilities
    # in is not a statement about them.
    touch = sorted((str(x).lower() for x in (it.get("touch") or [])),
                   key=lambda s: _ABILITY_RANK.index(s) if s in _ABILITY_RANK else 99)
    if touch:
        chips = ""
        for s in touch:
            ic = _SCOPE_ICON.get(s)
            if ic:
                c = _ABILITY_CLR.get(s, "var(--text-muted)")
                chips += f'<span title="{E(s)}" style="display:flex;color:{c}">{_icon(ic, 16)}</span>'
        if chips:
            secs += section("Can touch", chips)
    if not secs:
        return ""
    return f'<span style="display:flex;gap:22px;align-items:center;margin-right:14px">{secs}</span>'


def _cap_conn_info(it: dict, kind: str, ok: bool) -> str:
    """Connection state shown as a plain icon + text (not a pill) next to the name — only for things
    that actually connect, or when a state needs attention."""
    show = (kind == "connectors") or ((it.get("runs") or "").lower() == "service") or (not ok)
    if not show:
        return ""
    if ok:
        return (f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;color:var(--status-ok);flex:none">'
                f'<span style="display:flex">{_icon("circle-check", 13)}</span>Connected</span>')
    lab = (it.get("status") or "planned").title()
    return (f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;color:var(--status-bad);flex:none">'
            f'<span style="display:flex">{_icon("circle-x", 13)}</span>{E(lab)}</span>')
_KIND_SINGULAR = {"connectors": "Connector", "extensions": "Extension",
                  "skills": "Skill", "plugins": "Plugin"}


def _cap_made(it: dict) -> tuple:
    """(made-key, is-you) — who made it, where that is recorded.

    No display label any more. It used to return one, and its fallback for "nobody recorded a
    maker" was the string "Third-party", which is what the row pill showed for most capabilities.
    The pill now reports the SOURCE instead, and the publisher has its own line in the panel when
    one is actually named, so a manufactured stand-in has nothing left to stand in for.
    """
    made = (it.get("made") or ("you" if (it.get("source") or "").lower() == "custom" else "")).lower()
    return made, made == "you"


def _cap_tier(it: dict) -> str:
    """The risk tier. One implementation — every view reads this, nothing computes its own."""
    return _cap_tier_why(it)[0]


# Every ability, worst first. This is the order the legend renders in and the order the tier is
# computed from, so the stripe on a card is always the worst icon shown on it.
_ABILITY_RANK = ("hooks", "shell", "code", "service", "connectors", "files", "network", "reads")
_COLOUR_TIER = {"var(--status-bad)": "red", "var(--status-warn)": "amber", "var(--status-ok)": "green"}

# What each ability means for the tier, said as a sentence about the capability.
_ABILITY_WHY = {
    "hooks": "Ships hooks \u2014 its own code runs automatically on the engine's events.",
    "shell": "Can run terminal commands on your computer.",
    "code": "Runs code on your computer, with your permissions.",
    "service": "Exchanges your data with an outside service.",
    "connectors": "Can call your other connected services.",
    "files": "Can create, edit and delete files on your computer.",
    "network": "Can make internet requests.",
    "reads": "Reads only \u2014 supplies instructions and data, runs no code.",
}


def _cap_tier_why(it: dict) -> tuple:
    """(tier, one-line reason). Derived from checkable facts, never from an opinion.

    The tier is the worst thing the capability can do, and nothing else. That is what makes the
    card coherent: the coloured stripe is a summary of the ability icons printed next to it, so a
    row whose abilities are all amber cannot wear a red stripe and leave you looking for the
    reason. It also means the scale keeps discriminating — if every remote connector were Caution,
    Caution would stop meaning anything, because a connector talking to a remote service is the
    normal case rather than the alarming one.

    Provenance only decides the case where we know nothing yet. It cannot promote something past
    what it can reach: a capability that writes to your disk is not made safe by who published it.
    A blank used to fall through to green, which meant every plugin ARMADA discovered was rated
    Trusted by omission. Unknown is Review — red is for what we found, amber for what we
    haven't looked at.
    """
    t = (it.get("tier") or "").lower()
    if t in _TIER_META:
        return t, "Set by you."
    abilities = [str(x).lower() for x in (it.get("touch") or [])]
    runs = (it.get("runs") or "").lower()
    if runs:
        abilities.append(runs)
    known = [a for a in _ABILITY_RANK if a in abilities]
    if known:
        worst = known[0]
        return _COLOUR_TIER.get(_ABILITY_CLR.get(worst, ""), "amber"), _ABILITY_WHY[worst]
    # Nothing recorded about what it can reach. Provenance is all we have.
    made, you = _cap_made(it)
    if you:
        return "green", "You made this."
    if made == "anthropic":
        return "green", "Published by Anthropic, and it declares no abilities."
    if (it.get("curated") or "").lower() == "registry":
        return "amber", "Self-published to an open registry; nobody has reviewed it."
    return "amber", "Not inspected yet \u2014 what it can reach hasn't been recorded."


def _cap_persist(it: dict, kind: str) -> tuple:
    """(is-frozen, note). Explicit 'persist' wins; else derive: remote/service = living, local = frozen."""
    p = (it.get("persist") or "").lower()
    runs = (it.get("runs") or "").lower()
    if not p:
        p = "living" if (kind in ("connectors", "plugins") or runs == "service") else "frozen"
    note = it.get("persist_note") or ("Local artifact — audit once; stable unless you update it."
            if p == "frozen" else "A standing dependency — you trust the operator over time.")
    return p == "frozen", note


# The one source of truth for "where did this come from", shared by the pill on the row and the
# Source line in the panel. Named the way the Catalogue names it, because they are the same
# question: the pill used to say "by Third-party", which is not a place, not a publisher, and not
# any of the four answers the Catalogue's own Source filter offers.
_FROM_CLAUDE = "Claude"


def _cap_source_label(it: dict) -> str:
    """Which Catalogue source this capability came from, as the Catalogue would name it.

    Read off `catalogue_key` where there is one \u2014 that key IS the source, so the two can't drift
    \u2014 and off `origin` for records written before keys were stored. Anything left arrived through
    Claude's own MCP configuration rather than any source you can browse, and says so.
    """
    from .. import catalogue as cat
    if (it.get("source") or "").lower() == "custom":
        return cat.SOURCE_LABEL[cat.MINE]
    key = str(it.get("catalogue_key") or "")
    if key:
        return cat.source_label(key.split("/", 1)[0])
    return str(it.get("origin") or "").strip() or _FROM_CLAUDE


def _cap_source_id(it: dict) -> str:
    """The filter value for that source \u2014 the catalogue source id, or "claude"."""
    from .. import catalogue as cat
    if (it.get("source") or "").lower() == "custom":
        return cat.MINE
    key = str(it.get("catalogue_key") or "")
    return key.split("/", 1)[0] if key else "claude"


def _cap_source_pill(it: dict) -> str:
    """The 'from X' source pill shown right after the capability name."""
    from .. import catalogue as cat
    label = _cap_source_label(it)
    mine = _cap_source_id(it) == cat.MINE
    bg = ("var(--status-ok-16)" if mine
          else "var(--text-8)")
    cl = "var(--status-ok)" if mine else "var(--text-muted)"
    return (f'<span class="mc-cap-pill" style="background:{bg};color:{cl};flex:none;'
            f'padding:1px 8px">from {E(label)}</span>')


def _cap_cell(label: str, icons: str) -> str:
    """One capability-row column: a small caption above its icon(s), on a single line."""
    return (f'<span style="display:flex;flex-direction:column;gap:3px;align-items:flex-start">'
            f'<span style="font-size:8.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:700;line-height:1">{label}</span>'
            f'<span style="display:flex;gap:8px;align-items:center;min-height:16px">{icons}</span></span>')


def _cap_runs_cell(it: dict) -> str:
    runs = (it.get("runs") or "").lower()
    if runs not in _RUNS_ICON:
        return "<span></span>"
    c = _ABILITY_CLR.get(runs, "var(--text-muted)")
    return _cap_cell("Runs", f'<span title="{E(_RUNS_META[runs][0])}" style="display:flex;color:{c}">'
                             f'{_icon(_RUNS_ICON[runs], 16)}</span>')


def _cap_touch_cell(it: dict) -> str:
    chips = ""
    for s in (it.get("touch") or []):
        ic = _SCOPE_ICON.get(s)
        if ic:
            c = _ABILITY_CLR.get(s, "var(--text-muted)")
            chips += f'<span title="{E(s)}" style="display:flex;color:{c}">{_icon(ic, 16)}</span>'
    if not chips:
        return "<span></span>"
    return _cap_cell("Can touch", chips)


def _cap_badges(it: dict) -> str:
    out = ""
    runs = (it.get("runs") or "").lower()
    if runs in _RUNS_META:
        rl, rc = _RUNS_META[runs]
        out += f'<span class="mc-cap-pill" style="background:color-mix(in srgb,{rc} 16%,transparent);color:{rc}">{E(rl)}</span>'
    # Riskiest first, so the leading icon is the one that set the card's stripe. Sorted here
    # rather than trusted from the file: the order a capability happens to list its abilities
    # in is not a statement about them.
    touch = sorted((str(x).lower() for x in (it.get("touch") or [])),
                   key=lambda s: _ABILITY_RANK.index(s) if s in _ABILITY_RANK else 99)
    if touch:
        for s in touch:
            c = _SCOPE_CLR.get(s, "var(--text-muted)")
            out += f'<span class="mc-cap-scope" style="background:color-mix(in srgb,{c} 14%,transparent);color:{c}">{E(s)}</span>'
    elif runs:
        out += ('<span class="mc-cap-scope" style="background:var(--text-8);'
                'color:var(--text-muted)">no local access</span>')
    return out


def _cap_has_update(it: dict) -> bool:
    v = str(it.get("version") or "").strip()
    l = str(it.get("latest") or "").strip()
    return bool(l and l != v)


def _cap_advanced(it: dict, kind: str, manage) -> str:
    """A collapsible Advanced section (an expansion inside the expansion): granular per-capability
    settings. For now, the permission stance ARMADA passes to agents for this capability."""
    if not manage:
        return ""
    iid = E(it.get("id", ""))
    perm = (it.get("permission") or "allow").lower()
    fs = ("padding:5px 8px;border:1px solid var(--color-divider);border-radius:var(--r);"
          "background:var(--color-bg);color:var(--color-text);font:inherit;font-size:12px")
    opts = ("".join(f'<option value="{v}" {"selected" if v==perm else ""}>{lab}</option>'
                    for v, lab in (("allow", "Always allow"), ("ask", "Ask the owner first"))))
    return (f'<details class="mc-cap-adv" onclick="event.stopPropagation()">'
            f'<summary>{_icon("chevron-right",12)}Advanced</summary>'
            f'<div class="mc-cap-advbody">'
            f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            f'<span style="font-size:11.5px;color:var(--text-muted)">When agents may use this</span>'
            f'<select onchange="mcCapPerm(this,\'{manage}\',\'{kind}\',\'{iid}\')" style="{fs}">{opts}</select></div>'
            f'<div style="font-size:10.5px;color:var(--text-muted);margin-top:6px;line-height:1.4">'
            f'Guides the agents (via their context) for this whole capability. Per-tool controls and hard '
            f'enforcement land with the engine-permission work.</div></div></details>')


def _cap_agents(realm, realm_root, it: dict) -> tuple:
    """(coordinators, granted) — who can use this capability.

    Coordinators hold everything by virtue of the role, so they're derived rather than looked up;
    the granted list is the explicit mapping. Two lists, not one, because the UI has to show them
    differently: one is pinned, the other can be taken away.
    """
    from .. import capabilities as _caps
    cid = it.get("id") or it.get("name") or ""
    coords = [a for a in realm.agents if a.is_coordinator]
    granted = []
    if _caps.realm_enabled(it):
        for a in realm.members:            # members excludes the coordinator
            try:
                if _caps.may_use(realm_root, a.id, cid):
                    granted.append(a)
            except Exception:  # noqa — one unreadable agent shouldn't blank the column
                swallowed(log, '_cap_agents: failed; skipping this one')
                continue
    return coords, granted


def _cap_availto_label(realm, coords, granted) -> str:
    """The collapsed-row summary: 'Marcus + 4 agents', or '4 agents' where there's no coordinator."""
    n = len(granted)
    if coords:
        who = ", ".join(a.display for a in coords)
        return f"{who} + {n} agent{'s' if n != 1 else ''}" if n else who
    if not n:
        return "No agents"
    return f"{n} agent{'s' if n != 1 else ''}"


def _cap_availto_cell(realm, realm_root, it: dict) -> str:
    coords, granted = _cap_agents(realm, realm_root, it)
    label = _cap_availto_label(realm, coords, granted)
    muted = "var(--text-faint)"
    col = muted if (not coords and not granted) else "var(--text-strong)"
    return (f'<span style="min-width:0;display:flex;flex-direction:column;gap:2px">'
            f'<span style="font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;color:{muted}">Available to</span>'
            f'<span style="font-size:11.5px;color:{col};overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap">{E(label)}</span></span>')


def _cap_availto_chips(realm, realm_root, it: dict, kind: str) -> str:
    """The expanded 'Available to' row — the same chip language as goal owners, deliberately: it is
    the same idea (who is attached to this thing), and a second visual vocabulary for it would make
    two familiar screens feel unrelated."""
    coords, granted = _cap_agents(realm, realm_root, it)
    cid = E(str(it.get("id") or it.get("name") or ""))
    base = ("display:inline-flex;align-items:center;gap:5px;font-size:11.5px;"
            "padding:3px 4px 3px 3px;border-radius:999px;color:var(--color-text);")
    chip = (base + "background:var(--accent-13);"
                   "border:1px solid var(--accent-38)")
    pinned = (base + "background:var(--text-6);"
                     "border:1px solid var(--color-divider);"
                     "color:var(--text-62)")
    out = ""
    for c in coords:
        out += (f'<span title="{E(realm.theme_coordinator)} — can use every capability" '
                f'style="{pinned};padding-right:9px">{_portrait(realm_root, c, 18)}{E(c.display)}'
                f'<span style="display:inline-flex;color:var(--text-38)">'
                f'{_icon("pin",11)}</span></span>')
    for a in granted:
        out += (f'<span style="{chip}">{_portrait(realm_root, a, 18)}{E(a.display)}'
                f'<span onclick="mcCapRemoveAgent(event,\'{cid}\',{_J(a.id)})" title="Remove access" '
                f'style="cursor:pointer;display:inline-flex;padding:1px;border-radius:50%;'
                f'color:var(--text-faint)">{_icon("x",11)}</span></span>')
    if not granted:
        out += ('<span style="font-size:11px;color:var(--text-42)">'
                '— drag an agent here to give them access</span>')
    return out


def _cap_prov(it: dict, kind: str, manage=None, realm=None, realm_root=None) -> str:
    """The expandable provenance panel: where from (+ link), persistence, installs, declared-vs-observed,
    a skill-contents link, and an Advanced sub-section."""
    tier, why = _cap_tier_why(it)
    tcol, tlab = _TIER_META[tier]
    url = it.get("url") or ""
    custom = (it.get("source") or "").lower() == "custom"
    origin = _cap_source_label(it)
    # The label alone is terse where it is a fallback rather than a catalogue source, so the row
    # keeps the sentence the pill has no room for.
    if custom:
        origin += " — defined in this realm"
    elif origin == _FROM_CLAUDE:
        origin += " — added and authorised there, not from a source you can browse"
    link = (f' · <a href="{E(url)}" target="_blank" rel="noopener" style="color:var(--color-accent-2);text-decoration:none">View source ↗</a>'
            if url else "")
    frozen, pnote = _cap_persist(it, kind)
    pchip = (f'<span class="mc-cap-frozen">frozen</span>' if frozen else '<span class="mc-cap-living">living</span>')
    # The reason sits beside the badge. A tier is a verdict, and a verdict nobody can check is
    # just a colour — this is what makes "Caution" answerable rather than something to click past.
    rows = (f'<div class="k">Trust level</div><div><span class="mc-cap-pill" '
            f'style="background:color-mix(in srgb,{tcol} 16%,transparent);color:{tcol}">{tlab}</span>'
            f'<span style="margin-left:8px;color:var(--text-muted)">{E(why)}</span></div>'
            f'<div class="k">Source</div><div>{E(origin)}{link}</div>'
            # This page is headed "who made it", and the publisher used to be the pill on the row.
            # The pill now answers "where from", which is a different question — so the publisher
            # gets a line of its own rather than quietly disappearing.
            + (f'<div class="k">Published by</div><div>{E(str(it.get("made_by")))}</div>'
               if it.get("made_by") else "")
            + f'<div class="k">Persistence</div><div>{pchip} &nbsp;{E(pnote)}</div>')
    if realm is not None and realm_root is not None:
        rows += (f'<div class="k">Available to</div>'
                 f'<div class="mc-cap-availto" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
                 f'{_cap_availto_chips(realm, realm_root, it, kind)}</div>')
    ver = str(it.get("version") or "").strip()
    upd = _cap_has_update(it)
    if ver or upd:
        vtxt = (f'installed <b>{E(ver or "?")}</b>' + (f' · latest <b>{E(str(it.get("latest")))}</b>' if upd else " · up to date"))
        rows += f'<div class="k">Version</div><div>{vtxt}</div>'
    if upd and manage:
        info = it.get("update_info") or ""
        btn = (f'<button class="mc-cap-updbtn" onclick="mcCapUpdate(this,\'{manage}\',\'{kind}\',{_J(it.get("id",""))})">'
               f'{_icon("download",13)}Update to {E(str(it.get("latest")))}</button>')
        rows += (f'<div class="k">Update</div><div>{_md_inline(E(info)) if info else ""}'
                 f'<div>{btn}</div></div>')
    if kind == "skills":
        sid = E(it.get("id", ""))
        rows += (f'<div class="k">Contents</div>'
                 f'<div style="display:flex;align-items:center;gap:14px">'
                 f'<a class="mc-cap-ico" '
                 f'onclick="mcSkillView(\'{sid}\',{_J(it.get("name") or it.get("id",""))})">'
                 f'{_icon("file-view",15)}View contents</a>'
                 f'<a class="mc-cap-ico" onclick="mcSkillReveal(event,\'{sid}\',\'\')">'
                 f'{_icon("go-to-file",14)}Go to file</a></div>')
    if it.get("installs"):
        rows += f'<div class="k">Installs</div><div>{E(it.get("installs"))}</div>'
    declared = it.get("declared") or it.get("description") or ""
    observed = it.get("observed") or ""
    warn = it.get("warn") or ""
    cmp_block = ""
    if declared or observed:
        obs_html = (_md_inline(E(observed)) if observed
                    else '<span style="color:var(--text-muted)">Not scanned yet.</span>')
        if warn:
            head_icon = (f' <span title="Flagged" style="display:inline-flex;color:var(--status-bad)">'
                         f'{_icon("warning-tri", 12)}</span>')
            obs_html += (f'<div style="margin-top:5px;display:flex;align-items:center;gap:4px;color:var(--status-bad);font-weight:600;font-size:11px">'
                         f'<span style="display:flex;flex:none">{_icon("warning-tri", 13)}</span>{E(warn)}</div>')
        elif observed:
            head_icon = f' <span title="Nothing unusual detected" style="display:inline-flex;color:var(--status-ok)">{_icon("circle-check",12)}</span>'
        else:
            head_icon = ''
        cmp_block = (f'<div class="mc-cap-cmp"><div class="declared"><div class="h">From the developer</div>{_md_inline(E(declared))}</div>'
                     f'<div class="observed"><div class="h" style="display:flex;align-items:center;gap:4px">What we found in the content{head_icon}</div>{obs_html}</div></div>')
    return f'<div class="mc-cap-prov"><div class="g">{rows}</div>{cmp_block}{_cap_advanced(it, kind, manage)}</div>'


def _cap_card(it: dict, inherited: bool = False, manage=None, kind: str = "",
              realm=None, realm_root=None) -> str:
    ok = (it.get("status") or "connected").lower() == "connected"
    # always the type icon (skill/plugin/connector/extension) — no per-item custom icons
    ic = {"connectors": "cap-connector", "extensions": "puzzle",
          "skills": "cap-skill", "plugins": "cap-plugin"}.get(kind, "plug")
    tier = _cap_tier(it)
    tcol, tlab = _TIER_META[tier]
    name = E(it.get("name") or it.get("id", ""))
    inh = _mini_pill("inherited", "plain") if inherited else ""
    # data-source is what the Source filter matches, and it is the same value the pill displays —
    # a filter whose values you cannot see on the cards is a filter you have to guess at.
    src_grp = _cap_source_id(it)
    # data-agents drives the "Available to" filter: every agent id that can use this, coordinators
    # included, so filtering by the PM shows the whole catalogue rather than an empty page.
    avail_ids = ""
    if realm is not None and realm_root is not None:
        _co, _gr = _cap_agents(realm, realm_root, it)
        avail_ids = " ".join(a.id for a in (_co + _gr))
    data = (f'data-owner="{E(str(manage or ""))}" data-source="{E(src_grp)}" data-tier="{tier}" '
            f'data-runs="{E((it.get("runs") or "").lower())}" data-kind="{E(kind)}" '
            f'data-cap="{E(str(it.get("id") or it.get("name") or ""))}" data-agents="{E(avail_ids)}"')
    # A capability you just added has no connection state worth reporting yet — it has not been
    # installed or signed in to. "Planned", in red, read as something having gone wrong.
    is_new = _cap_is_new(it, realm, realm_root, kind)
    conn_info = _cap_new_badge() if is_new else _cap_conn_info(it, kind, ok)
    enabled = it.get("enabled", True)
    off_cls = "" if enabled else " mc-cap-off"
    ed = dl = toggle = ""
    if manage:
        iid = E(it.get("id", "")); nm = E(it.get("name") or it.get("id", ""))
        dsc = E(it.get("description", "")); stt = E(it.get("status") or "connected")
        custom = (it.get("source") or "").lower() == "custom"
        toggle = (f'<label class="mc-toggle" title="{"Enabled — click to disable" if enabled else "Disabled — click to enable"}" '
                  f'onclick="event.stopPropagation()">'
                  f'<input type="checkbox" {"checked" if enabled else ""} '
                  f'onchange="mcCapToggle(this,\'{manage}\',\'{kind}\',\'{iid}\')"><span class="mc-toggle-sl"></span></label>')
        ed = (f'<a onclick="event.stopPropagation();mcCapEdit(this)" data-scope="{manage}" data-kind="{kind}" data-id="{iid}" '
              f'data-name="{nm}" data-scope-text="" data-descr="{dsc}" data-status="{stt}" title="Edit" '
              f'style="cursor:pointer;display:inline-flex;padding:3px;color:var(--text-muted)">{_icon("edit",13)}</a>') if custom else ""
        dl = (f'<a onclick="event.stopPropagation();mcCapDelete(\'{manage}\',\'{kind}\',\'{iid}\')" title="Remove" '
              f'style="cursor:pointer;display:inline-flex;padding:3px;color:var(--status-bad)">{_icon("trash",13)}</a>')
    # collapsed row = a 5-column grid so every item's columns line up: type · title+by · Runs · Can-touch · actions
    upd = _cap_has_update(it)
    upd_badge = (f'<span class="mc-cap-upd" title="Update available: {E(str(it.get("latest")))}">Update</span>'
                 if upd else "")
    # The disclosure chevron leads the row, the way it does on a job. It used to sit at the far
    # right, past the toggle and the bin — so the thing that opens the row was the last thing you
    # reached, and the two lists opened from opposite ends.
    col0 = (f'<span class="mc-cap-caret" style="display:flex;align-self:center">'
            f'{_icon("chevron-right",14)}</span>')
    # …and the type icon travels with the name instead of holding a column of its own. A column put
    # 16px of gap between an icon and the thing it describes.
    col2 = (f'<span style="min-width:0;display:flex;flex-direction:column;gap:2px">'
            f'<span style="display:flex;align-items:center;gap:7px;min-width:0">'
            f'<span title="{tlab}" style="display:flex;flex:none;color:var(--text-62)">{_icon(ic,15)}</span>'
            f'<span style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{name}</span>{conn_info}{upd_badge}</span>'
            f'<span style="display:flex;align-items:center;gap:6px;margin-left:22px">{_cap_source_pill(it)}{inh}</span></span>')
    col5 = (f'<span style="display:flex;gap:7px;align-items:center;justify-self:end">{toggle}{ed}{dl}</span>')
    droppable = ""
    availto = ""
    if realm is not None and realm_root is not None:
        availto = _cap_availto_cell(realm, realm_root, it)
        cid = E(str(it.get("id") or it.get("name") or ""))
        droppable = (f' ondragover="mcCapDragOver(event)" ondragleave="mcCapDragLeave(event)" '
                     f'ondrop="mcCapDrop(event,\'{cid}\')"')
    # The tier colour bleeds ~8px in from the left border and fades out, so a card reads as the
    # same object as its swatch in the Risk legend. It's a background-IMAGE, not the `background`
    # shorthand: the shorthand would drop the card's own background-color and the row would go
    # transparent over the page.
    grad = (f'border-left-color:{tcol};'
            f'background-image:linear-gradient(to right,'
            f'color-mix(in srgb,{tcol} 14%,transparent) 0,'
            f'color-mix(in srgb,{tcol} 11%,transparent) 11px,transparent 28px)')
    # 14px for the chevron with a tight gap after it, then the name column — which absorbed the
    # type icon, so it is wider than the 300 it was.
    cols = ("14px 316px 88px 118px 150px 1fr" if availto else "14px 316px 88px 118px 1fr")
    return (f'<details class="mc-cap mc-toolrow{off_cls}" style="{grad}" {data}{droppable}>'
            f'<summary style="display:grid;grid-template-columns:{cols};'
            f'column-gap:16px;align-items:center">'
            f'{col0}{col2}{_cap_runs_cell(it)}{_cap_touch_cell(it)}{availto}{col5}'
            f'</summary>{_cap_prov(it, kind, manage, realm, realm_root)}</details>')


_tool_row = _cap_card   # back-compat alias: the row renderer is now a trust card (same signature)


_CAP_DESC = {
    "connectors": "Remote services an agent can read from or act on.",
    "extensions": "Local tools that run on this machine.",
    "skills": "Packaged know-how for a repeatable task.",
    "plugins": "Bundles of skills and connectors, installed as one.",
}


def _cap_is_new(it: dict, realm=None, realm_root=None, kind: str = "") -> bool:
    """Has this capability been added but not yet put to work?

    "New" is a state you leave by doing something, not a timer you wait out: it clears once the
    capability is switched on AND at least one agent can actually use it. Dating it instead would
    mean a capability you added a fortnight ago and never wired up stops announcing itself for no
    reason — and that one is exactly the loose end worth showing.

    The coordinator doesn't count. It can use everything in the realm by virtue of the role, so it
    is granted the moment anything is added, and counting it would clear the badge instantly on
    every realm that has one.
    """
    if not it.get("added"):
        return False                     # predates the catalogue, or was pulled in by a scan
    if it.get("enabled") is False:
        return True
    if realm is None or realm_root is None:
        return False
    try:
        from .. import capabilities as _caps
        cid = _caps.cap_key(it)
        for a in realm.members:          # members excludes the coordinator
            if cid in _caps.granted_keys(realm_root, a.id):
                return False
    except Exception:  # noqa — a badge is not worth breaking the page for
        swallowed(log, '_cap_is_new: failed; returning a fallback')
        return False
    return True


def _cap_new_badge() -> str:
    return ('<span class="mc-cap-pill" style="background:color-mix(in srgb,var(--color-accent-2) 18%,'
            'transparent);color:var(--color-accent-2);font-weight:600" '
            'title="Added but not in use yet \u2014 switch it on and give an agent access">new</span>')


def _tool_group(title: str, icon: str, realm_items, agent_items=None, manage=None, compact: bool = False,
                realm=None, realm_root=None, allow_refresh: bool = False) -> str:
    """manage: None (read-only) or a scope string ('realm' or an agent id) that owns the *own* items.
    compact: show the category by its icon only (no title/description) — used for the per-agent grid,
    where the icon + fixed order already identify each bucket."""
    rows = ""
    # Anything you just added leads its section. It is the thing you came to the page to see, and
    # it starts switched off, so it needs to be where you'd look rather than alphabetically buried
    # among things already working.
    realm_items = sorted(realm_items or [],
                         key=lambda x: (not _cap_is_new(x, realm, realm_root, title.lower()),
                                        str(x.get("name") or x.get("id") or "").lower()))
    for it in (realm_items or []):
        # realm_items are 'inherited' only when we're also showing agent_items (agent tab)
        rows += _cap_card(it, inherited=agent_items is not None,
                          manage=(manage if agent_items is None else None), kind=title.lower(),
                          realm=realm, realm_root=realm_root)
    for it in (agent_items or []):
        rows += _cap_card(it, inherited=False, manage=manage, kind=title.lower(),
                          realm=realm, realm_root=realm_root)
    if not rows:
        rows = ('<div style="font-size:12px;color:var(--text-soft);padding:8px 4px">'
                'None yet.</div>')
    is_conn = title.lower() == "connectors"
    add = ""   # per-bucket "+ Add" removed — adding is handled by a separate section-wide flow
    # Refresh pulls servers into the realm CATALOGUE, so it belongs to the realm page only. On an
    # agent's page it read as "refresh this agent's connectors" and did something else entirely.
    refresh = ""
    if is_conn and manage and allow_refresh:
        refresh = (f'<a onclick="mcConnectorRefresh(this)" title="Refresh connectors from Claude" '
                   f'style="cursor:pointer;display:inline-flex;margin-left:auto;color:var(--text-muted)">{_icon("refresh-cw",14)}</a>'
                   f'<span class="mc-connref-msg" style="font-size:11px;color:var(--text-muted);margin-left:8px"></span>')
    desc = _CAP_DESC.get(title.lower(), "")
    if compact:
        head = (f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                f'<span style="display:flex;color:var(--color-accent)" title="{E(title)}">{_icon(icon,17)}</span>{refresh}</div>')
    else:
        # title + description on the same line (keeps each one's font style)
        head = (f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px">'
                f'<span style="display:flex;color:var(--color-accent);align-self:center">{_icon(icon,17)}</span>'
                f'<span style="font-family:var(--font-heading);font-weight:600;font-size:16px">{E(title)}</span>'
                + (f'<span style="font-size:11px;color:var(--text-muted)">{E(desc)}</span>' if desc else "")
                + f'{refresh}</div>')
    # no holder box — the section header + the cards' own left-border tiers carry the structure
    return f'<div class="mc-cap-grp" style="margin-bottom:30px">{head}<div>{rows}{add}</div></div>'


def _cap_legend() -> str:
    """A compact key for the card labels — same icons the cards use, with a plain-English description."""
    def grp(title, body):
        return (f'<div style="margin-bottom:14px"><div style="font-size:9.5px;text-transform:uppercase;'
                f'letter-spacing:.07em;color:var(--text-muted);font-weight:700;margin-bottom:6px">{title}</div>{body}</div>')
    def iconline(name, key, desc):
        c = _ABILITY_CLR.get(key, "var(--text-muted)")
        if " — " in desc:
            title, rest = desc.split(" — ", 1)
            desc = f'<b>{title}</b> — {rest}'
        return (f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:7px;'
                f'font-size:11px;color:var(--text-muted);line-height:1.35">'
                f'<span style="flex:none;color:{c}">{_icon(name,19)}</span>'
                f'<span>{desc}</span></div>')
    # The three risk levels sit on one row rather than three: they're one short scale, and the
    # vertical space this frees is what lets the agent roster share the rail without scrolling.
    risk = '<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
    for t, (clr, lab) in _TIER_META.items():
        risk += (f'<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text-muted)">'
                 f'<span style="width:13px;height:13px;border-radius:3px;border-left:3px solid {clr};'
                 f'background:color-mix(in srgb,{clr} 12%,transparent);flex:none"></span>{lab}</div>')
    risk += '</div>'
    risk += ('<div style="font-size:10px;color:var(--text-muted);font-style:italic;margin-top:6px;line-height:1.35">'
             'Based on detected abilities and/or discrepancies. Not a security audit, do your own research.</div>')
    # Every group reads riskiest-first, the same way the risk scale above it does — and from the
    # same order the tier is computed from, so the legend can't disagree with the badge.
    runs = "".join(iconline(_RUNS_ICON[k], k, _RUNS_DESC[k])
                   for k in _ABILITY_RANK if k in _RUNS_ICON)
    touch = "".join(iconline(_SCOPE_ICON[k], k, _SCOPE_DESC[k])
                    for k in _ABILITY_RANK if k in _SCOPE_ICON)
    inner = grp("Risk", risk) + grp("Runs", runs) + grp("Can touch", touch)
    return (f'<div style="font-family:var(--font-heading);font-weight:600;font-size:12px;text-transform:uppercase;'
            f'letter-spacing:.06em;color:var(--text-muted);margin-bottom:10px">Legend</div>{inner}')


def _cap_roster(realm, realm_root) -> str:
    """Draggable agents, below the legend. Same component as the Goals roster — dragging a person
    onto a thing to attach them is one idea, and it should feel identical in both places."""
    # What each agent can already reach, by type. Dragging someone onto a capability is the only
    # way to grant one, and until now the roster gave no way to tell whether you had already done
    # it — you had to open every card and read the chips. Same four icons as the minister card, so
    # the count means the same thing in both places.
    from .. import capabilities as _caps
    _KINDS = (("connectors", "cap-connector"), ("extensions", "puzzle"),
              ("skills", "cap-skill"), ("plugins", "cap-plugin"))
    chips = ""
    for a in realm.members:
        try:
            grants = _caps.grants(realm_root, a.id)
        except Exception:  # noqa — a roster is not worth breaking the page for
            swallowed(log, '_cap_roster: failed; using a default')
            grants = {}
        # Each cell is the same width, so the four columns line up down the list and you can read
        # "who has the most skills" by scanning rather than by comparing. Wide enough for two
        # digits: an agent with ten connectors shouldn't push the row out of alignment.
        counts = "".join(
            f'<span class="mc-rc" data-agent="{E(a.id)}" data-kind="{k}" '
            f'title="{E(_KIND_SINGULAR[k])}s this agent can use" '
            f'style="flex:0 0 30px;display:inline-flex;align-items:center;justify-content:flex-start;'
            f'gap:3px;color:var(--text-faint)">{_icon(ic, 12)}'
            f'<b class="mc-rc-n" style="font-weight:600;font-size:10.5px;'
            f'font-variant-numeric:tabular-nums">{len(grants.get(k) or [])}</b></span>'
            for k, ic in _KINDS)
        chips += (f'<div draggable="true" ondragstart="mcCapDragStart(event,{_J(a.id)})" class="mc-rosteragent" '
                  f'style="display:flex;align-items:center;gap:8px;padding:6px 8px;border:1px solid var(--color-divider);'
                  f'border-radius:var(--r);background:var(--color-bg);cursor:grab;margin-bottom:6px;font-size:12.5px">'
                  # The grip leads the row: picking the agent up is what the row is FOR, so the
                  # handle sits where the cursor arrives rather than trailing everything else.
                  f'<span style="display:flex;flex:none;color:var(--text-35)">'
                  f'{_icon("grip-vertical",13)}</span>'
                  f'{_portrait(realm_root, a, 20)}'
                  # Fixed width, not flex: the counts sit in the same column on every row, so the
                  # four numbers read as a column you can scan rather than four that wander with
                  # the length of each name.
                  f'<span style="flex:0 0 96px;min-width:0;overflow:hidden;text-overflow:ellipsis;'
                  f'white-space:nowrap" title="{E(a.display)}">{E(a.display)}</span>'
                  f'<span style="display:flex;align-items:center;gap:7px;margin-left:auto">{counts}</span>'
                  f'</div>')
    if not chips:
        chips = ('<div style="font-size:11.5px;color:var(--text-muted)">No agents yet.</div>')
    note = ""
    if realm.coordinator:
        note = (f'<div style="font-size:11px;color:var(--text-faint);'
                f'margin-top:8px;padding-top:8px;border-top:1px solid var(--color-divider)">'
                f'{E(realm.theme_coordinator)} ({E(realm.coordinator.display)}) can use every '
                f'capability in the realm.</div>')
    else:
        note = ('<div style="font-size:11px;color:var(--text-faint);'
                'margin-top:8px;padding-top:8px;border-top:1px solid var(--color-divider)">'
                'This realm has no coordinator, so no agent has access to everything.</div>')
    return (f'<div class="mc-frame" style="padding:12px;border-radius:var(--r);margin-top:18px">'
            f'<div style="font-family:var(--font-heading);font-weight:600;font-size:13px">Agents</div>'
            f'<div style="font-size:11px;color:var(--text-muted);margin:2px 0 10px">'
            f'Drag an agent onto a capability to let them use it</div>{chips}{note}</div>')


def _sys_card(it: dict) -> str:
    """One system skill: same visual language as a capability card, but locked — no toggle, no
    delete, no edit. The lock is the point, so it's stated on the card and explained once above."""
    desc = E(it.get("description") or "")
    lock = (f'<span title="Locked — part of ARMADA itself" style="display:inline-flex;align-items:center;'
            f'gap:4px;color:var(--text-muted);font-size:11px">{_icon("lock",12)}Locked</span>')
    ver = (f'<span style="font-size:11px;color:var(--text-muted)">v{E(it.get("version") or "")}</span>')
    view = (f'<span style="display:inline-flex;align-items:center;gap:14px">'
            f'<a class="mc-cap-ico" onclick="mcSkillView({_J(it["id"])},\'system\')">'
            f'{_icon("file-view",20)}View contents</a>'
            f'<a class="mc-cap-ico" onclick="mcSkillReveal(event,{_J(it["id"])},\'system\')">'
            f'{_icon("go-to-file",19)}Go to file</a></span>')
    # The type icon, the same one the User tab uses for that kind. A shield on every row said
    # "system" — which the tab you are already on says — while the one fact the row couldn't tell
    # you is whether it's a skill, a connector or something else.
    kind = (it.get("kind") or "skills").lower()
    ic = {"connectors": "cap-connector", "extensions": "puzzle",
          "skills": "cap-skill", "plugins": "cap-plugin"}.get(kind, "cap-skill")
    return (f'<div class="mc-cap mc-cap-sys" data-kind="system" style="border-left-color:var(--status-ok)">'
            f'<div style="display:grid;grid-template-columns:18px 1fr auto;gap:10px;align-items:start;padding:10px 12px">'
            f'<span title="{E(_KIND_SINGULAR.get(kind, "Skill"))}" style="color:var(--status-ok);'
            f'display:flex;padding-top:1px">{_icon(ic,16)}</span>'
            f'<div style="min-width:0">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
            f'<span style="font-weight:600">{E(it.get("name") or it["id"])}</span>{lock}{ver}</div>'
            f'<div style="font-size:12.5px;color:var(--text-muted);margin-top:3px">{desc}</div></div>'
            f'<div style="white-space:nowrap">{view}</div></div></div>')


def _system_panel() -> str:
    """The System tab: what ARMADA runs on your behalf, and why you can't switch it off."""
    items = sysskills.list_system_skills()
    if not items:
        return ('<div style="font-size:13px;color:var(--text-muted)">No system skills are bundled '
                'with this build.</div>')
    cards = "".join(_sys_card(it) for it in items)
    note = ('<div style="font-size:13px;color:var(--text-muted);line-height:1.6;max-width:1100px;margin:0 0 14px">'
            '<div>ARMADA uses these to do its own work — like checking the capabilities on the User '
            'tab are filed correctly and can only touch what they claim.</div>'
            '<div>System capabilities can\'t be edited or removed: they ship inside the app and '
            'update with it.</div></div>')
    return note + cards



# The Capabilities page: User tab (above), System tab, and the Catalogue tab (catalogue.py,
# Phase 2, 2.4) stitched into one page with client-side tab switching.
def _realm_skills(realm, realm_root) -> str:
    tk = _realm_toolkit(realm_root)
    _hd = 'font-family:var(--font-heading);font-weight:600;font-size:16px;margin:0 0 10px'
    _ctx = {"realm": realm, "realm_root": realm_root, "allow_refresh": True}
    realm_grps = (f'{_tool_group("Connectors", "cap-connector", tk["connectors"], manage="realm", **_ctx)}'
                  f'{_tool_group("Extensions", "puzzle", tk["extensions"], manage="realm", **_ctx)}'
                  f'{_tool_group("Skills", "cap-skill", tk["skills"], manage="realm", **_ctx)}'
                  f'{_tool_group("Plugins", "cap-plugin", tk["plugins"], manage="realm", **_ctx)}')
    realm_region = f'<div class="mc-cap-region"><div style="{_hd}">Realm-wide</div>{realm_grps}</div>'
    # "Available to" rather than "All owners": a capability has no owner now, it has a list of
    # agents allowed to use it, and the filter should ask the question the page answers. Every
    # agent is listed, not only those with their own entries — the useful query is "what can
    # Warren reach", which for most agents is a shorter list than the catalogue.
    avail_opts = [(a.id, a.display) for a in realm.agents]
    # Source options come from the capabilities actually here, not from a fixed list: this filter
    # used to offer "You / Anthropic / Third-party (company) / Open-source", which described who
    # MADE a thing rather than where it came from, and "Third-party" is not an answer to either
    # question. Built from the same helper the pills use, so the menu can only ever offer values
    # that appear on a card.
    _seen = {}
    for _k in ("connectors", "extensions", "skills", "plugins"):
        for _it in (tk.get(_k) or []):
            _seen.setdefault(_cap_source_id(_it), _cap_source_label(_it))
    src_opts = sorted(_seen.items(), key=lambda kv: kv[1].lower())
    # An agent's toolkit now holds GRANTS — pointers at realm capabilities — so listing it verbatim
    # printed the same capability once per agent that had been given it, under a heading claiming it
    # was theirs alone. "Available to" on the realm card is where a grant belongs. What survives here
    # is the genuinely agent-only case: something in an agent's toolkit with no realm entry behind
    # it, which shouldn't happen under the new model and is worth seeing if it does.
    from .. import capabilities as _caps
    _realm_keys = {_caps.cap_key(c) for _k, c in _caps.catalogue_flat(realm_root)}
    per = ""
    for a in realm.agents:
        atk = _agent_toolkit(realm_root, a.id)
        own = {k: [it for it in (atk[k] or []) if _caps.cap_key(it) not in _realm_keys]
               for k in ("connectors", "extensions", "skills", "plugins")}
        if not any(own.values()):
            continue
        sub = ""
        for _k in ("connectors", "extensions", "skills", "plugins"):
            for _it in own[_k]:
                sub += _cap_card(_it, manage=a.id, kind=_k)
        per += (f'<div class="mc-cap-agent" style="margin-bottom:14px">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
                f'<span style="font-family:var(--font-heading);font-weight:600;font-size:15px">{E(a.display)}</span>'
                f'<span style="font-size:11px;color:var(--text-muted)">{E(a.theme_role)}</span></div>{sub}</div>')
    per_region = (f'<div class="mc-cap-region" style="border-top:1px solid var(--color-divider);padding-top:16px;margin-top:6px">'
                  f'<div style="{_hd}">Agent-specific</div>'
                  f'<div style="font-size:11.5px;color:var(--text-muted);margin:-4px 0 10px">'
                  f'In an agent\'s toolkit but not in the realm catalogue. Normally empty — add it '
                  f'to the realm so you can see and manage it in one place.</div>{per}</div>') if per else ""
    # filter bar: search + owner (incl. realm-wide) + source + risk level. Same controls as the
    # Catalogue's and the Jobs page's — one filter bar in the app, not one per tab.
    faint = "var(--text-faint)"
    search_box = (f'<div style="position:relative;flex:0 0 172px">'
                  f'<span style="position:absolute;left:9px;top:50%;transform:translateY(-50%);display:flex;'
                  f'color:{faint}">{_icon("search",14)}</span>'
                  f'<input id="cap-search" oninput="mcCapFilter()" placeholder="Search…" '
                  f'style="{_FIELD};padding-left:30px;padding-right:26px">'
                  f'<span id="cap-search-x" onclick="mcCapSearchClear()" title="Clear" style="display:none;position:absolute;'
                  f'right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:{faint}">{_icon("x",14)}</span></div>')

    def capsel(sid, label, opts, width=""):
        rows = [("", label)] + list(opts)
        return _filter_dropdown(sid, label, [(v, l, "") for v, l in rows],
                                width=width, onpick="mcCapFilter")

    filters = (f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 18px">{search_box}'
               f'<span style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;'
               f'color:{faint}">Filter</span>'
               # No fixed widths, and short default labels. This bar shares its row with the
               # legend column, which leaves it about 700px — five controls sized for their
               # longest option wrapped onto a second line. Each is now as wide as the words it
               # has to hold, and the menus below them are unchanged.
               + capsel("cap-f-type", "All types",
                        [("connectors", "Connectors"), ("extensions", "Extensions"),
                         ("skills", "Skills"), ("plugins", "Plugins")])
               + capsel("cap-f-avail", "Any agent", avail_opts)
               + capsel("cap-f-source", "All sources", src_opts)
               # Built from _TIER_META, not repeated here: the legend and this dropdown are two
               # views of one scale, and a second hand-written copy is how they came to disagree
               # about which end to start from.
               + capsel("cap-f-tier", "Any risk",
                        [(k, lab) for k, (_c, lab) in _TIER_META.items()])
               + f'<button id="cap-f-clear" onclick="mcCapFilterClear()" style="display:none;align-items:center;'
               f'gap:4px;border:0;background:transparent;cursor:pointer;font-size:12px;'
               f'color:var(--color-accent);padding:6px 4px">{_icon("x",12)}Clear</button>'
               + f'</div>')
    filter_js = _CAPFILTER_JS
    scan_btn = (f'<button class="btn btn-secondary" style="font-size:12px;padding:5px 11px;display:inline-flex;'
                f'align-items:center;gap:5px;margin-right:8px" onclick="mcCapScan(this)">'
                # "Check for updates" read as though it might update ARMADA itself; this checks the
                # installed capabilities for newer releases and nothing else.
                f'{_icon("refresh-cw",13)}Check for version updates</button>')
    # Three tabs: User (yours), System (ARMADA's own, locked) and Catalogue (what you could add).
    # The header actions and the legend belong to the User tab only — neither applies to bundled
    # system skills, and nothing in the Catalogue has a risk level yet to need a legend for.
    tabs = (f'<div class="mc-captabs" style="display:flex;gap:2px;border-bottom:1px solid var(--color-divider);'
            f'margin:10px 0 16px">'
            f'<a id="cap-tab-user" class="mc-captab" onclick="mcCapTab(\'user\')">User</a>'
            f'<a id="cap-tab-system" class="mc-captab" onclick="mcCapTab(\'system\')">System</a>'
            f'<a id="cap-tab-catalogue" class="mc-captab" onclick="mcCapTab(\'catalogue\')">Add a capability</a></div>')
    user_pane = (f'<div id="cap-pane-user">'
                 f'<div style="display:flex;gap:32px;align-items:stretch">'
                 f'<div style="flex:1;min-width:0;max-width:900px">{filters}{realm_region}{per_region}</div>'
                 f'<div style="flex:none;width:390px">'
                 f'<div style="position:sticky;top:16px">{_cap_legend()}'
                 f'{_cap_roster(realm, realm_root)}</div></div></div></div>')
    sys_pane = f'<div id="cap-pane-system" style="display:none">{_system_panel()}</div>'
    # Local, not module-level: catalogue.py imports _KIND_SINGULAR/_cap_iconcluster/_cap_tier_why
    # back from this module, so a top-of-file import here would be a cycle (Phase 2, 2.4).
    from .catalogue import _catalogue_pane, _CAT_JS
    cat_pane = _catalogue_pane(realm, realm_root)
    # Re-opening a <details> doesn't re-run its CSS open animation: the panel element is never
    # re-created, so the animation only ever played on first expand. Restart it by hand on each
    # open (clear → force reflow → restore). `toggle` doesn't bubble, hence capture.
    anim_js = _CAPANIM_JS
    tab_js = _CAPTAB_JS
    # Drag an agent from the roster onto a capability to grant it. Dropping is a write, so the row
    # is re-rendered from the server's answer rather than optimistically: a chip that appears and
    # then turns out not to have been saved is worse than a half-second wait.
    drag_js = _CAPDRAG_JS
    return (f'<div style="padding:18px 24px 24px">'
            f'<div style="display:flex;align-items:flex-start"><div style="flex:1">{_page_title("Capabilities", "who made it · what it can touch · your risk")}</div>'
            f'<span id="cap-actions">{scan_btn}{_cap_manage_btn()}</span></div>'
            f'{tabs}{user_pane}{sys_pane}{cat_pane}'
            f'{_CAP_HELP}{_CAP_EDIT_MODAL}{_CONNECTOR_MODAL}</div>'
            # fdrop.js FIRST: both filter bars on this page are the app's dropdown, and the page
            # was rendering them without ever loading the script that makes them pick. Clicking an
            # option called an undefined function, so the Catalogue's filters did nothing at all.
            f'{_FDROP_JS}{filter_js}{_CAT_JS}{tab_js}{anim_js}{drag_js}')
