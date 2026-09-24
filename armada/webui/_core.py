"""ARMADA web UI — server-rendered screens matching the approved design handoff.

Reproduces the design's DOM (Industry design-system + ARMADA brand overrides, served from
webui/static/) from LIVE realm data, so the app looks like the mockups but shows the real realm.
This module renders the **realm overview dashboard** (design #2b): title bar, top nav with realm
switcher + tabs + user sections, KPI header, and the Register / From-the-Hand / Attention / Today
widgets. Other screens (agent frame, job detail) are added here as they're built.
"""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import clock, util
from .. import goals as goalsmod

from .changelog import _CHANGELOG, _changelog_modal  # carved out in Phase 3
from ._base import (  # base layer carved out in Phase 3
    E, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _chip, _poss, _REVEAL_JS)
from .consumption import (  # carved out in Phase 3 (pure lower layer)
    _MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE, _CONSUMPTION_STOPS,
    _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js, _model_is_claude)
from .schedfmt import (  # carved out in Phase 3 (pure lower layer)
    _DOW_NAME, _humanize, _cadence_bucket, _sysjob_cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _ordinal, _next_hint, _fmt_ts)
from .agentbits import (  # Layer-1 agent-rendering primitives carved out in Phase 3
    _activity_dot, _agent_activity, _agent_busy, _agent_has_unread, _agent_model_effort,
    _agent_stored_color, _autonomy_badge, _autonomy_of, _avatar_file, _bust, _goals_cell,
    _has_pending_proposals, _health7, _model_chip, _model_chip_label, _model_mark,
    _portrait, _pretty_model, _running_markers, _runs, _thread_meta, _job_created_ts,
    _ACTIVITY_DOT, _AUTONOMY_ALIAS, _AUTONOMY_META, _AUTONOMY_MODES)
from .widgets import (  # dashboard widget renderers carved out in Phase 3
    _health_legend_chips, _jobcal, _reg_row, _register, _usage, _wid_header, _widget_menu,
    _HEALTH_LEGEND_ORDER, _HEALTH_STYLES, _ICON_GRAPH, _ICON_LINE,
    _RUNNING_COLOR, _UNSCHEDULED_COLOR)
from .layout import (  # page chrome/layout carved out in Phase 3
    _titlebar, _nav, _page_shell, _kpis, _theme_style, _NEW_REALM_MODAL)
from .agentcommon import (_AGENT_PALETTE, _EFFORTS, _STATUS_FILTER_COLOR, _agent_color_control, _art_meta, _autonomy_control, _effort_options, _filter_dropdown, _gather_artifacts, _job_created, _job_created_ts, _job_prompt, _job_proposals_block, _model_options, _realm_artefacts, _running_jobs)
from .realmpages import (_agent_cap_counts, _appoint_modal, _cap_count_row, _fmt_date_short, _health7_header, _health_square, _health_grid, _job_health7, _jobs_filter_bar, _new_agent_form, _realm_jobs, _realm_ministers, _status_legend)
from .agentframe import (_agent_body, _agent_default_color, _agent_header, _avatar_count, _avatar_modal, _inbox_msgs, _md_field, _read_md, _tab_configure, _tab_inbox, _tab_jobs, _MD_FIELD_JS)
from .threadsview import (  # threads/chat rendering carved out in Phase 3
    _agent_model_label, _art_chip, _attachments_html, _chat_center, _clear_thread_unread, _est_tokens, _event_card, _mark_thread_unread, _ordered_threads, _render_segments, _render_turns, _sub, _tab_threads, _thread_artifacts, _thread_arts_rail, _thread_caps_rail, _thread_caps_used, _thread_rail, _thread_title, _touch_last_thread, _turn, _turn_actions, _user_avatar, _user_avatar_file, _write_thread_meta, _CAP_ICON, _CAP_KIND_LABEL, _EVENT_ICONS, _THREADLIST_JS)
from .memoryview import (  # Layer-2 carved out in Phase 3
    _agent_memory, _list_mem, _mem_add_button, _mem_cards, _mem_modals, _mem_search, _realm_memory, _tab_memory, _updater_label)
from .goalsview import (  # Layer-2 carved out in Phase 3
    _goal_cards, _goal_modals, _goal_owner_chips, _goal_roster, _goal_status_badge, _goal_status_options, _realm_goals, _tab_goals, _GOAL_STATUS_COLOR)
from .capabilities import (  # Layer-2 carved out in Phase 3
    _agent_toolkit, _cap_manage_btn, _realm_skills, _realm_toolkit, _tab_skills, _tool_group, _tool_row, _toolkit_from, _CAP_DESC, _CAP_EDIT_MODAL, _CAP_HELP, _CONNECTOR_MODAL)


# Static-asset plumbing (cache-buster, stylesheet links, externalized-JS <script> tags) lives in
# assets.py. Re-exported here under the names this module's page templates already interpolate.
from ..assets import (  # noqa: E402
    CSS_LINKS as _CSS_LINKS, CHAT_JS as _CHAT_JS, DASH_JS as _DASH_JS,
    JOBCAL_JS as _JOBCAL_JS, USAGE_JS as _USAGE_JS, LAYOUT_JS as _LAYOUT_JS,
    ADDSEC_JS as _ADDSEC_JS)  # Phase 2, 2.1
# Externalized inline client-JS blocks (Phase 1): now lintable static/js modules, re-exported
# under the names this module's templates interpolate.
from ..assets import (  # noqa: E402
    AGENT_COLOR_JS as _AGENT_COLOR_JS,
    AGENT_JS as _AGENT_JS,
    APPOINT_JS as _APPOINT_JS,
    ARTEFACTS_JS as _ARTEFACTS_JS,
    AUTONOMY_JS as _AUTONOMY_JS,
    DOTPOLL_JS as _DOTPOLL_JS,
    FDROP_JS as _FDROP_JS,
    FORM_JS as _FORM_JS,
    GOALS_JS as _GOALS_JS,
    JOBS_FILTER_JS as _JOBS_FILTER_JS,
    JOBS_SORT_JS as _JOBS_SORT_JS,
    JOB_JS as _JOB_JS,
    JOB_PROPOSAL_JS as _JOB_PROPOSAL_JS,
    MEM_ADD_JS as _MEM_ADD_JS,
    MEM_EXPAND_JS as _MEM_EXPAND_JS,
    NEW_JS as _NEW_JS,
    PENDING_BADGE_JS as _PENDING_BADGE_JS,
    REALM_ICON_JS as _REALM_ICON_JS,
    RUN_JS as _RUN_JS,
    SECTION_EDIT_JS as _SECTION_EDIT_JS,
    SETTINGS_JS as _SETTINGS_JS,
    SWITCHER_JS as _SWITCHER_JS,
    TABLE_SORT_JS as _TABLE_SORT_JS,
    THRESIZE_JS as _THRESIZE_JS,
    USER_JS as _USER_JS)


