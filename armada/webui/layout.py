"""Page chrome / layout (carved from _core.py in Phase 3).

The title bar, top nav (realm switcher + tabs + user sections), page shell (<head> + body
frame) and KPI header, plus per-app visual-theme injection. Imports lower layers + assets
(never _core); _core re-imports these so page renderers keep calling _page_shell()/_nav().
"""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import brand, vtheme, appconfig
from ..icons import ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR
from ._base import (E, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _chip, _poss)
from ..assets import (CSS_LINKS as _CSS_LINKS, RUN_JS as _RUN_JS, FORM_JS as _FORM_JS,
    DOTPOLL_JS as _DOTPOLL_JS, SWITCHER_JS as _SWITCHER_JS, PENDING_BADGE_JS as _PENDING_BADGE_JS,
    SECTION_EDIT_JS as _SECTION_EDIT_JS, AUTHBAR_JS as _AUTHBAR_JS, SCHEDBAR_JS as _SCHEDBAR_JS, UPDBAR_JS as _UPDBAR_JS, SUPPORT_JS as _SUPPORT_JS,
    NOTIFBELL_JS as _NOTIFBELL_JS, CONFIRM_JS as _CONFIRM_JS, NAVKEYS_JS as _NAVKEYS_JS,
    MODEBOOT_JS as _MODEBOOT_JS, NEWREALM_JS as _NEWREALM_JS)  # Phase 2, 2.1
import logging
from ..util import swallowed
log = logging.getLogger(__name__)
LOGO = brand.LOGO
MARK = brand.MARK


APPEARANCE_MODES = ("light", "dark", "system")
APPEARANCE_DEFAULT = "light"


def appearance_mode() -> str:
    """light · dark · system — per machine, alongside the theme."""
    v = str(appconfig.get("appearance", APPEARANCE_DEFAULT) or "").strip().lower()
    return v if v in APPEARANCE_MODES else APPEARANCE_DEFAULT


def dark_default() -> bool:
    """Should the server render dark? 'system' renders light and lets the browser correct it —
    only the browser knows what the OS is set to."""
    return appearance_mode() == "dark"


def _mode_boot() -> str:
    """Apply the OS colour scheme when the mode is 'system'.

    The server cannot know what the OS is set to, and asking the browser and reloading would mean
    a visible flash and a redirect on every page. This goes in the <head>, so it runs before the
    body paints, and it listens for changes — switch the OS to dark mid-session and the app
    follows without a reload.

    It sets the class on <html> as well as <body>: at the time this runs <body> does not exist yet,
    and the stylesheet keys off `.armada-dark` rather than `body.armada-dark`, so either works."""
    if appearance_mode() != "system":
        return ""
    return _MODEBOOT_JS


def _theme_style() -> str:
    from .. import fonts
    return vtheme.theme_style(appconfig.get("theme", vtheme.DEFAULT)) + fonts.style() + _mode_boot()


def _titlebar(realm) -> str:
    # The OS window title (and the browser tab title) already show "ARMADA — <realm>",
    # so the in-app title strip is redundant — dropped to avoid a duplicated header.
    return ""


