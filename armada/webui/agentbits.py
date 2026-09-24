"""Agent-rendering primitives (Layer 1, carved from _core.py in Phase 3).

Portraits/avatars, per-agent activity + status dots, model chips/marks, autonomy badges, run
history and the goals cell — shared by the Register, minister cards, goals and agent pages.
Imports only lower layers (never _core), so _core imports these names back without a cycle.
"""
from __future__ import annotations
import html, json, datetime, time, re
from pathlib import Path
from .. import memory, model, models, brand, status
from .. import goals as goalsmod
from ..icons import (ICONS, _icon, _ICONS_JS, _file_icon, _realm_icon, _REALM_ICON_NAMES, GRIP, CHEVR,
                     ICON_MISSED)
from ._base import E, _J, _FIELD, _LBL, _TA, _STAR, _md_inline, _md, _page_title, _mini_pill
from .consumption import (_MODEL_CLR, _MODEL_FALLBACK, _model_color, _MODEL_FAMILY_BASE,
    _CONSUMPTION_STOPS, _grad_rgb, _consumption_color, _consumption_gradient_css, _consumption_js,
    _model_is_claude)
from .schedfmt import (_DOW_NAME, _humanize, _cadence_bucket, _status_bucket, _STATUS_FILTERS,
    _CADENCE_FILTERS, _next_run_dt, _ordinal, _next_hint, _fmt_ts)
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


def _bust(size: int, coord: bool) -> str:
    bg = "var(--color-accent-2-100)" if coord else "var(--color-accent-100)"
    fg = "var(--color-accent-2)" if coord else "color-mix(in srgb,var(--color-accent) 75%,transparent)"
    # viewBox crops the icon's padding: figure reads centred, with a little top room so the head
    # doesn't touch the border, and the shoulders reaching the bottom edge.
    return (f'<svg width="{size}" height="{size}" viewBox="2 0.8 21 21" preserveAspectRatio="xMidYMax meet" style="display:block;background:{bg}">'
            f'<path fill="{fg}" d="M7.5 6.5C7.5 8.981 9.519 11 12 11s4.5-2.019 4.5-4.5S14.481 2 12 2S7.5 4.019 7.5 6.5M20 21h1v-1c0-3.859-3.141-7-7-7h-4c-3.86 0-7 3.141-7 7v1z"/></svg>')


def _avatar_file(realm_root, agent_id: str):
    d = Path(realm_root) / "agents" / agent_id
    for ext in ("png", "jpg", "jpeg", "webp", "gif"):
        f = d / f"avatar.{ext}"
        if f.exists():
            return f
    return None


def _colour_peek(size: int) -> int:
    """How far the colour disc sticks out past the avatar, in px.

    Fixed steps rather than a ratio: a proportional offset gives the 18px avatars in a goal list
    well under a pixel, and at 1px the crescent reads as a rendering artefact rather than as
    something anyone chose."""
    if size < 24:
        return 2
    return 3 if size < 40 else 4


def _status_dot_on_avatar(state: str, size: int, grow: int = 0) -> str:
    """The activity dot, sat on the avatar's lower-right corner.

    Its centre sits *on* the circle's edge, so half the dot hangs outside the picture. The 45° point
    of a circle is inset from the corner of its bounding box by (1 - cos45°)/2 ≈ 0.1464 of the
    diameter, so that's where the centre goes — which conveniently keeps the whole dot inside the
    square box, with nothing to clip."""
    col, pulse, label = _ACTIVITY_DOT.get(state, _ACTIVITY_DOT["idle"])
    d = max(6, round(size * 0.22)) + grow               # never so small it stops being a dot
    inset = max(0, round(size * 0.1464 - d / 2))        # centre on the perimeter, not inside it
    anim = "animation:mc-actwork 1.4s ease-in-out infinite;" if pulse else ""
    # The transition is what makes a state change read as the state changing rather than as the page
    # having been repainted — most visibly when an agent's output goes from unseen to read while
    # you're looking straight at it.
    return (f'<i class="mc-actdot" data-act="{state}" title="{E(label)}" style="position:absolute;'
            f'right:{inset}px;bottom:{inset}px;width:{d}px;height:{d}px;border-radius:50%;'
            f'transition:background-color .55s ease;background-color:{col};{anim}"></i>')