# Visual theme (theme-as-data): the per-app chosen theme injects a :root token override right
# after the base stylesheets. The default "armada" theme returns '' (inherits brand.css), so
# rendering is unchanged unless the user picks another theme in Settings -> Appearance.
from .. import vtheme, appconfig  # noqa: E402


# --- inline SVGs (from the design) --------------------------------------------------------
# Brand identity (name, logo, mark, about, titles) lives in brand.py — one file to re-skin.
LOGO, MARK = brand.LOGO, brand.MARK
# Icon subsystem (registry, _icon, _ICONS_JS, file/realm-icon helpers) lives in icons.py — the
# single source shared with the client JS. Re-exported here so this module's call sites stay put.
from ..icons import (  # noqa: E402
    ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR, _ICON_REFRESH)
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


# Curated IANA timezones ordered west→east by standard UTC offset (value, city, offset label).
_TIMEZONES = [
    ("Pacific/Midway", "Midway", "−11:00"), ("Pacific/Honolulu", "Honolulu", "−10:00"),
    ("America/Anchorage", "Anchorage", "−09:00"), ("America/Los_Angeles", "Los Angeles", "−08:00"),
    ("America/Denver", "Denver", "−07:00"), ("America/Chicago", "Chicago", "−06:00"),
    ("America/New_York", "New York", "−05:00"), ("America/Halifax", "Halifax", "−04:00"),
    ("America/Sao_Paulo", "São Paulo", "−03:00"), ("Atlantic/South_Georgia", "South Georgia", "−02:00"),
    ("Atlantic/Azores", "Azores", "−01:00"), ("Europe/London", "London", "+00:00"),
    ("Europe/Madrid", "Madrid / Central European", "+01:00"), ("Europe/Athens", "Athens", "+02:00"),
    ("Europe/Moscow", "Moscow", "+03:00"), ("Asia/Dubai", "Dubai", "+04:00"),
    ("Asia/Karachi", "Karachi", "+05:00"), ("Asia/Kolkata", "Kolkata", "+05:30"),
    ("Asia/Dhaka", "Dhaka", "+06:00"), ("Asia/Bangkok", "Bangkok", "+07:00"),
    ("Asia/Shanghai", "Shanghai", "+08:00"), ("Asia/Tokyo", "Tokyo", "+09:00"),
    ("Australia/Sydney", "Sydney", "+10:00"), ("Pacific/Noumea", "Nouméa", "+11:00"),
    ("Pacific/Auckland", "Auckland", "+12:00"), ("Pacific/Tongatapu", "Tongatapu", "+13:00"),
]


def _tz_options(selected: str) -> str:
    """<option>s for the timezone select: 'System' first (value ''), then zones west→east.
    If the saved timezone isn't in the curated list, it's added so it stays selectable."""
    sel = (selected or "").strip()
    known = {v for v, _, _ in _TIMEZONES}
    out = f'<option value="" {"selected" if not sel else ""}>System (your OS timezone)</option>'
    if sel and sel not in known:
        out += f'<option value="{E(sel)}" selected>{E(sel)}</option>'
    for value, city, off in _TIMEZONES:
        out += f'<option value="{E(value)}" {"selected" if value == sel else ""}>(UTC{off}) {E(city)}</option>'
    return out


def _user(realm_root) -> dict:
    """The owner's settings (source of truth in realm.json 'user'), falling back to the
    top-level owner/timezone for older realms."""
    p = Path(realm_root) / "realm.json"
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8-sig"))
            u = dict(cfg.get("user") or {})
            u.setdefault("name", cfg.get("owner", ""))
            u.setdefault("timezone", cfg.get("timezone", ""))
            return u
        except Exception:  # noqa
            swallowed(log, '_user: failed; ignored')
    return {}


# --- data helpers -------------------------------------------------------------------------
# status vocabulary + colours now live in status.py (single source) — call sites use status.color().


# The look of each health state (square + legend swatch share this). Filled states set a
# background; Scheduled is a hollow teal outline; Not scheduled is a faint fill.
def _dot(status: str) -> str:
    return {"green": "var(--status-ok)", "yellow": "var(--status-warn)", "red": "var(--status-bad)",
            "planned": "var(--status-idle)", "unknown": "var(--status-idle)"}.get(status, "var(--status-idle)")


# state -> (dot colour, pulses?, label). Mirrors the Claude app: grey idle, teal unseen output,
# orange needs-input, pulsing darker grey while working.
# --- register row -------------------------------------------------------------------------
# --- widgets ------------------------------------------------------------------------------
# one base colour per family; versions within a family are shades of it (newest = strongest).
# Token-consumption gradient (matches the design bar): light cream (low consumption) → orange →
# green (low) → yellow → orange → red (high) — a traffic-light spectrum that reads intuitively as
# cost. A model/agent icon is coloured by sampling this at its 0..99 index.
def _ver_tuple(label: str) -> tuple:
    """Version part of a pretty label as a sortable tuple: 'Opus 4.8'→(4,8), 'Opus 5'→(5,), 'Opus'→()."""
    parts = (label or "").split()
    if len(parts) < 2:
        return ()
    bits = parts[1].split(".")
    return tuple(int(b) for b in bits) if all(b.isdigit() for b in bits) else ()


def _model_color_map(labels) -> dict:
    """label → colour by token-consumption index on the shared gradient (light = low, dark = high).
    All versions of a family share a price tier, so they share a colour; non-Claude labels fall back."""
    out: dict[str, str] = {}
    fb = 0
    for lb in dict.fromkeys(labels):
        if _model_is_claude(lb):
            out[lb] = _consumption_color(models.model_index(lb))
        else:
            out[lb] = _MODEL_CLR.get(lb) or _MODEL_FALLBACK[fb % len(_MODEL_FALLBACK)]
            fb += 1
    return out


def _htok(n: int) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n/1e6:.1f}M"
    if n >= 1_000:
        return f"{n/1e3:.1f}k"
    return str(n)