def _nav(realm, active: str = "Overview", sec_edit: bool = False) -> str:
    tabs = [("Overview", "/"), (realm.theme_agent + "s", "/ministers"), ("Goals", "/goals"), ("Jobs", "/jobs"),
            ("Inbox", "/inbox"), ("Memory", "/memory"), ("Capabilities", "/skills"),
            ("Artefacts", "/artefacts")]
    tab_html = ""
    npend = 0
    # Waiting inbox tasks get a badge too — work agents have handed each other is easy to miss
    # otherwise, since nobody asked for it.
    try:
        from .. import inbox as _inbox_mod
        nwait = len(_inbox_mod.all_messages(realm.root, recent_hours=0)["waiting"])
    except Exception:  # noqa — a malformed message must never break the nav
        swallowed(log, '_nav: failed; using a default')
        nwait = 0
    try:
        from .. import jobs as _jobs_mod
        npend = _jobs_mod.count_pending(realm.root)
    except Exception:  # noqa — a bad proposal file must never break the nav
        swallowed(log, '_nav: failed; using a default')
        npend = 0
    for label, href in tabs:
        cur = 'aria-current="page"' if label == active else ""
        # the Jobs tab carries a live pending-proposal badge, always present (hidden at 0) so a
        # background poller (mcPendingRefresh) can update it without a page navigation
        badge = ""
        if label == "Jobs":
            disp = "inline-block" if npend else "none"
            badge = (f'<span id="mc-jobsbadge" class="mc-count" title="job proposals awaiting approval" '
                     f'style="display:{disp}">{npend}</span>')
        if label == "Inbox" and nwait:
            badge = (f'<span class="mc-count is-warn" title="tasks waiting to be picked up">{nwait}</span>')
        tab_html += f'<a class="mc-tab" href="{href}" {cur}>{E(label)}{badge}</a>'
    sections = getattr(realm, "sections", None) or []
    usr = ""
    greybg = "background:var(--text-7)"
    active_idx = None
    for i, s in enumerate(sections):
        nm = s.get("name") if isinstance(s, dict) else str(s)
        cur = 'aria-current="page"' if nm == active else ""
        if nm == active:
            active_idx = i
        usr += (f'<span class="mc-tab mc-tab-user" data-i="{i}" {cur} style="padding-inline:6px;gap:4px">'
                f'<span class="mc-secgrip" title="Drag to reorder" style="display:none;cursor:grab;color:var(--text-muted)">{_icon("grip-vertical",13)}</span>'
                f'<span class="mc-secname" onclick="mcSecClick(event,this)" ondblclick="mcSecRename(event,this)" '
                f'style="cursor:pointer">{E(nm)}</span>'
                f'<span class="mc-secx" title="Remove section" style="display:none;cursor:pointer;color:var(--text-muted)" '
                f'onclick="mcSecDelete(event,this)">{_icon("x",13)}</span></span>')
    # square icon-button (self-aligns so it doesn't stretch to nav height)
    sqbtn = ("cursor:pointer;width:28px;height:28px;align-self:center;display:inline-flex;align-items:center;"
             "justify-content:center;padding:0;border-radius:var(--r);" + greybg)
    # Both glyphs are rendered server-side and swapped by the toggle: the icon that gets you OUT of
    # edit mode should say so, and an unchanged pencil left you guessing whether the click landed.
    edit = (f'<a class="mc-tab" id="mc-seceditbtn" onclick="mcSectionEdit(this)" title="Edit sections" '
            f'style="{sqbtn};color:var(--text-muted)">'
            f'<span class="mc-sec-on" style="display:inline-flex">{_icon("pencil",14)}</span>'
            f'<span class="mc-sec-off" style="display:none">{_icon("edit-off",14)}</span></a>'
            f'<span id="mc-sechint" style="display:none;align-self:center;font-family:var(--font-body);'
            f'font-size:12px;font-style:italic;color:var(--text-muted);white-space:nowrap">Double click to edit titles</span>')
    edit = (edit + _SECTION_EDIT_JS) if sections else ""
    usr_sep = ('<i style="width:1px;background:var(--color-divider);margin:10px 0"></i>' + usr + edit) if sections else ""
    switcher = (f'<details class="mc-realmsw" style="position:relative">'
                f'<summary style="display:flex;align-items:center;gap:8px;padding:6px 11px;border:0;'
                f'background:var(--text-7);'
                f'cursor:pointer;margin:6px 0;border-radius:var(--r)"><span style="display:flex;color:color-mix(in srgb,var(--color-text) 75%,transparent)">{_realm_icon(realm, 15)}</span>'
                f'<span style="font-family:var(--font-heading);font-weight:600;font-size:15px">{E(realm.name)}</span>{CHEVR}</summary>'
                f'<div id="mc-realmlist" style="position:absolute;top:100%;left:0;z-index:50;min-width:210px;background:var(--color-bg);'
                f'border:1px solid var(--color-divider);border-radius:var(--r);box-shadow:var(--shadow-md);padding:6px;margin-top:4px">'
                f'<div style="font-size:11px;color:var(--text-muted);padding:4px 8px">loading…</div></div></details>')
    return (f'<div style="display:flex;align-items:center;gap:22px;padding:0 24px;'
            f'border-bottom:1px solid var(--color-divider);flex:none">'
            f'<a href="/" style="text-decoration:none;display:flex;align-items:center;gap:7px">{LOGO}{brand.BETA_PILL}</a>{switcher}'
            f'<div style="display:flex;gap:18px;align-items:stretch;align-self:stretch">{tab_html}{usr_sep}</div>'
            f'<div style="margin-left:auto;display:flex;align-items:center;gap:16px">'
            f'<span style="display:inline-flex;align-items:center;gap:7px;font-size:12px;'
            f'color:var(--text-strong)">'
            f'<i style="width:8px;height:8px;flex:none;border-radius:50%;background:var(--status-ok)"></i>{E(realm.engine)}</span>'
            # Bell opens the notification centre in place. It used to navigate to /approvals, which
            # meant losing your page to check whether anything had happened.
            f'<span id="mc-bellwrap" style="position:relative;display:flex">'
            f'<a id="mc-bell" title="Notifications" onclick="mcBellToggle(event)" '
            f'style="text-decoration:none;display:flex;align-items:center;cursor:pointer;'
            f'color:var(--text-strong)">{_icon("bell")}</a>'
            # One unread signal, not two. A numeric badge and a dot both pinned to the same corner
            # overlapped into a blob; the dot says "there's something new" and the exact count is
            # in the panel header, which is where you look when you actually care about it.
            f'<span id="mc-belldot" style="display:none;position:absolute;top:-2px;right:-3px;'
            f'width:8px;height:8px;border-radius:50%;background:var(--status-bad);'
            f'box-shadow:0 0 0 2px var(--color-surface);pointer-events:none"></span>'
            f'<div id="mc-bellpanel" style="display:none"></div></span>'
            f'<a href="/docs" title="Documentation" style="text-decoration:none;display:flex;align-items:center;color:var(--text-strong)">{_icon("documentation")}</a>'
            # Report an issue (5.6): beside the gear, on every page — the beta's one feedback path.
            f'<button type="button" class="mc-iconbtn mc-support-btn" title="Report an issue" aria-label="Report an issue" '
            f'onclick="mcSupportOpen()">{_icon("support-ai", 19)}</button>'
            f'<a href="/settings" title="Settings" style="text-decoration:none;display:flex;align-items:center;color:var(--text-strong)">{_icon("settings")}</a></div></div>'
            # Sign-in banner: sits under the nav on EVERY page, because a lapsed Claude session
            # stops every agent run — not just whatever page you happen to be looking at.
            f'<div id="mc-authbar"></div>'
            # Scheduler banner (5.5): same reasoning — scheduled jobs stop for every page, not one.
            f'<div id="mc-schedbar"></div>'
            # Update bar (5.4): a new version is waiting, or needs the new installer.
            f'<div id="mc-updbar"></div>'
            # confirm.js first: every page gets the app's own dialog, so nothing has to fall back
            # to the browser's confirm()
            f'{_CONFIRM_JS}{_NAVKEYS_JS}{_SWITCHER_JS}{_PENDING_BADGE_JS}{_NEW_REALM_MODAL}'
            f'{_AUTHBAR_JS}{_SCHEDBAR_JS}{_UPDBAR_JS}{_SUPPORT_JS}{_NOTIFBELL_JS}')