def _portrait(realm_root, a, size: int, color: str = "", dot: bool = False, dot_grow: int = 0) -> str:
    """An uploaded avatar image if present, else the generic bust.

    No border. The agent's colour is a filled disc behind the avatar, offset left so a crescent of
    it shows — 1px on the small inline avatars, 3px at card and header sizes.

    `dot=True` puts the agent's activity dot on the lower-right corner of the picture, the way chat
    apps do it, instead of floating beside the name somewhere else on the page. Off by default: it
    costs a filesystem check per avatar, and it's only wanted where the avatar stands for the agent
    as a whole — not on the 18px markers in a goal list. `dot_grow` nudges that dot a pixel or two
    where the proportional size lands badly; `color` forces a colour, for the Configure preview.
    """
    f = _avatar_file(realm_root, a.id)
    if f:
        t = int(f.stat().st_mtime)
        inner = (f'<img src="/avatar/{E(a.id)}?t={t}" width="{size}" height="{size}" '
                 f'style="width:100%;height:100%;object-fit:cover;display:block" alt="">')
    else:
        inner = _bust(size, a.is_coordinator)
    col = (color or _agent_stored_color(realm_root, a.id) or getattr(a, "color", "") or "").strip()
    peek = _colour_peek(size) if col else 0
    # The wrapper is WIDER than the avatar by the crescent, with the disc at its left edge and the
    # avatar pushed right — rather than the avatar filling the wrapper and the disc hanging out at a
    # negative offset. Several containers on the way up (the minister card's top row, the goal
    # chips) set overflow:hidden, and anything sticking out of the wrapper got sliced off there.
    # Nothing here escapes its own box, so nothing can clip it.
    av = (f'<span class="mc-av" style="position:absolute;top:0;left:{peek}px;box-sizing:border-box;'
          f'width:{size}px;height:{size}px;border-radius:50%;overflow:hidden">{inner}</span>')
    # Emitted first, so the avatar paints over it: between positioned elements at z-index:auto,
    # paint order is DOM order. Only the left crescent shows.
    disc = (f'<span aria-hidden="true" class="mc-avdisc" style="position:absolute;top:0;left:0;'
            f'width:{size}px;height:{size}px;border-radius:50%;background:{col}"></span>') if col else ""
    status, hook = "", ""
    if dot:
        status = _status_dot_on_avatar(_agent_activity(realm_root, a.id), size, dot_grow)
        hook = f' data-agentdot="{E(a.id)}"'      # the live poller repaints .mc-actdot inside this
    return (f'<span class="mc-avwrap" data-agent="{E(a.id)}"{hook} '
            f'style="position:relative;display:inline-block;flex:none;'
            f'width:{size + peek}px;height:{size}px;vertical-align:top">{disc}{av}{status}</span>')


def _runs(realm_root: Path, agent_id: str) -> list[dict]:
    rf = realm_root / "agents" / agent_id / "runs" / f"{agent_id}.jsonl"
    out = []
    if rf.exists():
        for ln in rf.read_text(encoding="utf-8-sig").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


def _health7(runs: list[dict], today: datetime.date) -> list[str]:
    """7 colour cells, oldest→newest, from run-reports."""
    by_day: dict[str, list[str]] = {}
    for ev in runs:
        d = str(ev.get("ts", ""))[:10]
        if d:
            by_day.setdefault(d, []).append(str(ev.get("status", "ok")).lower())
    cells = []
    for i in range(6, -1, -1):
        d = (today - datetime.timedelta(days=i)).isoformat()
        st = by_day.get(d)
        norms = [status.normalize(s) for s in st] if st else []
        if not st:
            cells.append("var(--color-neutral-300)")           # missed / no run
        elif status.FAILED in norms:
            cells.append("var(--status-bad)")
        elif status.WARN in norms:
            cells.append("var(--status-warn)")
        else:
            cells.append("var(--color-accent-2)")               # ok
    return cells


def _running_markers(realm_root, agent_id: str) -> set:
    """Stems of fresh .running markers (jobs *and* the reserved '_chat' interactive-run marker)."""
    d = Path(realm_root) / "agents" / agent_id / "runs" / ".running"
    out = set()
    if d.is_dir():
        cutoff = time.time() - 30 * 60          # ignore stale markers (crashed runs)
        for p in d.glob("*.json"):
            try:
                if p.stat().st_mtime >= cutoff:
                    out.add(p.stem)
            except OSError:
                pass
    return out


def _agent_busy(realm_root, agent_id: str) -> bool:
    """True if the agent is actively running anything right now — a scheduled job or a live chat."""
    return bool(_running_markers(realm_root, agent_id))


def _chat_running(realm_root, agent_id: str, thread: str) -> bool:
    """Is a live chat turn running in THIS thread right now?

    The marker is one file per agent, because the activity dot only asks whether the agent is
    busy at all. A transcript asks a narrower question: without the thread name, opening any
    thread while the agent worked in another would show a spinner under a turn that was finished
    days ago. Same staleness cut-off as the dot — a crashed run stops claiming to be running.
    """
    p = Path(realm_root) / "agents" / agent_id / "runs" / ".running" / "_chat.json"
    try:
        if p.stat().st_mtime < time.time() - 30 * 60:
            return False
        got = json.loads(p.read_text(encoding="utf-8-sig")).get("thread")
    except (OSError, ValueError):
        return False
    # A marker written before this carried a thread name means "some chat is running". Treating
    # that as the thread you are looking at is the friendlier miss: a spinner that resolves on the
    # next poll beats a reply that arrives with no sign anything was happening.
    return got is None or str(got) == str(thread)


def _has_pending_proposals(realm_root, agent_id: str) -> bool:
    """True if the agent has job proposals sitting in _pending, awaiting the owner's approval."""
    from .. import jobs as _jobs_mod
    pd = Path(realm_root) / "agents" / agent_id / "jobs" / _jobs_mod.PENDING
    return pd.is_dir() and any(pd.glob("*.json"))