def _totals_30d(realm, realm_root, today: datetime.date):
    """Epoch-aware rolling-30-day (today-29 … today) token + api-eq totals from run telemetry.
    THE single source for both the Overview header KPIs (server-rendered) and the Usage endpoint's
    total_30d/usd_30d, so the header value doesn't change when usage.js refreshes it on load."""
    realm_root = Path(realm_root)
    lo30 = (today - datetime.timedelta(days=29)).isoformat()
    try:
        epoch = str(json.loads((realm_root / "realm.json").read_text("utf-8-sig")).get("usage_epoch") or "")
    except Exception:  # noqa
        swallowed(log, '_totals_30d: failed; using a default')
        epoch = ""
    agents = ([realm.coordinator] if realm.coordinator else []) + list(realm.members)
    tok, usd = 0, 0.0
    for a in agents:
        for ev in _runs(realm_root, a.id):
            dd = str(ev.get("ts", ""))[:10]
            if len(dd) != 10 or dd < lo30 or (epoch and dd < epoch):
                continue
            tk = ev.get("tokens") if isinstance(ev.get("tokens"), dict) else {}
            tok += int(tk.get("total", 0) or 0)
            usd += float(tk.get("api_equiv_usd", 0) or 0)
    return tok, round(usd, 2)


def _usage_stats(realm, realm_root: Path, today: datetime.date):
    """Aggregate ARMADA's own run-report telemetry over the last 30 days → overall total,
    per-agent totals (first), and per-model totals. Real data we log ourselves."""
    lo = (today - datetime.timedelta(days=29)).isoformat()
    per_model: dict[str, dict] = {}
    per_agent = []
    total_tok, total_usd = 0, 0.0
    agents = ([realm.coordinator] if realm.coordinator else []) + list(realm.members)
    for a in agents:
        atok, ausd = 0, 0.0
        for ev in _runs(realm_root, a.id):
            if str(ev.get("ts", ""))[:10] < lo:
                continue
            tk = ev.get("tokens") if isinstance(ev.get("tokens"), dict) else {}
            t = int(tk.get("total", 0) or 0)
            usd = float(tk.get("api_equiv_usd", 0) or 0)
            atok += t
            ausd += usd
            lbl = _pretty_model(ev.get("model"))
            m = per_model.setdefault(lbl, {"tok": 0, "usd": 0.0})
            m["tok"] += t
            m["usd"] += usd
        per_agent.append((a, atok, ausd))          # every agent, even idle ones
        total_tok += atok
        total_usd += ausd
    per_agent.sort(key=lambda x: (-x[1], x[0].display.lower()))   # top-usage → least
    # every available model (from the catalog) + any recorded model, with its token use
    labels: list[str] = []
    for m in _MODELS:
        p = _pretty_model(m)
        if p not in labels:
            labels.append(p)
    for p in per_model:
        if p not in labels:
            labels.append(p)
    models = [(p, per_model.get(p, {"tok": 0, "usd": 0.0})) for p in labels]
    models.sort(key=lambda kv: (-kv[1]["tok"], kv[0].lower()))    # most-used → unused
    return total_tok, total_usd, per_agent, models


# ColorBrewer "Paired" (12) — concrete hex so they double as <input type=color> presets and stay
# stable in the stored agent.json. Used for agent colours in the usage graphs/legends.
def _usage_data(realm, realm_root, mode: str, window: str, by: str = "agents") -> dict:
    """Windowed usage from run telemetry, for the Usage widget's line/graph modes.
    line: per-agent + per-model totals over a window (today/7d/mtd).
    graph: a stacked time series (weekly = last 7 days; monthly = last 12 months),
    split per agent (default) or per model."""
    realm_root = Path(realm_root)
    today = clock.today()
    agents = ([realm.coordinator] if realm.coordinator else []) + list(realm.members)
    agent_color = {a.display: (_agent_stored_color(realm_root, a.id) or _AGENT_PALETTE[i % len(_AGENT_PALETTE)])
                   for i, a in enumerate(agents)}
    recs = []   # (date_iso, agent_display, model_label, tokens, usd)
    for a in agents:
        for ev in _runs(realm_root, a.id):
            dd = str(ev.get("ts", ""))[:10]
            if len(dd) != 10:
                continue
            tk = ev.get("tokens") if isinstance(ev.get("tokens"), dict) else {}
            recs.append((dd, a.display, _pretty_model(ev.get("model")),
                         int(tk.get("total", 0) or 0), float(tk.get("api_equiv_usd", 0) or 0)))

    # usage epoch: a clean-slate cutoff (realm.json 'usage_epoch', ISO date). Runs before it are kept
    # on disk (job history/calendars still use them) but excluded from usage totals, so usage can be
    # reset to "today forward" without destroying run history.
    try:
        epoch = str(json.loads((realm_root / "realm.json").read_text("utf-8-sig")).get("usage_epoch") or "")
    except Exception:  # noqa
        swallowed(log, '_usage_data: failed; using a default')
        epoch = ""
    if epoch:
        recs = [r for r in recs if r[0] >= epoch]

    # rolling-30-day totals (epoch-aware) — surfaced on every response so the Overview header's
    # Tokens/30d KPI can refresh on the Usage widget's cadence instead of only at page load. Same
    # helper the header uses at render time, so the two never disagree (no jump on load).
    total_30d, usd_30d = _totals_30d(realm, realm_root, today)

    # model universe = currently-available models (from the synced catalog) + any model actually used
    # in the data (so a since-retired model still appears); coloured by family, newest = strongest.
    model_universe: list[str] = []
    for mid, _lab in models.options(realm_root):
        p = _pretty_model(mid)
        if p not in model_universe:
            model_universe.append(p)
    for _dd, _disp, lbl, _t, _u in recs:
        if lbl not in model_universe:
            model_universe.append(lbl)
    model_colors = _model_color_map(model_universe)

    if mode == "graph":
        by = "models" if by == "models" else "agents"
        if window == "monthly":
            order = []
            for i in range(11, -1, -1):
                mm, yy = today.month - i, today.year
                while mm <= 0:
                    mm += 12
                    yy -= 1
                order.append(((yy, mm), datetime.date(yy, mm, 1).strftime("%b") + (f"'{yy % 100:02d}" if mm == 1 else "")))
            bkey = lambda dd: (int(dd[:4]), int(dd[5:7]))
        elif window == "weekly":
            # last 8 ISO weeks, one bar per week, labelled by the week's Monday (e.g. "1 Sep")
            this_mon = today - datetime.timedelta(days=today.weekday())
            order = []
            for i in range(7, -1, -1):
                m = this_mon - datetime.timedelta(weeks=i)
                order.append((m.isoformat(), f"W{m.isocalendar()[1]} · {m.day} {m.strftime('%b')}"))
            bkey = lambda dd: (datetime.date(int(dd[:4]), int(dd[5:7]), int(dd[8:10]))
                               - datetime.timedelta(days=datetime.date(int(dd[:4]), int(dd[5:7]), int(dd[8:10])).weekday())).isoformat()
        else:
            window = "daily"
            days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
            order = [(d.isoformat(), d.strftime("%a ") + str(d.day)) for d in days]
            bkey = lambda dd: dd
        keys = {k for k, _ in order}
        perbucket = {k: {} for k in keys}
        for dd, disp, lbl, tok, _u in recs:
            k = bkey(dd)
            if k not in perbucket:
                continue
            seg = disp if by == "agents" else lbl
            perbucket[k][seg] = perbucket[k].get(seg, 0) + tok
        # stable colour per segment key across the whole series
        allkeys = sorted({s for m in perbucket.values() for s in m})
        kidx = {s: i for i, s in enumerate(allkeys)}

        def seg_color(name, i):
            if by == "agents":
                return agent_color.get(name, _AGENT_PALETTE[i % len(_AGENT_PALETTE)])
            return model_colors.get(name) or _model_color(name, i)
        bars = []
        for k, label in order:
            segs = sorted(perbucket[k].items(), key=lambda kv: -kv[1])
            segments = [{"name": s, "tok": v, "color": seg_color(s, kidx.get(s, 0))} for s, v in segs if v > 0]
            bars.append({"label": label, "tok": sum(perbucket[k].values()), "segments": segments})
        return {"mode": "graph", "window": window, "by": by, "bars": bars,
                "total": sum(b["tok"] for b in bars), "total_30d": total_30d, "usd_30d": usd_30d}

    # line mode
    if window == "today":
        lo = today
    elif window == "mtd":
        lo = today.replace(day=1)                 # month-to-date: 1st of the current month
    else:
        window, lo = "7d", today - datetime.timedelta(days=6)
    loi, hii = lo.isoformat(), today.isoformat()
    per_agent = {a.display: 0 for a in agents}
    per_model: dict[str, int] = {}
    total, usd = 0, 0.0
    for dd, disp, lbl, tok, u in recs:
        if dd < loi or dd > hii:
            continue
        per_agent[disp] = per_agent.get(disp, 0) + tok
        per_model[lbl] = per_model.get(lbl, 0) + tok
        total += tok
        usd += u
    labels = list(model_universe)                 # available + used (retired-but-used included)
    for p in per_model:
        if p not in labels:
            labels.append(p)
    labels.sort(key=lambda p: (-per_model.get(p, 0), p.lower()))
    model_rows = [{"label": p, "tok": per_model.get(p, 0),
                   "color": model_colors.get(p) or _model_color(p, i),
                   "claude": _model_is_claude(p)} for i, p in enumerate(labels)]
    agents_list = sorted(({"name": a.display, "tok": per_agent.get(a.display, 0),
                           "color": agent_color.get(a.display)} for a in agents),
                         key=lambda x: (-x["tok"], x["name"].lower()))
    return {"mode": "line", "window": window, "total": total, "usd": round(usd, 2),
            "total_30d": total_30d, "usd_30d": usd_30d,
            "agents": agents_list, "models": model_rows}