def _htok(n) -> str:
    """Token count formatted EXACTLY like usage.js's htok(), so the server-rendered header value and
    the value usage.js writes on load are byte-identical — no visible 'jump' on every Overview visit."""
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n/1e6:.1f}M"
    if n >= 1_000:
        return f"{n/1e3:.1f}k"
    return str(n)


def _kpis(realm, tok30=None, usd30=None) -> str:
    # Tokens & API-eq carry ids so usage.js can refresh them on its cadence (see fixHeaderTotals).
    # We render them from the SAME epoch-aware 30-day totals the Usage endpoint uses, formatted the
    # same way, so usage.js overwrites with an identical string — the value no longer changes on load.
    # (Falls back to the reader snapshot only if the epoch-aware totals weren't supplied.)
    if tok30 is None:
        tok_disp = f"{realm.tokens_30d/1000:.0f}k" if realm.tokens_30d else "—"
    else:
        tok_disp = _htok(tok30) if tok30 else "—"
    if usd30 is None:
        usd_disp = f"≈${realm.cost_30d:.0f}" if realm.cost_30d else "—"
    else:
        usd_disp = f"≈${int(usd30 + 0.5):,}" if usd30 else "—"   # int(x+0.5) = JS Math.round for x>=0
    # Active jobs, not all jobs. A switched-off job is not doing anything, and counting it here
    # made the headline number describe how many jobs exist rather than how much is running.
    t = [("Agents", str(len(realm.members)), "", ""),
         ("Active jobs", str(sum(1 for a in realm.agents for j in a.jobs if j.enabled)), "", ""),
         ("Runs", str(sum(a.runs_30d for a in realm.agents)), "/30d", ""),
         ("Tokens", tok_disp, "/30d", "mc-kpi-tokens"),
         ("API-eq", usd_disp, "", "mc-kpi-apieq")]
    cells = ""
    for label, val, unit, vid in t:
        if vid:
            # async KPI (usage.js fills it on load): show a shimmer skeleton, with the correct value
            # kept in data-v as a no-JS / fetch-failure fallback (see mcHeaderFallback in usage.js).
            valhtml = f'<span id="{vid}" class="mc-kpi-v" data-v="{E(val)}"><span class="mc-skel"></span></span>'
        elif label == "Active jobs":
            # Tagged so toggling a job on the agent page updates this immediately (mcJobCount)
            # rather than leaving the headline disagreeing with the list underneath it.
            valhtml = f'<span data-active-jobs>{E(val)}</span>'
        else:
            valhtml = E(val)
        # Fixed height and no wrapping: the value lands after a fetch, and a unit that wraps onto a
        # second line once the number is wide made this cell — and the whole header — grow.
        cells += (f'<div class="mc-kpi" style="height:62px;white-space:nowrap">'
                  f'<div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
                  f'color:var(--text-muted)">{E(label)}</div>'
                  f'<div style="font-family:var(--font-heading);font-weight:600;font-size:22px;line-height:1.05">{valhtml}'
                  f'<span style="font-size:12px;color:var(--text-soft);margin-left:3px">{E(unit)}</span></div></div>')
    return f'<div style="display:flex;gap:28px;margin-left:8px;flex:none">{cells}</div>'