def _agent_has_unread(realm_root, agent_id: str) -> bool:
    """True if any of the agent's threads is flagged unread (unseen output)."""
    meta = _thread_meta(Path(realm_root) / "agents" / agent_id)
    return any(bool(v) for v in (meta.get("unread") or {}).values())


def _agent_activity(realm_root, agent_id: str) -> str:
    """Live activity state for the status dot, highest-priority first:
      working  — a run is executing right now (.running marker)
      input    — the agent has a job proposal awaiting the owner's approval
      unseen   — the agent has output in a thread the owner hasn't marked read
      idle     — nothing pending."""
    if _agent_busy(realm_root, agent_id):
        return "working"
    if _has_pending_proposals(realm_root, agent_id):
        return "input"
    if _agent_has_unread(realm_root, agent_id):
        return "unseen"
    return "idle"


# Mixed against --color-bg, not transparent. These were semi-transparent while the dot sat on the
# page background, where that made no visible difference. It makes two now: on an avatar the photo
# shows through, and a semi-transparent colour can't be animated smoothly — the pulse degraded into
# a flip between two flat values. Opaque colours interpolate, so the pulse is a pulse again.
_ACTIVITY_DOT = {
    "working": ("color-mix(in srgb,var(--color-text) 55%,var(--color-bg))", True,  "Working…"),
    "input":   ("var(--status-warn)",                                       False, "Needs input"),
    "unseen":  ("var(--color-accent-2)",                                     False, "Unseen output"),
    "idle":    ("color-mix(in srgb,var(--color-text) 20%,var(--color-bg))", False, "Idle"),
}


def _activity_dot(state: str, size: int = 8) -> str:
    """A free-standing status dot. Nothing renders one any more — the dot lives on the avatar's
    corner now (see _status_dot_on_avatar) — but it stays exported because several modules import
    it, and it's the obvious thing to reach for if a dot is ever needed away from an avatar."""
    col, pulse, label = _ACTIVITY_DOT.get(state, _ACTIVITY_DOT["idle"])
    anim = "animation:mc-actwork 1.4s ease-in-out infinite;" if pulse else ""
    return (f'<i class="mc-actdot" data-act="{state}" title="{E(label)}" style="display:inline-block;'
            f'width:{size}px;height:{size}px;border-radius:50%;flex:none;background:{col};{anim}"></i>')


def _goals_cell(realm_root, a) -> str:
    """Goals column: just the count of goals this agent advances (the titles live in the tooltip)."""
    gs = goalsmod.goals_for_agent(realm_root, a.id, is_coord=a.is_coordinator)
    if not gs:
        return '<span style="font-size:11px;color:var(--text-muted)">—</span>'
    tip = f"{len(gs)} goal{'s' if len(gs) != 1 else ''} assigned to {a.display}"
    return (f'<span title="{E(tip)}" style="display:inline-flex;align-items:center;gap:6px;font-size:12px;'
            f'padding:2px 9px;border-radius:10px;background:var(--text-6);'
            f'white-space:nowrap"><span style="display:flex;color:var(--text-muted)">{_icon("target", 12)}</span>{len(gs)}</span>')


def _jobs_cell(a) -> str:
    """Jobs column, built like the Goals one beside it — a bare digit next to a pill read as a
    different kind of fact. Counts jobs that are on, which is the number that decides anything."""
    n = sum(1 for j in (getattr(a, "jobs", []) or []) if getattr(j, "enabled", True))
    if not n:
        return '<span style="font-size:11px;color:var(--text-muted)">—</span>'
    total = len(getattr(a, "jobs", []) or [])
    tip = (f"{n} active job{'s' if n != 1 else ''}"
           + (f" of {total}" if total != n else "") + f" owned by {a.display}")
    return (f'<span title="{E(tip)}" style="display:inline-flex;align-items:center;gap:6px;font-size:12px;'
            f'padding:2px 9px;border-radius:10px;background:var(--text-6);'
            f'white-space:nowrap"><span style="display:flex;color:var(--text-muted)">{_icon("clock-play", 12)}</span>{n}</span>')


def _pretty_model(m) -> str:
    """Concrete model id → versioned label, e.g. 'claude-opus-4-8' → 'Opus 4.8',
    'claude-sonnet-4-5-20250929' → 'Sonnet 4.5', 'claude-opus-5' → 'Opus 5'. Version digits after
    the family are joined with '.', stopping at a date stamp (≥6 digits). Family-only ids ('opus')
    stay 'Opus'. Keeps the exact version so the by-model split distinguishes e.g. Opus 4.7 vs 4.8."""
    d = (m or "").strip().lower()
    if not d:
        return "Unknown"
    if d.startswith("mock"):
        return "Mock (offline)"
    fam = next((f for f in ("opus", "sonnet", "haiku", "fable") if f in d), "")
    if not fam:
        return str(m)
    nums = []
    for tok in re.split(r"[-_.]+", d.split(fam, 1)[1]):
        if tok.isdigit() and len(tok) < 6:
            nums.append(tok)
        elif tok:                      # non-numeric or a date stamp → version part is over
            break
    return fam.capitalize() + (" " + ".".join(nums) if nums else "")