def _jc_norm(st) -> str:
    # calendar buckets: success | failed | warn (default success), from the canonical status
    return {status.FAILED: "failed", status.WARN: "warn"}.get(status.normalize(st), "success")


def _jobcal_events(realm, realm_root, d_from, d_to) -> list[dict]:
    """Job occurrences in [d_from, d_to]: projected from each job's schedule, with past slots
    resolved to their actual run status (success/failed/warn/missed); manual/ad-hoc runs added too."""
    from .. import scheduler as S
    realm_root = Path(realm_root)
    now = clock.now().replace(tzinfo=None)
    today_d = now.date()
    agents = ([realm.coordinator] if realm.coordinator else []) + list(realm.members)
    days = []
    d = d_from
    while d <= d_to:
        days.append(d)
        d += datetime.timedelta(days=1)
    lo, hi = d_from.isoformat(), d_to.isoformat()
    out = []
    for a in agents:
        idx = {}
        for r in _runs(realm_root, a.id):
            dd = str(r.get("ts", ""))[:10]
            if not dd or dd < lo or dd > hi:
                continue
            if r.get("kind") == "chat" or str(r.get("task") or "").startswith("chat:"):
                continue                          # interactive chat turns aren't jobs — keep them off the calendar
            idx.setdefault((dd, str(r.get("task") or "")), []).append(r)
        run_now = _running_jobs(realm_root, a.id)
        task2job = {(j.report_task or j.id): j for j in a.jobs}
        for j in a.jobs:
            sched = j.cadence or "manual"
            task = j.report_task or j.id
            cron = isinstance(sched, str) and S.is_cron(sched)
            parsed = None if cron else S.parse_schedule(sched)
            if not cron and not parsed:
                continue  # manual — only its runs (handled below) appear
            # When the job came into being. The week strip has always honoured this; the calendar
            # did not, so the same job read "missed four times" on one view and "missed once" on
            # the other — one word with two meanings on one page. A job cannot miss a fire time
            # that fell before it was written.
            since = _job_created_ts(realm_root, a.id, j.id,
                                    _job_prompt(realm_root, a.id, j.id))
            since_dt = None
            if since:
                try:
                    since_dt = datetime.datetime.fromisoformat(
                        since if "T" in str(since) else str(since) + "T00:00:00")
                    if since_dt.tzinfo is not None:
                        since_dt = since_dt.replace(tzinfo=None)
                except (ValueError, TypeError):
                    since_dt = None
            for day in days:
                if cron:
                    occs = S.cron_day_times(sched, day)[:12]
                else:
                    ds, hh, mm = parsed
                    occs = [(hh, mm)] if day.weekday() in ds else []
                for hh, mm in occs:
                    dt = datetime.datetime(day.year, day.month, day.day, hh, mm)
                    if since_dt and dt < since_dt:
                        continue                      # before the job existed: nothing was due
                    past = dt <= now
                    status = "scheduled"
                    if past:
                        rs = idx.get((day.isoformat(), task))
                        if rs:
                            status = _jc_norm(rs[0].get("status"))
                            idx[(day.isoformat(), task)] = rs[1:]
                        elif j.id in run_now and day == today_d:
                            status = "running"           # executing now (its slot passed, no report yet)
                        else:
                            status = "missed"
                    out.append({"agent": a.id, "agent_disp": a.display, "job": j.id, "job_name": j.name,
                                "ts": dt.strftime("%Y-%m-%dT%H:%M"), "status": status, "past": past,
                                "cad": _cadence_bucket(j.cadence)})
        for (dd, task), rs in idx.items():
            for r in rs:
                ts = str(r.get("ts", ""))
                hm = ts[11:16] if len(ts) >= 16 else "00:00"
                jb = task2job.get(task)
                out.append({"agent": a.id, "agent_disp": a.display,
                            "job": (jb.id if jb else task), "job_name": (jb.name if jb else (task or "run")),
                            "ts": dd + "T" + hm, "status": _jc_norm(r.get("status")), "past": True,
                            "cad": _cadence_bucket(jb.cadence) if jb else "other"})
    return out


