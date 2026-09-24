"""ARMADA cockpit renderer — Realm model -> self-contained cockpit.html.

Read-only in v0.1 (P1): it shows the realm, its agents, the jobs each owns, health,
run volume, and the gaps ARMADA would formalize. Light ARMADA-branded theme.
"""
from __future__ import annotations
import base64, html
from pathlib import Path
from .model import Realm, Agent

NAVY, TEAL, INK, BG, CARD, LINE, DIM = "#0b3f86", "#12a3b8", "#1f2a37", "#eef1f5", "#ffffff", "#e2e8f0", "#6b7688"
STATUS = {  # bulletin status -> (bg, fg, label)
    "green": ("#e4f6ec", "#1f9d57", "GREEN"), "yellow": ("#fdf3d8", "#b7860f", "YELLOW"),
    "red": ("#fbe4e4", "#d64545", "RED"), "planned": ("#eceff3", "#6b7688", "PLANNED"),
    "unknown": ("#eceff3", "#6b7688", "—"),
}
JOB = {  # last_status -> (glyph, color, word)
    "ok": ("●", "#1f9d57", "ran"), "quiet": ("●", "#1f9d57", "ran (quiet)"),
    "warn": ("▲", "#d9a218", "issues"), "warning": ("▲", "#d9a218", "issues"),
    "issues": ("▲", "#d9a218", "issues"), "error": ("✕", "#d64545", "error"),
    None: ("○", "#9aa4b2", "no telemetry"),
}
E = html.escape
SCOPE_BG = {"files": "#e8eefb", "network": "#fdeee0", "connectors": "#e9f6ee", "shell": "#fbe4e4"}


def _logo_b64() -> str:
    p = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
    try:
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    except OSError:
        return ""


def _pill(status: str) -> str:
    bg, fg, label = STATUS.get(status, STATUS["unknown"])
    return f'<span class="pill" style="background:{bg};color:{fg}">{E(label)}</span>'


def _jobs_table(a: Agent) -> str:
    if not a.jobs:
        return '<p class="dim">No jobs.</p>'
    rows = []
    for j in a.jobs:
        g, c, w = JOB.get(j.last_status, JOB[None])
        seen = f' · {E(j.last_seen)}' if j.last_seen else ""
        tag = ' <span class="jtag" title="deterministic script job">cmd</span>' if j.kind == "command" else ""
        rows.append(
            f'<tr><td>{E(j.name)}{tag}</td><td class="dim mono">{E(j.cadence)}</td>'
            f'<td style="color:{c};white-space:nowrap" title="{w}{seen}">{g} <span class="dim">{w}</span></td></tr>')
    return f'<table class="jobs"><tr><th>Job</th><th>Cadence</th><th>Last run</th></tr>{"".join(rows)}</table>'


def _skill_chips(a: Agent) -> str:
    if not a.skills:
        return '<span class="dim">none declared</span>'
    chips = []
    for s in a.skills:
        badges = "".join(
            f'<i class="sc" style="background:{SCOPE_BG.get(sc, "#eceff3")}" title="scope: {E(sc)}">{E(sc[:3])}</i>'
            for sc in s.scopes)
        ver = "" if s.version == "*" else f'<span class="sv">@{E(s.version)}</span>'
        warn = ' <i class="sc" style="background:#fdf3d8;color:#b7860f" title="unpinned version">*</i>' if s.version == "*" else ""
        chips.append(f'<span class="chip" title="source: {E(s.source)}">{E(s.id)}{ver}{warn}{badges}</span>')
    return '<span class="chips">' + "".join(chips) + "</span>"


def _cost(a: Agent) -> str:
    if not a.tokens_30d:
        return '<span class="dim">—</span>'
    c = f' · <span class="dim" title="api-equiv, subscription quota — not billed">≈${a.cost_30d:.2f}</span>' if a.cost_30d else ""
    return f'<b>{a.tokens_30d:,}</b>{c}'


def _agent_card(a: Agent, coordinator: bool = False) -> str:
    if a.placeholder:
        return (f'<div class="card planned"><div class="chead"><b>{E(a.display)}</b>'
                f'<span class="leader">{E(a.leader)}</span>{_pill("planned")}</div>'
                f'<p class="dim">{E(a.placeholder)}</p></div>')
    metric = f'<div class="metric">{E(a.goal_metric)}</div>' if a.goal_metric else ""
    head = f'<span class="crown" title="coordinator">♛</span> ' if coordinator else ""
    return f"""<div class="card{' coord' if coordinator else ''}">
  <div class="chead">{head}<b>{E(a.display)}</b><span class="leader">{E(a.leader)}</span>{_pill(a.status)}</div>
  {metric}
  <p class="bull">{E(a.bulletin)}</p>
  {_jobs_table(a)}
  <div class="skrow"><span class="sklabel">Skills</span>{_skill_chips(a)}</div>
  <div class="foot"><span>Runs (30d): <b>{a.runs_30d}</b></span><span>Tokens (30d): {_cost(a)}</span><span class="dim">{E(a.membership)}</span></div>
</div>"""


def render(realm: Realm) -> str:
    logo = _logo_b64()
    coord = realm.coordinator
    coord_html = _agent_card(coord, coordinator=True) if coord else ""
    cards = "\n".join(_agent_card(a) for a in realm.members)
    gaps = "\n".join(
        f'<li class="{ "gap-warn" if g.kind=="warn" else "gap-info" }">{E(g.label)}</li>' for g in realm.gaps)
    total_runs = sum(a.runs_30d for a in realm.agents)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARMADA — {E(realm.name)}</title><style>