def _model_chip_label(value: str) -> tuple[bool, str]:
    """A stored model value (concrete id 'claude-opus-5' or old label 'Claude Opus 5') →
    (is_claude, friendly label 'Claude Opus 5') for the model chips, so the icon + name always show."""
    m = (value or "").strip()
    if not m:
        return (False, "—")
    if not _model_is_claude(m):
        return (False, m)
    if " " in m and not m.lower().startswith("claude-"):
        return (True, m)                                  # already a friendly label
    return (True, f"Claude {_pretty_model(m)}")           # concrete id / bare family → prettify


def _agent_stored_color(realm_root, agent_id: str) -> str:
    """The agent's chosen colour from agent.json ('' if none/unreadable)."""
    try:
        ac = json.loads((Path(realm_root) / "agents" / agent_id / "agent.json").read_text("utf-8-sig"))
        return (ac.get("color") or "").strip()
    except Exception:  # noqa
        swallowed(log, '_agent_stored_color: failed; returning a fallback')
        return ""


def _thread_meta(agent_dir) -> dict:
    f = Path(agent_dir) / "threads" / "meta.json"
    d = {"titles": {}, "pinned": {}, "unread": {}, "order": []}
    if f.exists():
        try:
            d.update(json.loads(f.read_text(encoding="utf-8-sig")))
        except (json.JSONDecodeError, OSError):
            pass
    return d


_AUTONOMY_MODES = [
    ("manual", "Manually approve everything", "hand", "You approve every action before it runs.",
     "var(--status-ok)", "User manually approves all actions"),
    ("auto", "Auto-approve routine actions", "circle-check",
     "Routine actions auto-approved, sensitive ones require manual approval.",
     "var(--status-warn)", "Only routine actions auto-approved"),
    ("skip", "Skip all approvals", "zap", "Full autonomy, nothing pauses for approval.",
     "var(--status-bad)", "All actions auto-approved"),
]
_AUTONOMY_ALIAS = {"propose": "manual", "act_folder": "auto", "act_connectors": "auto", "autonomous": "skip"}
_AUTONOMY_META = {v: (ic, title, color, hover) for v, title, ic, desc, color, hover in _AUTONOMY_MODES}


def _autonomy_of(realm_root, aid: str) -> str:
    p = Path(realm_root) / "agents" / aid / "agent.json"
    v = ""
    if p.exists():
        try:
            v = (json.loads(p.read_text(encoding="utf-8-sig")).get("autonomy") or "")
        except json.JSONDecodeError:
            pass
    return _AUTONOMY_ALIAS.get(v, v) or "manual"


def _autonomy_badge(mode: str, size: int = 14) -> str:
    ic, title, color, hover = _AUTONOMY_META.get(mode, _AUTONOMY_META["manual"])
    return (f'<span title="{E(hover)}" style="display:inline-flex;align-items:center;'
            f'color:{color}">{_icon(ic, size)}</span>')


def _agent_model_effort(realm, realm_root, aid: str):
    ac = {}
    p = Path(realm_root) / "agents" / aid / "agent.json"
    if p.exists():
        try:
            ac = json.loads(p.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            pass
    model = ac.get("model") or getattr(realm, "default_model", "") or "Claude Opus 4.8"
    effort = ac.get("effort") or getattr(realm, "default_effort", "") or "high"
    return model, effort


def _model_mark(model_value: str, size: int = 12, effort: str = "") -> str:
    """The Claude mark for a model chip, tinted by token-consumption on the shared gradient. With an
    `effort`, the tint reflects the model+effort combo (agents); without it, the model alone (Usage
    breakdown). '' for non-Claude models."""
    if not _model_is_claude(model_value):
        return ""
    idx = models.combo_index(model_value, effort) if effort else models.model_index(model_value)
    col = _consumption_color(idx)
    return (f'<span class="mc-modelmark" data-model="{E(model_value)}" data-effort="{E(effort or "")}" '
            f'style="display:inline-flex;color:{col}">{_icon("claude", size)}</span>')


def _model_chip(model: str, effort: str, size: int = 12) -> str:
    # Same pill style as the agent overview header (grey fill, rounded, Claude mark tinted by consumption).
    is_claude, disp = _model_chip_label(model)
    label = f"{disp} · {effort}"
    mark = _model_mark(model, size, effort)
    return (f'<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:var(--r);'
            f'background:var(--text-7);font-size:11px;'
            f'color:var(--text-strong)">{mark}<span>{E(label)}</span></span>')


# --------------------------------------------------------------------------- job files + health
# These moved down from agentcommon/realmpages/widgets so the Register widget and the agent cards
# can show the same seven squares the Jobs list shows. agentbits is the lowest layer all three
# import, so this is the only place the code can live without a cycle.

def _running_jobs(realm_root, agent_id: str) -> set:
    """Job ids with an in-progress run. Excludes reserved '_'-prefixed markers (e.g. '_chat', the
    interactive-chat marker) so they never masquerade as a running scheduled job."""
    return {s for s in _running_markers(realm_root, agent_id) if not s.startswith("_")}


def _job_prompt(realm_root, agent_id: str, job_id: str) -> dict:
    p = Path(realm_root) / "agents" / agent_id / "jobs" / f"{job_id}.json"
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}