def _sysjobcal_events(realm_root, d_from, d_to) -> list[dict]:
    """System-job occurrences in [d_from, d_to], in the same shape as _jobcal_events.

    System jobs keep only their *last* run in state, not a history — so this draws only what is
    actually known: the one recorded run, plus the upcoming due times projected forward from it at
    the job's interval. Past slots we have no record for are left blank rather than invented.

    Jobs that run more often than hourly (inbox delivery) are omitted: plotting 1,440 identical
    chips a day would tell you nothing and hide everything else."""
    from .. import sysjobs as _sj
    now = clock.now().replace(tzinfo=None)
    lo = datetime.datetime.combine(d_from, datetime.time.min)
    hi = datetime.datetime.combine(d_to, datetime.time.max)
    out = []
    for j in _sj.status(realm_root):
        mins = int(j.get("every_minutes") or 0)
        ev = {"agent": "system", "agent_disp": "ARMADA", "job": j["id"], "job_name": j["name"],
              "cad": _sysjob_cadence_bucket(mins), "cost": j.get("cost") or ""}
        last = None
        try:
            last = datetime.datetime.fromisoformat(str(j.get("last_run") or ""))
        except ValueError:
            last = None
        if last is not None:
            naive = last.replace(tzinfo=None)
            if lo <= naive <= hi:
                st = "failed" if j.get("status") == "error" else "success"
                out.append({**ev, "ts": naive.strftime("%Y-%m-%dT%H:%M"), "status": st, "past": True})
        if mins < 60 or not j.get("enabled"):
            continue                       # sub-hourly: unplottable. Switched off: nothing upcoming.
        step = datetime.timedelta(minutes=mins)
        nxt = (last.replace(tzinfo=None) + step) if last is not None else now
        while nxt < max(lo, now):          # fast-forward to the first future slot inside the window
            nxt += step
        guard = 0
        while nxt <= hi and guard < 400:
            out.append({**ev, "ts": nxt.strftime("%Y-%m-%dT%H:%M"), "status": "scheduled", "past": False})
            nxt += step
            guard += 1
    return out


def _from_hand(realm, realm_root) -> str:
    c = realm.coordinator
    if not c:
        return ""
    quote = E(c.bulletin or f"{c.display} coordinates the realm.")
    return (f'<div class="mc-widget" style="height:100%;background:var(--color-accent-2-100);'
            f'border-color:color-mix(in srgb,var(--color-accent-2) 50%,var(--color-divider))">'
            f'<div style="display:flex;align-items:center;gap:6px;padding:8px 12px 0">{GRIP}'
            f'<span style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--color-accent-2-700)">'
            f'From the {E(realm.theme_coordinator)}</span></div>'
            f'<div style="display:flex;gap:12px;padding:8px 12px 12px;align-items:flex-start">'
            f'<div style="flex:none">{_portrait(realm_root, c, 52)}</div>'
            f'<div style="flex:1"><div style="font-family:var(--font-heading);font-weight:600;font-size:17px;line-height:1.2">'
            f'&ldquo;{quote}&rdquo;</div>'
            f'<div style="display:flex;gap:8px;margin-top:10px">'
            f'<button class="btn btn-primary btn-sm">Reply</button>'
            f'<button class="btn btn-secondary btn-sm">Main thread</button></div></div></div></div>')


def _attention(realm, realm_root, today) -> str:
    items = []
    for a in realm.agents:
        for ev in _runs(realm_root, a.id):
            st = status.normalize(ev.get("status", ""))
            if status.is_bad(st) and str(ev.get("ts", ""))[:10] == today.isoformat():
                failed = st == status.FAILED
                items.append((("var(--status-bad)" if failed else "var(--status-warn)"),
                              E(str(ev.get("summary", "") or f"{a.display} job issue")[:120]),
                              "Failure" if failed else "Issue", E(a.display), "today"))
    body = ""
    if items:
        for dot, text, kind, who, age in items[:8]:
            body += (f'<div class="mc-row" style="padding:9px 12px;border-bottom:1px solid '
                     f'var(--text-8);display:flex;gap:9px;align-items:flex-start">'
                     f'<i style="width:8px;height:8px;border-radius:50%;flex:none;margin-top:4px;background:{dot}"></i>'
                     f'<div style="min-width:0;flex:1"><div style="font-size:12px;line-height:1.35">{text}</div>'
                     f'<div style="font-size:10.5px;color:var(--text-muted);margin-top:2px">'
                     f'{kind} · {who} · {age}</div></div></div>')
    else:
        body = ('<div style="padding:16px 12px;font-size:12.5px;color:var(--text-muted)">'
                'Nothing needs you right now.</div>')
    return (f'<div class="mc-widget" style="height:100%">'
            f'{_wid_header("Attention", "· " + str(len(items)))}'
            f'<div style="overflow:auto;display:flex;flex-direction:column">{body}</div></div>')


def _today(realm, realm_root, today) -> str:
    evs = []
    for a in realm.agents:
        for ev in _runs(realm_root, a.id):
            if str(ev.get("ts", ""))[:10] == today.isoformat():
                evs.append((str(ev.get("ts", ""))[11:16], a.display,
                            E(str(ev.get("task", ""))), str(ev.get("status", "ok")).lower(),
                            E(str(ev.get("summary", "") or "")[:60])))
    evs.sort()
    body = ""
    if evs:
        for tm, who, job, st, note in evs[:12]:
            body += (f'<div class="mc-row" style="display:grid;grid-template-columns:40px 10px 1fr;gap:8px;'
                     f'align-items:center;padding:6px 0">'
                     f'<span style="font-family:ui-monospace,Menlo,monospace;font-size:11.5px;'
                     f'color:var(--text-65)">{E(tm)}</span>'
                     f'<i style="width:8px;height:8px;border-radius:50%;background:{status.color(st)}"></i>'
                     f'<div style="font-size:12px;min-width:0"><div style="font-weight:500;white-space:nowrap;overflow:hidden;'
                     f'text-overflow:ellipsis">{job}</div><div style="font-size:10.5px;'
                     f'color:var(--text-muted);white-space:nowrap;overflow:hidden;'
                     f'text-overflow:ellipsis">{who} · {note}</div></div></div>')
    else:
        body = ('<div style="padding:16px 12px;font-size:12.5px;color:var(--text-muted)">'
                'No runs yet today.</div>')
    d = today.strftime("%a %d %b")
    return (f'<div class="mc-widget" style="height:100%">'
            f'{_wid_header("Today", "· " + E(d))}'
            f'<div style="padding:6px 12px;display:flex;flex-direction:column">{body}</div></div>')


