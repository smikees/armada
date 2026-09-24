"""Static-asset plumbing — how server-rendered pages reference the CSS/JS served from webui/static.

`CSSV` is a cache-buster derived from the stylesheets' mtimes, so a CSS edit + restart forces
browsers to refetch. `js()` builds a <script src> tag for an externalized JS module (kept out of
webui.py for smaller diffs / lintability); the per-module tags are pre-built here. `CSS_LINKS` is
the stylesheet <link> pair, cache-buster baked in, used in every page's <head>.
"""
from __future__ import annotations
from pathlib import Path
import logging
from .util import swallowed
log = logging.getLogger(__name__)

# Cache-buster for CSS *and* JS: the newest mtime across every stylesheet and JS module, so editing
# any of them + restart forces the (webview) browser to refetch. Keying only off the CSS meant a
# JS-only change kept the same ?v= and the webview served a stale cached script (dashboard dots not
# updating, old chat behaviour) until an unrelated CSS edit happened to bump the version.
try:
    _sd = Path(__file__).resolve().parent / "webui" / "static"
    _assets = [_sd / "brand.css", _sd / "industry.css", *(_sd / "js").glob("*.js")]
    CSSV = "?v=" + str(int(max(p.stat().st_mtime for p in _assets if p.exists())))
except Exception:  # noqa
    swallowed(log, '<module>: failed; using a default')
    CSSV = ""


def js(name: str) -> str:
    """Reference an externalized JS module served from webui/static/js/. Keeps big scripts
    out of webui.py (lintable, smaller diffs)."""
    return f'<script src="/static/js/{name}.js{CSSV}"></script>'


# The stylesheet links every page's <head> carries (cache-buster baked in).
CSS_LINKS = (f'<link rel="stylesheet" href="/static/industry.css{CSSV}">'
             f'<link rel="stylesheet" href="/static/brand.css{CSSV}">')

# Per-module <script src> tags for the externalized client JS.
CHAT_JS = js("chat")
DASH_JS = js("dash")
JOBCAL_JS = js("jobcal")
USAGE_JS = js("usage")
LAYOUT_JS = js("layout")

# Phase 1: externalized inline client-JS blocks.
AGENT_COLOR_JS = js("agent_color")
AGENT_JS = js("agent")
APPOINT_JS = js("appoint")
ARTEFACTS_JS = js("artefacts")
AUTONOMY_JS = js("autonomy")
AUTHBAR_JS = js("authbar")
SCHEDBAR_JS = js("schedbar")           # 5.5
SUPPORT_JS = js("support")             # 5.6
NOTIFBELL_JS = js("notifbell")
DOTPOLL_JS = js("dotpoll")
FDROP_JS = js("fdrop")
FORM_JS = js("form")
GOALS_JS = js("goals")
JOBS_FILTER_JS = js("jobs_filter")
JOBS_SORT_JS = js("jobs_sort")
JOB_JS = js("job")
JOB_PROPOSAL_JS = js("job_proposal")
MEM_ADD_JS = js("mem_add")
MEM_EXPAND_JS = js("mem_expand")
NEW_JS = js("new")
PENDING_BADGE_JS = js("pending_badge")
REALM_ICON_JS = js("realm_icon")
RUN_JS = js("run")
SECTION_EDIT_JS = js("section_edit")
SETTINGS_JS = js("settings")
SWITCHER_JS = js("switcher")
TABLE_SORT_JS = js("table_sort")
THRESIZE_JS = js("thresize")
USER_JS = js("user")

SYSJOBS_JS = js("sysjobs")
CONFIRM_JS = js("confirm")
NAVKEYS_JS = js("navkeys")

# Phase 2, 2.1: the remaining inline <script> blocks, externalized the same way.
REVEAL_JS = js("reveal")
MDFIELD_JS = js("mdfield")
CAT_JS = js("cat")
INBOX_JS = js("inbox")
CAPHELP_JS = js("caphelp")
CAPEDIT_JS = js("capedit")
CONNMODAL_JS = js("connmodal")
NEWREALM_JS = js("newrealm")
ADDSEC_JS = js("addsec")
MODEBOOT_JS = js("modeboot")
THREADLIST_JS = js("threadlist")
CAPFILTER_JS = js("capfilter")
CAPANIM_JS = js("capanim")
CAPTAB_JS = js("captab")
CAPDRAG_JS = js("capdrag")
JOBSTAB_JS = js("jobstab")
GOALSEARCH_JS = js("goalsearch")
STA2A_TOGGLE_JS = js("sta2a_toggle")
ADDSECTION_JS = js("addsection")
EDITSECTION_JS = js("editsection")
SNAP_JS = js("snap")
DOCSEARCH_JS = js("docsearch")
A2A_TOGGLE_JS = js("a2a_toggle")
ANCHOR_SCROLL_JS = js("anchor_scroll")
JOBOPEN_JS = js("jobopen")
MEMFOCUS_JS = js("memfocus")
COVENANT_JS = js("covenant")
CONSUMPTION_JS = js("consumption")
ADOPT_JS = js("adopt")  # held-realm banner on the Jobs page (5.8c)