def _job_created(realm_root, agent_id: str, job_id: str, jc: dict) -> str:
    if jc.get("created"):
        return str(jc["created"])[:10]
    p = Path(realm_root) / "agents" / agent_id / "jobs" / f"{job_id}.json"
    try:
        return datetime.date.fromtimestamp(p.stat().st_mtime).isoformat()
    except OSError:
        return ""


def _job_created_ts(realm_root, agent_id: str, job_id: str, jc: dict) -> str:
    """When the job came into being, to the minute where we can tell.

    The health strip needs this rather than the date, because a job written at two in the afternoon
    should not be shown as having missed its nine o'clock. The file's mtime is the only signal we
    have and it moves on every edit, which errs the safe way: after you change a schedule, the days
    before the change are not judged against the new one.

    Retirement pushes this forward the same way. A job whose owner spent a fortnight retired did
    not miss fourteen fire times — it wasn't due, because its agent wasn't here. Without this an
    agent back from leave arrives wearing a fortnight of red, from two true statements ("the cron
    says 09:00", "nothing ran") that add up to a false one."""
    born = str(jc.get("created") or "")
    if not born:
        p = Path(realm_root) / "agents" / agent_id / "jobs" / f"{job_id}.json"
        try:
            born = datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat()
        except OSError:
            born = ""
    try:
        from .. import agentops
        back = agentops.reinstated_at(realm_root, agent_id)
    except Exception:  # noqa — never let this break a job row
        swallowed(log, '_job_created_ts: failed; using a default')
        back = ""
    if not back:
        return born
    if not born:
        return back
    # Parsed, not string-compared: these two come from different places and carry different
    # precision and offsets. '…T13:32:36+02:00' and '…T13:32:36.015881+01:00' do not order as
    # text. A stamp we can't parse falls back to the birth date, which is the safe direction —
    # it can only show more history, never invent a missed day.
    def _dt(s):
        try:
            d = datetime.datetime.fromisoformat(str(s))
            return d if d.tzinfo else d.astimezone()
        except ValueError:
            return None
    b, r = _dt(born), _dt(back)
    if b is None or r is None:
        return born
    return back if r > b else born


_RUNNING_COLOR = "var(--color-accent-2)"                                            # theme teal
_UNSCHEDULED_COLOR = "var(--text-8)"
_HEALTH_STYLES = {
    "Success":       "background:color-mix(in srgb,var(--status-ok) 22%,var(--color-bg))",   # light green
    "Running":       f"background:{_RUNNING_COLOR}",                                          # theme teal
    "Scheduled":     "background:transparent;border:1.5px solid var(--color-accent-2)",       # hollow teal
    "Warning":       "background:color-mix(in srgb,var(--status-warn) 30%,var(--color-bg))",  # lighter orange
    "Failed":        "background:color-mix(in srgb,var(--status-bad) 20%,var(--color-bg))",   # light red
    # Missed also draws a ✕ (see _health_square) — against "Not scheduled" a grey a shade darker
    # was not a difference anyone could read without the legend open beside them.
    "Missed":        "background:color-mix(in srgb,var(--status-bad) 10%,transparent)",
    "Not scheduled": f"background:{_UNSCHEDULED_COLOR}",
}
_HEALTH_LEGEND_ORDER = ["Success", "Running", "Scheduled", "Warning", "Failed", "Missed", "Not scheduled"]


def _health_swatch(label: str, size: int = 10, cls: str = "") -> str:
    """One status, at legend size. The single definition of what a status LOOKS like when it isn't
    a day in a strip — used by the legend and by the status filter's dropdown, which had its own
    flat-colour table and so was still showing the palette from two revisions ago."""
    from ..icons import ICON_MISSED
    c = f' class="{cls}"' if cls else ""
    # Missed is a glyph in the strip, so it has to be the same glyph here — a legend or a menu
    # showing a swatch for a mark the row draws differently is worse than showing nothing.
    if label == "Missed":
        return (f'<i{c} style="width:{size}px;height:{size}px;display:inline-flex;flex:none;'
                f'color:var(--status-bad)">{ICON_MISSED.format(s=size)}</i>')
    return (f'<i{c} style="width:{size}px;height:{size}px;border-radius:2px;box-sizing:border-box;'
            f'flex:none;display:inline-block;{_HEALTH_STYLES.get(label, "")}"></i>')