# --- page ---------------------------------------------------------------------------------
# form styling constants (defined early so modals declared above their later duplicates can use them)
_ADD_SECTION_MODAL = (
    '<div id="mc-addsec-modal" class="mc-modal-ov" onclick="if(event.target===this)mcAddSectionClose()">'
    '<div class="mc-modal-box" style="padding:20px;width:min(520px,92vw)">'
    '<div style="display:flex;align-items:center;margin-bottom:8px"><div style="font-family:var(--font-heading);'
    'font-weight:600;font-size:17px">Add a section</div>'
    '<button class="btn btn-secondary btn-sm" style="margin-left:auto" onclick="mcAddSectionClose()">Cancel</button></div>'
    '<div style="font-size:12px;color:var(--text-dim);margin-bottom:10px">'
    'Promote a page or artifact to the top menu — point it at a file in the realm (HTML/Markdown) or a URL.</div>'
    f'<label style="{_LBL};margin-top:0">Name {_STAR}</label>'
    f'<input id="as-name" placeholder="E.g. Daily Digest" style="{_FIELD}">'
    f'<label style="{_LBL}">Source (file path in the realm, or https URL) {_STAR}</label>'
    f'<input id="as-src" placeholder="E.g. shared/digest.html  ·  or  ·  https://digest.stamih.com" style="{_FIELD}">'
    '<div style="margin-top:14px;display:flex;gap:8px;align-items:center;justify-content:flex-end">'
    '<span id="as-msg" style="margin-right:auto;font-size:12px;color:var(--text-muted)"></span>'
    '<button class="btn btn-primary" onclick="mcAddSectionSave()">Add</button>'
    '</div></div></div>'
    + _ADDSEC_JS)


# Keeps the Jobs-tab pending-proposal badge current without a navigation: polls every 10s and on
# tab focus, and exposes window.mcPendingRefresh() so a fresh proposal (e.g. an agent creating one
# mid-chat) can bump it immediately.






# Event types that get a bespoke look; everything else falls back to the generic card.
def _agent_memory_realm(realm_root: Path) -> list[tuple[str, str]]:
    return memory._memories(Path(realm_root) / "memory")


# (value, title, icon, description, icon colour, icon hover)
# migrate old values to the 3-mode model
# value → (icon, title, colour, hover) derived from the modes above (one source)
_MODELS = ["Claude Opus 5", "Claude Sonnet 5", "Claude Haiku 4.5", "Claude Fable 5",
           "Claude Opus 4.8", "Claude Sonnet 4.5"]
_DOWS = [("Mon", 1), ("Tue", 2), ("Wed", 3), ("Thu", 4), ("Fri", 5), ("Sat", 6), ("Sun", 0)]


_CRON_HELP = ('<div id="mc-cronhelp" class="mc-modal-ov" onclick="if(event.target===this)mcCronHelp(false)">'
              '<div class="mc-modal-box" style="padding:20px;width:min(560px,92vw);max-height:80vh;overflow:auto">'
              '<div style="display:flex;align-items:center;margin-bottom:12px"><div style="font-family:var(--font-heading);'
              'font-weight:600;font-size:17px">Cron notation</div>'
              '<button class="btn btn-secondary btn-sm" style="margin-left:auto" onclick="mcCronHelp(false)">Close</button></div>'
              '<div style="font-size:12.5px;line-height:1.6">A schedule is five space-separated fields:'
              '<pre style="background:var(--color-sand-100);border:1px solid var(--color-sand-300);border-radius:var(--r);'
              'padding:10px;margin:8px 0;font-size:12px;white-space:pre-wrap">minute  hour  day-of-month  month  day-of-week\n  0      9        *          *        1-5</pre>'
              '<ul style="margin:6px 0 10px;padding-left:18px">'
              '<li><b>*</b> = every value</li>'
              '<li><b>1-5</b> = a range (Mon–Fri; days are 0=Sun … 6=Sat)</li>'
              '<li><b>1,15</b> = a list</li>'
              '<li><b>*/2</b> = every 2nd value</li></ul>'
              '<div style="font-weight:600;margin-bottom:4px">Examples</div>'
              '<table class="table" style="font-size:12px"><tbody>'
              '<tr><td class="mono">0 9 * * *</td><td>every day at 09:00</td></tr>'
              '<tr><td class="mono">0 9 * * 1-5</td><td>weekdays at 09:00</td></tr>'
              '<tr><td class="mono">30 14 * * 1</td><td>Mondays at 14:30</td></tr>'
              '<tr><td class="mono">0 8 1 * *</td><td>the 1st of every month at 08:00</td></tr>'
              '<tr><td class="mono">0 8 1-7 * 6</td><td>the first Saturday of the month at 08:00</td></tr>'
              '</tbody></table>'
              '<div style="font-size:11.5px;color:var(--text-muted);margin-top:8px">'
              'Tip: use the presets and day circles above and the cron box fills in for you.</div></div></div></div>')




# The New-realm wizard as a dashboard modal (iframe of /new/realm?embed=1) — a lightweight shell so the
# heavy wizard DOM/JS load only when opened, and only once, without duplicating on every page.
# Live status-dot poller for any server-rendered page (Ministers, etc.) that carries [data-agentdot]
# markers. Self-contained + inert unless such dots exist, so it's safe to drop into every page shell.


# status-filter value → the colour swatch shown next to that option
# Shared dropdown behaviour (used by the realm Jobs page and the agent Jobs tab).


def _settings_realm(realm, realm_root) -> str:
    return (f'<div style="display:flex;gap:10px;align-items:center">'
            f'<span style="display:flex;color:var(--text-strong)">{_realm_icon(realm, 22)}</span>'
            f'<div style="font-size:12.5px"><b>{E(realm.name)}</b> · <span class="mono">{E(str(realm_root))}</span></div>'
            f'<label class="mc-frame" style="cursor:pointer;padding:5px 10px;border-radius:var(--r);font-size:12px;margin-left:auto">'
            f'Upload icon<input type="file" accept="image/*" style="display:none" onchange="mcUploadRealmIcon(this)"></label></div>'
            f'<div id="ri-msg" style="font-size:11.5px;color:var(--text-muted);margin-top:4px"></div>'
            + _REALM_ICON_JS)


_ABOUT = brand.ABOUT