_NEW_REALM_MODAL = (
    '<div id="mc-newrealm-ov" onclick="if(event.target===this)mcNewRealmClose()" style="display:none;position:fixed;'
    'inset:0;z-index:130;background:rgba(0,0,0,.4);align-items:flex-start;justify-content:center;padding:32px 16px;overflow:auto">'
    '<div style="background:var(--color-bg);border:1px solid var(--color-divider);border-radius:14px;box-shadow:var(--shadow-lg);'
    'width:100%;max-width:760px;display:flex;flex-direction:column;max-height:94vh;overflow:hidden">'
    '<div style="display:flex;align-items:center;gap:10px;padding:14px 18px 8px">'
    '<h2 style="font-family:var(--font-heading);font-size:20px;margin:0">New realm</h2>'
    '<button type="button" class="mc-x" onclick="mcNewRealmClose()" title="Close" aria-label="Close">'
    '&times;</button></div>'
    '<iframe id="mc-newrealm-frame" title="New realm" style="border:0;width:100%;height:600px;display:block"></iframe></div></div>'
    + _NEWREALM_JS)


def _page_shell(realm, active_tab: str, title: str, body: str, dark: bool = False, sec_edit: bool = False) -> str:
    body_cls = "armada-dark" if dark else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(title)}</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, active_tab, sec_edit)}
<div class="mc-appscroll" style="flex:1;min-height:0;overflow:auto">{body}</div></div>{_RUN_JS}{_FORM_JS}{_DOTPOLL_JS}</body></html>"""