def _filter_dropdown(fid: str, default_label: str, options, width: str = "", onpick: str = "mcJobsFilter") -> str:
    """A custom dropdown matching the realm switcher: a pill <summary> + a <details> menu.
    options: list of (value, label, status|"") — a status renders the legend's own swatch next to
    the option, and the same swatch next to the summary once selected. `width` fixes the control's
    width so it doesn't resize when a shorter option is chosen (the label ellipsizes instead).
    `onpick` is the JS function (by name) called after a selection — so the same dropdown drives
    different lists."""
    has_swatch = any(st for _v, _l, st in options)
    rows = ""
    for val, label, st in options:
        if st:
            dot = _health_swatch(st, cls="mc-fdrop-dot")
        elif has_swatch:
            dot = '<span class="mc-fdrop-dot" style="background:transparent"></span>'   # keep labels aligned
        else:
            dot = ""
        # The swatch travels in the markup rather than as an argument: it is now a fill, a border
        # or an SVG depending on the status, none of which survives being passed as a colour
        # string through an onclick attribute.
        # data-val as well as the onclick: anything that wants to know what a row stands for
        # (the Catalogue greys the ones that would return nothing) reads the attribute rather
        # than picking the argument back out of a string of JavaScript.
        rows += (f'<a data-val="{E(val)}" '
                 f'onclick="mcFDPick(this,\'{fid}\',{_J(val)},{_J(label)},\'{onpick}\')">'
                 f'{dot}{E(label)}</a>')
    sw = '<span class="mc-fdrop-sw" style="display:none"></span>'
    wstyle = f' style="width:{width}"' if width else ""
    return (f'<details class="mc-fdrop" id="{fid}" data-val="" data-default="{E(default_label)}"{wstyle}>'
            f'<summary>{sw}<span class="mc-fdrop-lbl">{E(default_label)}</span>{CHEVR}</summary>'
            f'<div class="mc-fdrop-menu">{rows}</div></details>')


def _health_legend_chips(exclude=()) -> str:
    """The shared status swatches (Jobs list legend + Job-calendar widget). Each swatch uses the
    same styling as the health squares — including the faint, border-less 'Not scheduled' fill.
    `exclude` drops states that don't apply to a given view (e.g. 'Not scheduled' on a calendar,
    which shows occurrences per day, not per job)."""
    chips = ""
    for label in _HEALTH_LEGEND_ORDER:
        if label in exclude:
            continue
        chips += (f'<span style="display:inline-flex;align-items:center;gap:5px;font-size:11px;white-space:nowrap;'
                  f'color:var(--text-dim)">'
                  f'{_health_swatch(label)}{label}</span>')
    return chips


def _health_square(label: str, tooltip: str, size: int = 11, margin: bool = True) -> str:
    """One day. Missed is a circled ✕ glyph rather than a shade of grey.

    Missed and Not scheduled were two faint greys a shade apart, so the one that means "this should
    have run and didn't" looked like the one that means "nothing was due". A mark you can see at a
    glance is the difference between a legend you have to consult and a row you can read."""
    if label == "Missed":
        return (f'<i title="{E(tooltip)}" style="display:inline-flex;width:{size}px;height:{size}px;'
                f'box-sizing:border-box;{"margin-right:2px;" if margin else ""}'
                f'color:var(--status-bad)">{ICON_MISSED.format(s=size)}</i>')
    return (f'<i title="{E(tooltip)}" style="display:inline-block;width:{size}px;height:{size}px;border-radius:2px;'
            f'box-sizing:border-box;{"margin-right:2px;" if margin else ""}{_HEALTH_STYLES.get(label, "")}"></i>')


# The week is centred on today: three days behind, today, three ahead. A trailing week answered
# "how has it been going", which you can also get from the last-run column; the centred one also
# answers "what is coming", so the same seven squares carry both the log and the plan.
_WEEK_BACK, _WEEK_FWD = 3, 3


def _job_health7(jruns, cadence, now, running: bool = False, since: str = "",
                 back: int = _WEEK_BACK, fwd: int = _WEEK_FWD):
    """Per-day health for one job across a window, oldest→newest, schedule-aware:
    (weekday_full, 'DD Mon', status_label, is_weekend).

    Past days: Success/Warning/Failed if a run recorded one, Missed if it was due and nothing ran,
    else Not scheduled. Today: Running if a run is in progress, the recorded status if one has run,
    Scheduled if a fire time is still ahead, Missed if the time passed with nothing. Future days:
    Scheduled if due, Not scheduled otherwise — a day that has not happened cannot be missed, which
    is the bug you get if you extend the window without touching this branch.

    `since` (ISO date or timestamp for when the job came into being) guards the other end: a job
    cannot have missed a fire time that fell before it existed. Without it, every newly written job
    appeared with a row of red marks over a run history saying "no runs yet" — two true statements
    that together read as a fault. It is applied per fire time rather than per day, because a job
    written this afternoon should not be marked as having missed this morning either.

    `back`/`fwd` size the window. It defaults to the Jobs list's centred week; the agent rollup
    asks for a trailing one. The callers that zip this onto their own list of dates need the two
    windows to be the same length AND the same days — pasting a centred week onto a trailing one
    labelled last Wednesday with next Wednesday's status."""
    from .. import scheduler as S
    today = now.date()
    since_dt = None
    if since:
        try:
            since_dt = datetime.datetime.fromisoformat(
                since if "T" in since else since + "T00:00:00")
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=now.tzinfo)
        except ValueError:
            since_dt = None
    cron = cadence if (cadence and cadence != "manual" and S.is_cron(cadence)) else ""
    by_day: dict[str, list[str]] = {}
    for ev in jruns:
        d = str(ev.get("ts", ""))[:10]
        if d:
            by_day.setdefault(d, []).append(str(ev.get("status", "ok")).lower())
    out = []
    for i in range(-back, fwd + 1):
        d = today + datetime.timedelta(days=i)
        st = by_day.get(d.isoformat())
        times = S.cron_day_times(cron, d) if cron else []
        if running and d == today:
            label = "Running"
        elif st:
            norms = [status.normalize(s) for s in st]
            if status.FAILED in norms:
                label = "Failed"
            elif status.WARN in norms:
                label = "Warning"
            else:
                label = "Success"
        elif times:
            fires = [datetime.datetime.combine(d, datetime.time(h, m), tzinfo=now.tzinfo)
                     for h, m in times]
            if since_dt:
                fires = [f for f in fires if f >= since_dt]   # before the job existed: nothing due
            if not fires:
                label = "Not scheduled"
            elif d > today or any(f > now for f in fires):
                label = "Scheduled"
            else:
                label = "Missed"
        else:
            label = "Not scheduled"
        out.append((d.strftime("%A"), d.strftime("%d %b"), label, d.weekday() >= 5))
    return out