:root{{--navy:{NAVY};--teal:{TEAL};--ink:{INK};--bg:{BG};--card:{CARD};--line:{LINE};--dim:{DIM}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:20px 18px 60px}}
header{{display:flex;align-items:center;gap:18px;flex-wrap:wrap;border-bottom:3px solid var(--navy);padding-bottom:14px;margin-bottom:8px}}
header img{{height:56px}}
.htitle{{display:flex;flex-direction:column;gap:2px}} .htitle .rn{{font-size:20px;font-weight:800;color:var(--navy)}}
.htitle .rmeta{{color:var(--dim);font-size:13px}}
.badge{{margin-left:auto;background:var(--teal);color:#fff;border-radius:999px;padding:5px 12px;font-size:12px;font-weight:700;letter-spacing:.3px}}
h2{{font-size:15px;color:var(--navy);margin:26px 0 10px;text-transform:uppercase;letter-spacing:.6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--teal);border-radius:12px;padding:14px 15px;box-shadow:0 1px 2px rgba(16,42,86,.04)}}
.card.coord{{border-left-color:var(--navy);background:#f7faff}} .card.planned{{opacity:.7;border-left-color:#c7ced8}}
.chead{{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}} .chead b{{color:var(--navy);font-size:16px}}
.crown{{color:var(--navy)}} .leader{{color:#7c8aa0;font-size:12.5px;font-style:italic}}
.pill{{margin-left:auto;border-radius:999px;padding:2px 10px;font-size:11px;font-weight:800;letter-spacing:.4px}}
.metric{{color:#41506a;font-size:12.5px;margin:7px 0 2px;font-style:italic}}
.bull{{font-size:13px;margin:8px 0 10px;color:#2a374a}}
table.jobs{{width:100%;border-collapse:collapse;margin:6px 0}}
table.jobs th{{text-align:left;font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--line);padding:3px 6px 4px}}
table.jobs td{{font-size:12.5px;padding:4px 6px;border-bottom:1px solid #f0f3f7}}
.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px}}
.jtag{{display:inline-block;background:#eef2f8;border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:9.5px;color:#5a6b86;font-family:ui-monospace,Menlo,Consolas,monospace;vertical-align:middle}}
.foot{{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#41506a;margin-top:9px;border-top:1px dashed var(--line);padding-top:8px}}
.skrow{{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-top:9px}}
.sklabel{{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.4px}}
.chips{{display:flex;gap:6px;flex-wrap:wrap}}
.chip{{display:inline-flex;align-items:center;gap:3px;background:#eef2f8;border:1px solid var(--line);border-radius:999px;padding:2px 8px;font-size:11.5px;color:#2a374a;font-family:ui-monospace,Menlo,Consolas,monospace}}
.chip .sv{{color:var(--teal)}}
.chip .sc{{font-style:normal;border-radius:4px;padding:0 4px;font-size:9.5px;color:#41506a;letter-spacing:.2px}}
.dim{{color:var(--dim)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px}}
.panel ul{{margin:6px 0 0;padding-left:18px}} .panel li{{margin:4px 0;font-size:13px}}
.gap-warn{{color:#a15c00}} .gap-info{{color:#41506a}}
.kpis{{display:flex;gap:22px;flex-wrap:wrap;margin-top:8px}} .kpi b{{color:var(--navy);font-size:22px}} .kpi span{{color:var(--dim);font-size:12px;display:block}}
footer{{color:var(--dim);font-size:12px;margin-top:34px;border-top:1px solid var(--line);padding-top:12px}}
</style></head><body><div class="wrap">
<header>
  {'<img alt="ARMADA" src="'+logo+'">' if logo else '<b style="color:var(--navy);font-size:24px">ARMADA</b>'}
  <div class="htitle"><span class="rn">{E(realm.name)}</span>
    <span class="rmeta">{E(realm.theme_collective)} · {E(realm.theme_agent)}s · engine: {E(realm.engine)} · generated {E(realm.generated_at)}</span></div>
  <span class="badge">READ-ONLY COCKPIT · v0.5</span>
</header>

<div class="kpis">
  <div class="kpi"><b>{len(realm.members)}</b><span>{E(realm.theme_agent)}s</span></div>
  <div class="kpi"><b>{sum(len(a.jobs) for a in realm.agents)}</b><span>jobs</span></div>
  <div class="kpi"><b>{total_runs}</b><span>runs · last 30d</span></div>
  <div class="kpi"><b>{f"{realm.tokens_30d/1000:.0f}k" if realm.tokens_30d else "—"}</b><span>tokens · 30d</span></div>
  <div class="kpi"><b>{f"≈${realm.cost_30d:.2f}" if realm.cost_30d else "—"}</b><span>api-equiv · 30d</span></div>
  <div class="kpi"><b>1</b><span>{E(realm.theme_coordinator)}</span></div>
</div>

<h2>Realm health &amp; gaps</h2>
<div class="panel"><ul>{gaps}</ul></div>

<h2>{E(realm.theme_coordinator)}</h2>
{coord_html}

<h2>{E(realm.theme_agent)}s</h2>
<div class="grid">
{cards}
</div>

<footer>ARMADA v0.5 · read-only cockpit · reads the realm at <span class="mono">{E(realm.root)}</span> · roster · jobs · skills (pinned + scoped) · usage (SPEC §4/§6/§10). Nothing here is written back — this is the observe layer.</footer>
</div></body></html>"""