def _user_avatar_modal() -> str:
    n = _avatar_count()
    tiles = "".join(
        f'<img src="/static/avatars/a{i}.png" width="64" height="64" loading="lazy" onclick="mcSetUserPreset(\'a{i}\')" '
        f'style="width:64px;height:64px;border-radius:50%;cursor:pointer;border:2px solid transparent;background:var(--color-accent-100)"'
        f' onmouseover="this.style.borderColor=\'var(--color-accent)\'" onmouseout="this.style.borderColor=\'transparent\'">'
        for i in range(1, n + 1))
    return (f'<div id="us-avatar-modal" class="mc-modal-ov" onclick="if(event.target===this)mcUserAvatarModal(false)">'
            f'<div class="mc-modal-box" style="width:min(560px,92vw);max-height:78vh;overflow:auto">'
            f'<div style="display:flex;align-items:center;margin-bottom:12px"><div class="mc-h-card" style="margin-bottom:0px">Pick an avatar</div>'
            f'<button class="btn btn-secondary btn-sm" style="margin-left:auto" onclick="mcUserAvatarModal(false)">Close</button></div>'
            f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(64px,1fr));gap:14px;justify-items:center">{tiles}</div>'
            f'<div id="us-presetmsg" style="font-size:12px;color:var(--text-muted);margin-top:10px"></div></div></div>')




_ICONS_PICK = ["🏛️", "🏢", "🏴‍☠️", "🧭", "🛰️", "🧠", "💼", "🏰", "⚙️", "🔭", "📚", "🩺", "🌱", "🗺️"]


_WIZ_JS = r"""
let mcTpl='state', mcIcon='';
function mcPickTpl(el){mcTpl=el.dataset.tpl;document.querySelectorAll('.mc-tplcard').forEach(c=>c.style.outline='');
  el.style.outline='2px solid var(--color-accent)';mcIcon=MC_PRESETS[mcTpl].icon;mcMarkIcon();}
function mcPickIcon(el){mcIcon=el.dataset.icon;window.mcIconData='';document.getElementById('r-iconprev').innerHTML='';mcMarkIcon();}
async function mcWizIcon(input){const f=input.files[0];if(!f)return;
  const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=URL.createObjectURL(f);});
  const S=128,c=document.createElement('canvas');c.width=S;c.height=S;const x=c.getContext('2d');x.imageSmoothingQuality='high';
  const side=Math.min(img.naturalWidth,img.naturalHeight);
  x.drawImage(img,(img.naturalWidth-side)/2,(img.naturalHeight-side)/2,side,side,0,0,S,S);URL.revokeObjectURL(img.src);
  window.mcIconData=c.toDataURL('image/png');
  document.getElementById('r-iconprev').innerHTML='<img src="'+window.mcIconData+'" width=22 height=22 style="border-radius:3px;vertical-align:middle">';
  document.querySelectorAll('.mc-iconpick').forEach(s=>s.style.background='');}
function mcMarkIcon(){document.querySelectorAll('.mc-iconpick').forEach(s=>s.style.background=s.dataset.icon===mcIcon?'var(--text-12)':'');}
function mcWizStep(n){document.querySelectorAll('#wiz-steps .wiz-step').forEach(function(el){var on=(+el.dataset.s===n);
  el.style.background=on?'var(--color-accent-100)':'var(--text-6)';
  el.style.color=on?'var(--color-accent-700)':'var(--text-muted)';});}
function mcWizCancel(){if(window.parent!==window&&window.parent.mcNewRealmClose){window.parent.mcNewRealmClose();}else{location.href='/settings';}}
function mcWizStepClick(n){var onStep2=document.getElementById('wiz-2').style.display!=='none';
  if(n===2&&!onStep2)mcNext();else if(n===1&&onStep2)mcBack();}
function mcReportH(){try{if(window.parent!==window)window.parent.postMessage({mcRealmH:document.body.scrollHeight},'*');}catch(e){}}
function mcMode(){const c=document.getElementById('r-mode').value==='create';document.getElementById('r-createonly').style.display=c?'block':'none';}
async function mcBrowse(){const m=document.getElementById('r-msg');m.textContent='opening picker…';
  try{const r=await(await fetch('/api/pick-folder')).json();if(r.ok&&r.path){document.getElementById('r-path').value=r.path;m.textContent='';}else{m.textContent=r.error||'pick a folder manually';}}catch(e){m.textContent='type the path manually';}}
function mcNext(){const m=document.getElementById('r-msg');const path=document.getElementById('r-path').value.trim();
  if(!mcReq(['r-name','r-path'])){m.textContent='';return;}
  if(document.getElementById('r-mode').value==='adopt'){mcFinish();return;}
  const p=MC_PRESETS[mcTpl];document.getElementById('r-agents-intro').textContent='Choose who staffs your '+p.collective+'. At least one is required, including the '+p.coordinator+'.';
  const box=document.getElementById('r-agents');box.innerHTML=p.agents.map((a,i)=>
    `<label class="mc-frame" style="display:flex;gap:10px;align-items:center;padding:8px 10px;border-radius:var(--r);margin-bottom:6px">
      <input type="checkbox" class="mc-preset" data-i="${i}" checked>
      <span style="font-family:var(--font-heading);font-weight:600;font-size:14px">${a.display}</span>
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-accent-700)">${a.role||''}</span>
      ${a.coordinator?'<span title="Coordinator agent" style="display:inline-flex;margin-left:auto;color:var(--color-accent-2)">'+window.mcIcon('laurel',16)+'</span>':''}</label>`).join('')
    ||'<div style="font-size:12px;color:var(--text-muted)">Blank template — add at least one agent below (the first becomes the coordinator).</div>';
  document.getElementById('wiz-1').style.display='none';document.getElementById('wiz-2').style.display='block';mcWizStep(2);mcReportH();}
function mcBack(){document.getElementById('wiz-2').style.display='none';document.getElementById('wiz-1').style.display='block';mcWizStep(1);mcReportH();}
function mcAddAgentRow(){const box=document.getElementById('r-agents');const d=document.createElement('div');
  d.className='mc-customagent';d.style.cssText='display:flex;gap:6px;margin-bottom:6px';
  d.innerHTML=`<input class="ca-name" placeholder="Name" style="flex:1;padding:5px 7px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text)">
    <input class="ca-role" placeholder="Role" style="flex:1;padding:5px 7px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text)">
    <label style="font-size:11px;display:flex;align-items:center;gap:4px"><input type="checkbox" class="ca-coord">coord</label>`;
  box.appendChild(d);}
async function mcFinish(){const m=document.getElementById('r-msg2')||document.getElementById('r-msg');
  const mode=document.getElementById('r-mode').value;
  const payload={mode,name:document.getElementById('r-name').value,template:mcTpl,icon:mcIcon,
    iconData:window.mcIconData||'',path:document.getElementById('r-path').value};
  if(mode==='create'){const p=MC_PRESETS[mcTpl];const agents=[];
    document.querySelectorAll('.mc-preset:checked').forEach(c=>agents.push(p.agents[+c.dataset.i]));
    document.querySelectorAll('.mc-customagent').forEach(d=>{const n=d.querySelector('.ca-name').value.trim();
      if(n)agents.push({display:n,role:d.querySelector('.ca-role').value,coordinator:d.querySelector('.ca-coord').checked});});
    if(!agents.length){m.textContent='add at least one agent';return;}
    if(!agents.some(a=>a.coordinator))agents[0].coordinator=true;
    payload.agents=agents;}
  m.textContent='working…';
  try{const r=await(await fetch('/api/new-realm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
    if(r.ok){const t=window.top||window;
      if(r.format_warning&&t.mcAlert)await t.mcAlert(r.format_warning,'Saved by a newer ARMADA');
      if(r.review&&t.mcAlert){const nc=(r.review.command_jobs||[]).length,na=r.review.agent_jobs||0;
        await t.mcAlert('It came with '+nc+' command job'+(nc===1?'':'s')+' and '+na+' agent job'+(na===1?'':'s')+
          '. They\u2019re paused until you\u2019ve looked at them \u2014 the Jobs page lists every command and lets you allow them.',
          'This realm\u2019s jobs are paused');}
      t.location.href='/switch?path='+encodeURIComponent(r.path);}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
document.addEventListener('DOMContentLoaded',()=>{const c=document.querySelector('.mc-tplcard[data-tpl="state"]');if(c)mcPickTpl(c);mcWizStep(1);mcReportH();});
window.addEventListener('load',mcReportH);
"""