def _sysjob_health7(runs, now, enabled: bool = True,
                    back: int = _WEEK_BACK, fwd: int = _WEEK_FWD):
    """The same week strip, for a job that runs on an INTERVAL rather than at a time of day.

    The difference is Missed, and it matters. A cron job has fire times, so a time that passed with
    nothing recorded is a miss. An interval job has none — "every 30 minutes" cannot be late, it
    just runs when the scheduler next comes round — so a past day with no record means we have no
    record, not that something went wrong. Marking those red would put a row of failures against
    every job on a machine that was simply switched off over the weekend.

    So: past days take the worst recorded status, or 'Not scheduled' when nothing was recorded.
    Today and the days ahead read 'Scheduled' while the job is on, because an interval job is
    always going to run again, and 'Not scheduled' when it is off.
    """
    today = now.date()
    by_day: dict[str, list[str]] = {}
    for ev in (runs or []):
        d = str((ev or {}).get("ts", ""))[:10]
        if d:
            by_day.setdefault(d, []).append(str(ev.get("status", "ok")).lower())
    out = []
    for i in range(-back, fwd + 1):
        d = today + datetime.timedelta(days=i)
        st = by_day.get(d.isoformat())
        if st:
            norms = [status.normalize(s) for s in st]
            label = ("Failed" if status.FAILED in norms
                     else "Warning" if status.WARN in norms else "Success")
            # Today can hold both: a run that already happened AND another one still coming. The
            # recorded outcome wins — it is the thing that has actually been observed.
        elif not enabled:
            label = "Not scheduled"
        elif d >= today:
            label = "Scheduled"
        else:
            label = "Not scheduled"
        out.append((d.strftime("%A"), d.strftime("%d %b"), label, d.weekday() >= 5))
    return out


# Today plus the three days before it. The strip is a centred week, so half of it is the future —
# and "show me the failed jobs" is a question about what has happened, not what is booked.
_FILTER_BACK_DAYS = 4

_WEEK_BUCKET = {"Success": "success", "Running": "running", "Warning": "warning",
                "Failed": "failed", "Missed": "none"}


def _week_filter_bucket(week, back: int = _WEEK_BACK, days: int = _FILTER_BACK_DAYS) -> str:
    """The status bucket the filters should match, read from the week strip the row already draws.

    The bug this replaces: the bucket came from `last_status`, the outcome of the most recent
    recorded run. Four jobs that had never run all had no last status, all fell through to the
    same default, and all matched "Missed" — while the strip beside them showed two of the four
    as missed and the other two as never having been due. One word, two definitions, a centimetre
    apart; filtering on it returned the whole list.

    So the filter now reads the strip. Scheduled and Not scheduled are skipped: they are not
    outcomes, they say a day has nothing to report, and a row whose recent days are all one of
    those has no status to filter on — it matches nothing rather than matching Missed.
    """
    window = week[max(0, back - days + 1):back + 1]
    for _day, _dt, label, _wknd in reversed(window):
        if label in _WEEK_BUCKET:
            return _WEEK_BUCKET[label]
    return ""


_COORD_TIP = ("A coordinator agent has realm-wide visibility and is added automatically to "
              "every goal.")


def _coord_mark(size: int = 15, tip: bool = False) -> str:
    """The coordinator's laurel, for beside an agent's name.

    Said as a glyph rather than as the word "coordinator" in a pill: the role is a property of the
    agent, it appears in four different lists, and a word-shaped label in each of them competes for
    the width that the name, the model and the week strip already want. `tip` adds the longer
    hover explaining what the role means — worth it where the reader is choosing, and noise where
    they are only scanning.
    """
    extra = f' class="mc-tip" data-tip="{E(_COORD_TIP)}"' if tip else ""
    return (f'<span{extra} title="Coordinator agent" aria-label="Coordinator agent" '
            f'style="display:inline-flex;flex:none;align-items:center;color:var(--color-accent-2);'
            f'cursor:help">{_icon("laurel", size)}</span>')


def _health7_header(today) -> str:
    """The day-initials over the health squares, today marked so the split between what happened
    and what is coming is visible without counting."""
    cells = ""
    for i in range(-_WEEK_BACK, _WEEK_FWD + 1):
        d = today + datetime.timedelta(days=i)
        is_today = i == 0
        dim = "90" if is_today else ("32" if d.weekday() >= 5 else "60")
        deco = "border-bottom:1.5px solid var(--color-accent-2);" if is_today else ""
        cells += (f'<span title="{d.strftime("%A")}{" · today" if is_today else ""}" '
                  f'style="display:inline-block;width:11px;margin-right:2px;{deco}'
                  f'text-align:center;font-size:9.5px;font-weight:{"700" if is_today else "600"};line-height:1;'
                  f'color:color-mix(in srgb,var(--color-text) {dim}%,transparent)">{d.strftime("%a")[0]}</span>')
    return cells


def _status_legend() -> str:
    return (f'<div style="display:flex;align-items:center;gap:13px;flex-wrap:wrap">'
            f'<span style="font-size:10px;letter-spacing:.04em;text-transform:uppercase;'
            # What the strip actually covers, rather than a label that could mean either. This
            # week is centred on today: three days of what happened, then three of what is due.
            f'color:var(--text-42)">'
            f'-/+3D job outcome and outlook</span>{_health_legend_chips()}</div>')


# The order the rollup below reads as "worst". Missed and Failed are things that went wrong and the
# day should say so; Warning is a run that finished but complained; Running is happening now. Then
# Success — a day that has already produced a good run is worth more than one merely pencilled in —
# then Scheduled, then nothing due at all. One agent, one square per day, so the square has to pick.
_HEALTH_WORST = ["Missed", "Failed", "Warning", "Running", "Success", "Scheduled", "Not scheduled"]
_HEALTH_RANK = {label: i for i, label in enumerate(_HEALTH_WORST)}


# What a square means, said as a sentence about a job rather than as a bare adjective. "Scheduled"
# next to a date reads as a property of the date; "Job scheduled" says what is actually being
# reported. Used in the tooltips on every strip.
_HEALTH_PHRASE = {
    "Success": "Job succeeded", "Running": "Job running", "Scheduled": "Job scheduled",
    "Warning": "Job warning", "Failed": "Job failed", "Missed": "Job missed",
    "Not scheduled": "No job scheduled",
}


def _health_styles_js() -> str:
    """The status styles and phrasings, handed to the browser.

    One definition of what "Failed" looks like. The client repaints a square after a system job is
    run or switched, and a second copy of these colours in JavaScript is a second copy that drifts
    — the legend and the strip disagreeing about a colour is exactly the kind of thing nobody
    notices until they are trying to read a row.
    """
    import json as _json
    return (f"<script>window.MC_HEALTH={_json.dumps(_HEALTH_STYLES)};"
            f"window.MC_HEALTH_PHRASE={_json.dumps(_HEALTH_PHRASE)};</script>")


def _agent_health7(realm_root, a, now, back: int = 6, fwd: int = 0):
    """The agent's week: per day, the worst status across every job it owns.

    Same labels the Jobs list uses, compacted from N jobs to one row — an agent's card cannot show
    a strip per job, and the question it answers is "is anything wrong over there", which is the
    worst case, not the average.

    The window defaults to the trailing seven days, because on a card and in the Register this is a
    log: it says what happened. The Jobs list centres its week on today and carries the schedule
    ahead as well, but there each strip belongs to one job whose next run you can act on."""
    realm_root = Path(realm_root)
    jobs = list(getattr(a, "jobs", []) or [])
    today = now.date()
    days = [today + datetime.timedelta(days=i) for i in range(-back, fwd + 1)]
    if not jobs:
        return [(d.strftime("%A"), d.strftime("%d %b"), "Not scheduled", d.weekday() >= 5)
                for d in days]
    runs_all = _runs(realm_root, a.id)
    running = _running_jobs(realm_root, a.id)
    worst = ["Not scheduled"] * len(days)
    for j in jobs:
        if not getattr(j, "enabled", True):
            continue                      # a job that is off is not due, so it cannot be missed
        jc = _job_prompt(realm_root, a.id, j.id)
        jruns = [ev for ev in runs_all if ev.get("task") == j.id]
        week = _job_health7(jruns, j.cadence, now, j.id in running,
                            since=_job_created_ts(realm_root, a.id, j.id, jc),
                            back=back, fwd=fwd)
        for i, (_day, _dt, label, _wknd) in enumerate(week):
            if _HEALTH_RANK.get(label, 99) < _HEALTH_RANK.get(worst[i], 99):
                worst[i] = label
    return [(d.strftime("%A"), d.strftime("%d %b"), worst[i], d.weekday() >= 5)
            for i, d in enumerate(days)]


def _agent_week_strip(realm_root, a, now, size: int = 11, back: int = 6, fwd: int = 0) -> str:
    """The rendered strip — squares only; the caller decides what to label it with."""
    n = sum(1 for j in (getattr(a, "jobs", []) or []) if getattr(j, "enabled", True))
    return "".join(
        _health_square(label, _health_tip(day, dt, label, wknd, no_jobs=not n), size=size)
        for day, dt, label, wknd in _agent_health7(realm_root, a, now, back=back, fwd=fwd))


def _health_tip(day, dt, label, wknd, no_jobs: bool = False) -> str:
    """'Friday 18 Sep · Job scheduled'. The bare adjective read as a property of the date."""
    return (f'{day} {dt} · {_HEALTH_PHRASE.get(label, label)}'
            f'{" · weekend" if wknd else ""}{" · no jobs" if no_jobs else ""}')