def _widget_section_title(realm, wid: str) -> str:
    """A default nav title for a widget promoted to a section."""
    if wid == "register":
        return "Register"
    if wid == "usage":
        return "Usage"
    if wid == "jobcal":
        return "Job calendar"
    if wid.startswith("thread:"):
        p = wid.split(":", 2)
        if len(p) == 3:
            a = next((x for x in realm.agents if x.id == p[1]), None)
            thr = "Main" if p[2] == "main" else p[2].replace("-", " ").title()
            return (f"{a.display} · {thr}" if a else thr)
    return "Section"


def _render_widget_section(realm, realm_root, name, wid, dark=False) -> str:
    """Render a dashboard widget (register / usage / jobcal / a thread) as a full standalone page.
    The widget's own header becomes the page header; grip/⋮ chrome is dropped (section mode)."""
    realm_root = Path(realm_root)
    today = clock.today()
    # non-thread widgets render as a padded card with the widget JS bundle; a thread renders the full
    # Threads view (list + chat + context rail) full-bleed — a live shortcut to that specific thread.
    scripts = f"{_ICONS_JS}{_USAGE_JS}{_JOBCAL_JS}{_CHAT_JS}{_DOTPOLL_JS}"
    wrap_open = '<div style="flex:1;min-height:0;display:flex;flex-direction:column;padding:16px 24px 20px">'
    if wid == "register":
        content = _register(realm, realm_root, today, section=True)
    elif wid == "usage":
        content = _usage(realm, realm_root, today, section=True)
    elif wid == "jobcal":
        content = _jobcal(realm, realm_root, today, widget=False)
    elif wid.startswith("thread:"):
        p = wid.split(":", 2)
        a = next((x for x in realm.agents if x.id == p[1]), None) if len(p) == 3 else None
        if a:
            # focused thread view: chat + the right-side context rail only (no left thread list)
            agent_dir = realm_root / "agents" / a.id
            names, meta = _ordered_threads(agent_dir)
            thr = p[2] if p[2] in names else "main"
            _touch_last_thread(agent_dir, thr)
            _clear_thread_unread(agent_dir, thr, meta)   # opening the thread clears its unseen flag
            # avatar carrying its own live status dot, matching the thread widget's header
            lead = f'<span style="display:flex;flex:none;align-items:center">{_portrait(realm_root, a, 26, dot=True)}</span>'
            content = (f'<div style="display:grid;grid-template-columns:1fr 300px;height:100%;min-height:0">'
                       f'{_chat_center(realm_root, a, thr, embed=False, lead=lead)}{_thread_rail(realm_root, a, thr)}</div>')
            scripts = f"{_ICONS_JS}{_RUN_JS}{_CHAT_JS}{_AGENT_JS}{_FORM_JS}{_DOTPOLL_JS}"
            wrap_open = '<div style="flex:1;min-height:0">'                # full-bleed, no padding
        else:
            content = ('<div class="mc-widget" style="height:100%"><div style="padding:24px;font-size:13px;'
                       'color:var(--text-muted)">That agent or thread no longer exists.</div></div>')
    else:
        content = '<div style="padding:24px;font-size:13px;color:var(--text-muted)">Unknown widget.</div>'
    body_cls = "armada-dark" if dark else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{brand.NAME} — {E(name)}</title>
{_CSS_LINKS}{_theme_style()}</head>
<body class="{body_cls}"><div style="height:100vh;display:flex;flex-direction:column">
{_titlebar(realm)}{_nav(realm, name)}
{wrap_open}{content}</div>
</div>{scripts}</body></html>"""


def _load_dashboard(realm_root) -> dict:
    """Dashboard layout/state, persisted per realm (portable) in dashboard.json.
    Shape: {single:{id:bool}, order:[id], spans:{id:int}, heights:{id:px}, threads:[{agent,thread,...}]}."""
    p = Path(realm_root) / "dashboard.json"
    d = {"single": {}, "order": [], "spans": {}, "heights": {}, "threads": []}
    if p.exists():
        try:
            saved = json.loads(p.read_text(encoding="utf-8-sig"))
            if isinstance(saved, dict):
                d.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    for k, default in (("single", {}), ("order", []), ("spans", {}), ("heights", {}), ("threads", [])):
        if not isinstance(d.get(k), type(default)):
            d[k] = default
    # migrate widths from the old 4-column (25%) grid to the 20-column (5%) grid, once. Persist so the
    # ×5 conversion doesn't re-run on every load. New saves carry span_scale:20 already.
    if d.get("span_scale") != 20:
        d["spans"] = {k: max(1, min(20, int(v) * 5)) for k, v in d["spans"].items()
                      if isinstance(v, (int, float))}
        for w in d["threads"]:
            if isinstance(w, dict) and isinstance(w.get("span"), (int, float)):
                w["span"] = max(1, min(20, int(w["span"]) * 5))
        d["span_scale"] = 20
        # A render writing a file (4.3 L5): under the same lock _save_dashboard takes, and only if
        # the file on disk still needs it — a layout saved between our read and here must not be
        # overwritten with the stale copy we migrated.
        try:
            with util.file_lock(p):
                cur = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
                if not (isinstance(cur, dict) and cur.get("span_scale") == 20):
                    util.write_json_atomic(p, d)
        except (OSError, ValueError):
            log.debug("_load_dashboard: could not persist the span migration", exc_info=True)
    return d


