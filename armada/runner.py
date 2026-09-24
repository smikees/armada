"""Runner (SPEC §8) — runs ONE job through an engine and writes a tokenized run-report.

This closes the telemetry gap the P1 cockpit surfaced: every run now records
input/output/cache tokens + cost, per agent, in the realm files.

v0.2 reads a minimal ARMADA-native realm (JSON configs + .md context) so a job has a
prompt to run — the reference cabinet keeps its prompts in the scheduler, so the native
format is what the runner operates on. Context assembly is the P2 slice of §5: realm
objectives + tenets + agent mandate + soul + the job prompt. (Threads/compaction = P3.)
"""
from __future__ import annotations
import json, datetime, subprocess, shlex, time, os, re, sys, logging, threading
from pathlib import Path
from typing import Optional

log = logging.getLogger("armada.runner")
from .engine import get_engine, EngineAdapter
from . import memory, model, models, workspace
from .threads import Thread
from .util import swallowed


# Tool names whose file_path we treat as an OUTPUT artifact of the turn.
_OUT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _fs_snapshot(agent_dir: Path) -> dict:
    """{abs_path: mtime} for candidate artifact files under the agent dir — pruning the plumbing
    subtrees (jobs/threads/memory) and dot/underscore files. Used to detect files a turn creates via
    ANY tool (Bash, scripts, …), not just the Write/Edit tools we can see in the event stream."""
    snap: dict = {}
    root = Path(agent_dir)
    if not root.is_dir():
        return snap
    skip = {"jobs", "threads", "memory"}
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith((".", "_"))]
        for fn in files:
            if fn.startswith((".", "_")):
                continue
            p = os.path.join(dp, fn)
            try:
                snap[p] = os.path.getmtime(p)
            except OSError:
                pass
    return snap


def _guard_snapshot(realm_root: Path, agent_dir: Path) -> dict:
    """Snapshot every memory file the acting agent is NOT allowed to change — the realm memory dir
    and every OTHER agent's memory dir (its own is exempt). Paired with _guard_restore to revert any
    out-of-bounds writes an agent makes during a tool turn."""
    realm_root, agent_dir = Path(realm_root), Path(agent_dir)
    own = (agent_dir / "memory").resolve()
    roots = [realm_root / "memory"]
    adir = realm_root / "agents"
    if adir.is_dir():
        for d in adir.iterdir():
            md = d / "memory"
            try:
                if md.is_dir() and md.resolve() != own:
                    roots.append(md)
            except OSError:
                pass
    files = {}
    for r in roots:
        if not r.is_dir():
            continue
        for f in r.rglob("*"):
            if f.is_file():
                try:
                    files[str(f.resolve())] = f.read_bytes()
                except OSError:
                    pass
    return {"files": files, "roots": [str(r) for r in roots], "own": str(own)}


def _guard_restore(snap: dict) -> int:
    """Undo any change the agent made to guarded memory files: delete files it created, restore ones
    it edited or deleted. The agent's own memory folder is untouched. Returns the number reverted."""
    if not snap:
        return 0
    before, own = snap.get("files", {}), Path(snap.get("own", ""))
    reverted = 0
    for rt in snap.get("roots", []):
        rp = Path(rt)
        if not rp.is_dir():
            continue
        for f in rp.rglob("*"):
            try:
                if f.is_file() and str(f.resolve()) not in before and own not in f.resolve().parents:
                    f.unlink()                                   # agent-created → remove
                    reverted += 1
            except OSError:
                pass
    for p, data in before.items():
        try:
            fp = Path(p)
            if own in fp.parents:
                continue
            if not fp.exists() or fp.read_bytes() != data:
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_bytes(data)                             # edited/deleted → restore
                reverted += 1
        except OSError:
            pass
    return reverted


def _is_internal_artifact(path: str, agent_dir: Path) -> bool:
    """True for files that are plumbing, not a user-facing artifact: the agent's own realm records
    (job proposals, ledgers, thread logs/attachments, memory). We still surface anything the agent
    writes OUTSIDE its own agent dir (e.g. into D:\\Work\\Hand), which is where real deliverables land."""
    try:
        p = Path(path).resolve()
    except Exception:  # noqa
        log.debug('_is_internal_artifact: failed; returning a fallback', exc_info=True)
        return False
    try:
        rel = p.relative_to(Path(agent_dir).resolve())
    except Exception:  # noqa
        log.debug('_is_internal_artifact: failed; returning a fallback', exc_info=True)
        return False                                    # outside the agent dir → a real deliverable
    parts = set(rel.parts)
    return bool(parts & {"jobs", "threads", "memory"}) or rel.name.startswith("_")


def _running_marker(agent_dir: Path, job_id: str, on: bool) -> None:
    """Write/remove a transient marker so the UI can show a job as 'running' while it executes.
    Best-effort: any filesystem error is swallowed (telemetry, not correctness)."""
    p = Path(agent_dir) / "runs" / ".running" / f"{job_id}.json"
    try:
        if on:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}),
                         encoding="utf-8")
        else:
            p.unlink(missing_ok=True)
    except OSError:
        pass


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


def _load_json(p: Path) -> dict:
    return json.loads(_read(p)) if p.exists() else {}


def _cli_model(display: str, realm_root=None) -> str:
    """Map a ARMADA model label ('Claude Opus 4.8', 'Claude Sonnet 5', …) to a selector the
    Claude Code CLI accepts.

    The synced catalogue is the authority, because it IS a label -> id table kept in step with
    what this account can actually use. A label naming a specific version must resolve to that
    version's id, or the chip the UI shows is not the model that runs: 'Claude Opus 4.8' used to
    fall through to the family alias 'opus', and the run reports prove the CLI then served
    claude-opus-5 — a silent upgrade the user never asked for and could not see.

    Family aliases (opus/sonnet/haiku) remain the fallback for when the catalogue cannot answer:
    they are always valid, but they resolve to the newest version of the family rather than the
    one named, so they are a last resort and not the first choice. Unknown -> '' (CLI decides).
    """
    d = (display or "").strip().lower()
    if not d:
        return ""
    if d.startswith("claude-"):
        return display.strip()      # already a concrete model id (from the synced catalog) — pass through
    if realm_root is not None:
        # Active entries only: a retired model would be a pin the CLI rejects, and retirement is
        # also what disambiguates the two 'Claude Haiku 4.5' rows in a synced catalogue.
        for m in models.load(realm_root).get("models", []):
            if m.get("active") and str(m.get("label") or "").strip().lower() == d:
                return str(m.get("id") or "").strip()
    exact = {
        "claude opus 5": "claude-opus-5",
        "claude sonnet 5": "claude-sonnet-5",
        "claude fable 5": "claude-fable-5",
        "claude haiku 4.5": "haiku",
    }
    if d in exact:
        return exact[d]
    if "haiku" in d:
        return "haiku"
    if "sonnet" in d:
        return "sonnet"
    if "opus" in d:
        return "opus"
    if "fable" in d:
        return "claude-fable-5"
    return ""


def _resolve_model(realm_root: Path, agent: dict) -> str:
    """Effective CLI model for an agent: its own model, else the realm default, mapped to a
    CLI selector. Always returns a valid selector (or '') — never the raw display label, so a
    label like 'Claude Opus 4.8' can't reach the CLI verbatim and error."""
    m = agent.get("model")
    if not m:
        rj = _load_json(Path(realm_root) / "realm.json")
        m = rj.get("default_model")
    return _cli_model(m, realm_root)


_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def _resolve_effort(realm_root: Path, agent: dict) -> str:
    """Effective reasoning-effort level to pass to the engine (--effort): the agent's effort, else the
    realm default, else 'high'. (Effort IS the thinking level in current Claude models; the CLI has no
    hard 'off' — 'low' is the floor — so there's no separate Thinking toggle.)"""
    eff = str(agent.get("effort") or "").strip().lower()
    if not eff:
        rj = _load_json(Path(realm_root) / "realm.json")
        eff = str(rj.get("default_effort") or "").strip().lower()
    return eff if eff in _EFFORT_LEVELS else "high"


def _resolve_fallback_model(realm_root: Path, agent: dict) -> str:
    """Model to fall back to if the primary is overloaded/unavailable (--fallback-model): the agent's
    own choice, else the realm default, else '' (no fallback). Run through _cli_model so a display
    label ('Claude Opus 4.8') can't reach the CLI verbatim."""
    m = agent.get("fallback_model")
    if not m:
        m = _load_json(Path(realm_root) / "realm.json").get("default_fallback_model")
    return _cli_model(m, realm_root) if m else ""


def _resolve_timeout(realm_root: Path, job: dict) -> Optional[int]:
    """How long to let one agent run take: the job's own `timeout`, else the realm's
    `default_job_timeout`, else nothing (the engine's default applies)."""
    for v in (job.get("timeout"), _load_json(Path(realm_root) / "realm.json").get("default_job_timeout")):
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return None


def _resolve_max_budget(realm_root: Path, agent: dict) -> Optional[float]:
    """Per-run spend ceiling in USD (--max-budget-usd): the agent's value, else the realm default,
    else None (uncapped). 0/blank means 'no cap'."""
    v = agent.get("max_budget_usd")
    if v in (None, ""):
        v = _load_json(Path(realm_root) / "realm.json").get("default_max_budget_usd")
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _disallowed_tools(realm_root: Path, agent: dict) -> list:
    """MCP tool patterns to withhold for this run — every capability this agent may NOT use.

    This is where the grant model stops being a description and starts being enforcement. It used
    to block only capabilities switched off for the whole realm, which meant an empty agent toolkit
    inherited everything; now an agent gets what it was granted, the coordinator gets the catalogue,
    and everything else is denied by name. See armada.capabilities for the rule and for what this
    can and cannot reach (MCP servers yes, skills no).
    """
    from . import capabilities
    try:
        return capabilities.denied_tool_patterns(realm_root, agent)
    except Exception:  # noqa — never let a capability lookup take down a run
        log.exception("capability denial list failed; falling back to realm-disabled only")
        pats = set()
        rj = (_load_json(Path(realm_root) / "realm.json").get("toolkit") or {})
        for kind in ("connectors", "extensions", "plugins"):
            for it in (rj.get(kind) or []):
                if it.get("enabled", True) is False and str(it.get("id") or "").strip():
                    pats.add(f"mcp__{str(it['id']).strip()}")
        return sorted(pats)


def _record_used_capabilities(realm_root: Path, tool_names) -> None:
    """Ensure every MCP capability an agent actually used shows up in the REALM's list, keyed by its
    real server name. Best-effort; never breaks a run.

    Realm level and only realm level. A capability discovering itself mid-run must not also grant
    itself to the agent that tripped over it — that would make "first use wins" a way around the
    grant model, and the owner would learn about it only by noticing a new row. Discovery adds to
    the catalogue; granting stays a decision.
    """
    from . import util
    servers = []
    for nm in (tool_names or []):
        m = re.match(r"mcp__([A-Za-z0-9_.\-]+)__", str(nm or ""))
        if m and m.group(1) not in servers:
            servers.append(m.group(1))
    if not servers:
        return
    try:
        rp = Path(realm_root) / "realm.json"
        with util.file_lock(rp):
            js = _load_json(rp)
            conns = js.setdefault("toolkit", {}).setdefault("connectors", [])
            have = {str(c.get("id") or "").lower() for c in conns} | {str(c.get("name") or "").lower() for c in conns}
            added = False
            for srv in servers:
                if srv.lower() in have:
                    continue
                conns.append({"id": srv, "name": srv, "icon": "cap-connector", "scope": "MCP server (Claude)",
                              "status": "connected", "source": "3p", "discovered": True,
                              "runs": "service", "touch": ["network"]})
                have.add(srv.lower())
                added = True
            if added:
                util.write_json_atomic(rp, js)
    except Exception:  # noqa — auto-discovery must never break the turn
        log.exception("record used capabilities failed")


def _model_label(realm_root: Path, agent: dict, job: dict | None = None) -> str:
    """The human model label used for context sizing (job override → agent → realm default)."""
    m = (job or {}).get("model") or agent.get("model")
    if not m:
        m = _load_json(Path(realm_root) / "realm.json").get("default_model")
    return m or ""


def _compact_threshold(realm_root: Path, agent: dict, job: dict | None = None) -> int:
    return model.compaction_threshold_chars(_model_label(realm_root, agent, job))


def _host_preamble(realm_root: Path) -> str:
    """Runtime/host parity: tell the agent the real environment so prompts written for another
    runtime (e.g. the Cowork sandbox) resolve here. Provider- and host-aware, ~60 tokens."""
    import platform, datetime
    osname = "Windows" if os.name == "nt" else platform.system()
    py = "python" if os.name == "nt" else "python3"
    ws = workspace.root(realm_root)
    # Naming the root and the token together is what keeps jobs portable: an agent writing a new
    # job prompt has to know the token exists, or it bakes today's drive letter into next year's job.
    ws_line = (f"- Your workspace root is `{ws}`. In any job prompt you WRITE, refer to it as "
               f"`{{workspace}}` (ARMADA expands it at run time) so the job still works if this "
               f"realm moves to another machine. Use the real path in commands you run now.\n"
               if ws else "")
    return ("[ARMADA runtime — read first]\n"
            f"- Host OS: {osname}. Today: {datetime.date.today().isoformat()}. Run Python as `{py}`.\n"
            f"- This realm's folder: {realm_root}\n"
            + ws_line +
            "- You run under ARMADA on the user's own machine (not the Cowork sandbox). Any "
            "`/sessions/<...>/mnt/Work` path in the instructions is a sandbox artifact that DOES NOT "
            "EXIST here — use the absolute native path given alongside it (e.g. `D:\\Work\\...`).\n"
            + ("- In the Bash tool on Windows, quote Windows paths or use forward slashes "
               "(`\"D:\\Work\\...\"` or `/d/Work/...`); UTF-8 is already set, so Python Unicode output "
               "won't crash.\n" if os.name == "nt" else ""))


def _jobs_capability(agent_dir: Path) -> str:
    """The self-service job-proposal contract, addressed to THIS agent (absolute pending path)."""
    pend = str(Path(agent_dir) / "jobs" / "_pending")
    return (
        "[Creating scheduled jobs — you can do this yourself]\n"
        "- When the owner asks you to set up / schedule / create a job, DO NOT inspect the realm, "
        "list folders, or look for how jobs are registered — the contract below is complete and "
        "authoritative. Just write ONE file with your Write tool. Do not use Bash/PowerShell for this.\n"
        f"- Write it to: {pend}\\<slug>.json  (this `_pending` folder is inside your own agent "
        "folder — create it if it doesn't exist; `./jobs/_pending/<slug>.json` relative to your "
        "working directory is the same place).\n"
        "- File contents (JSON):\n"
        "    {\n"
        "      \"id\": \"<lowercase-kebab-slug>\",   // also the file name\n"
        "      \"name\": \"Human Readable Name\",\n"
        "      \"kind\": \"agent\",                   // \"agent\" = you run a prompt; \"command\" = run a shell/Python command\n"
        "      \"prompt\": \"what you should do on each run\",   // for kind:agent\n"
        "      \"run\": \"python foo.py\",            // instead of prompt, for kind:command\n"
        "      \"schedule\": \"daily 09:00\"          // or a 5-field cron like \"0 9 * * 1-5\", or \"manual\"\n"
        "    }\n"
        "- Schedule grammar: \"daily HH:MM\", \"mon-fri HH:MM\", \"mon,wed,fri HH:MM\", \"sat HH:MM\", a "
        "standard 5-field cron, or \"manual\". Prefer kind:agent unless a deterministic command is "
        "genuinely needed.\n"
        "- The job is a PROPOSAL: it appears on the owner's Jobs page for approval and only runs "
        "AFTER they approve it — you cannot enable or run it yourself. After writing the file, tell "
        "the owner you've proposed \"<name>\" and it's awaiting their approval on the Jobs page.\n"
        "- Whether a proposal is still pending, was approved, or was rejected is given to you in the "
        "'Your scheduled jobs — current status' snapshot below — treat that as ground truth and never "
        "guess from this conversation's history (a proposal you made earlier may already be approved "
        "or rejected). The owner approves/rejects proposals on the Jobs page; you can't, and you must "
        "not offer to delete or clean up proposal files yourself.\n")


def _say(*parts) -> None:
    """print() that can't take a run down.

    A run's console output is diagnostics, never the work. But these lines contain '─', '·' and '→',
    and stdout on Windows is often cp1252 — a pipe, a redirected file, an inherited handle from
    whatever launched us. Printing a 60-character rule then raised UnicodeEncodeError *after* the
    agent had finished successfully, so a completed task was reported as a failure.

    Falls back to an ASCII-safe rendering rather than staying silent, so a real console still gets
    something readable.
    """
    msg = " ".join(str(p) for p in parts)
    try:
        if sys.stdout is None:
            return
        print(msg)
    except UnicodeEncodeError:
        try:
            enc = getattr(sys.stdout, "encoding", None) or "ascii"
            print(msg.encode(enc, "replace").decode(enc, "replace"))
        except Exception:  # noqa
            log.debug('_say: failed; ignored', exc_info=True)
    except Exception:  # noqa — a closed or broken stream is not a reason to fail a job
        log.debug('_say: failed; ignored', exc_info=True)


def _thread_href(agent_id: str, thread: str = "main") -> str:
    """Where to go to read what a run produced — the agent's thread."""
    import urllib.parse as _up
    return (f"/agent/{_up.quote(str(agent_id), safe='')}/threads"
            f"?thread={_up.quote(str(thread or 'main'), safe='')}")


def _took(seconds) -> str:
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60:02d}s"


def _note(headline: str, subject: str = "", rows=()) -> tuple:
    """(title, body) for any notification: a headline, who or what it's about, then labelled rows.

    One shape for everything ARMADA tells you. The body is the entire message on Telegram and on a
    desktop toast — there's no page to click through to — so "Needs your approval / x" was, fairly,
    useless. Blank rows are dropped rather than printed empty."""
    title = f"{headline} · {subject}" if subject else headline
    body = "\n".join(f"{k}: {v}" for k, v in rows if str(v or "").strip())
    return title, body


def _cadence_text(job: dict) -> str:
    """A schedule in words. Deliberately a small local reader rather than the UI's full humaniser:
    that lives in the web layer, and the runner shouldn't drag the whole UI in to write a sentence."""
    cron = str(job.get("cron") or "").strip()
    if not cron:
        c = str(job.get("cadence") or "").strip()
        return c or "on demand (no schedule)"
    f = cron.split()
    if len(f) != 5:
        return f"cron: {cron}"
    mi, hh, dom, mon, dow = f
    at = f"{hh.zfill(2)}:{mi.zfill(2)}" if hh.isdigit() and mi.isdigit() else ""
    days = {"*": "every day", "1-5": "every weekday", "0": "Sundays", "1": "Mondays",
            "2": "Tuesdays", "3": "Wednesdays", "4": "Thursdays", "5": "Fridays", "6": "Saturdays"}
    if mon == "*" and dom == "*" and dow in days:
        return f"{days[dow]}{(' at ' + at) if at else ''}"
    if mon == "*" and dom.isdigit():
        return f"day {dom} of each month{(' at ' + at) if at else ''}"
    return f"cron: {cron}"


def _approval_note(agent_disp: str, agent_id: str, job: dict) -> tuple:
    """What the owner needs in order to decide without opening the app: which agent wants what,
    what kind of thing it is, when it would run, and what it would actually do."""
    kind = str(job.get("kind") or "").lower()
    if kind == "command" or job.get("run") or job.get("command"):
        what_it_does = job.get("run") or job.get("command") or ""
        if isinstance(what_it_does, list):
            what_it_does = " ".join(str(x) for x in what_it_does)
        type_label = "command job (runs a script — no agent, no tokens)"
    else:
        what_it_does = str(job.get("prompt") or "")
        type_label = "agent job (a prompt run on a schedule)"
    does = " ".join(str(what_it_does).split())[:280]
    return _note("Approval needed", agent_disp, (
        ("Job", job.get("name") or job.get("id") or "(unnamed)"),
        ("Proposed by", f"{agent_disp} ({agent_id})" if agent_disp != agent_id else agent_id),
        ("Type", type_label),
        ("Runs", _cadence_text(job)),
        ("Does", does or "(nothing specified)"),
        ("To decide", "Approvals in ARMADA — nothing runs until you say so"),
    ))


def _job_note(state: str, who: str, what: str, *, why: str = "", took=None,
              thread: str = "", agent_id: str = "") -> tuple:
    """One shape for every job notification: (title, body).

    These used to be assembled ad hoc at each call site, so a failure could arrive as nothing but
    "Marcus: job failed" and a bare exception class — no job name, no reason you could act on, and
    a different layout depending on which branch produced it. On Telegram, where there's no page to
    click through to, that's the whole message. Same fields, same order, every time; empty ones are
    dropped rather than printed blank."""
    labels = {"started": "Job started", "finished": "Job finished", "failed": "Job failed"}
    rows = [("Job", what), ("Agent", who)]
    if state == "failed":
        rows.append(("Why", (why or "no reason reported").strip()))
    elif why:
        rows.append(("Result", why.strip()))
    if took:
        rows.append(("Took", _took(took)))
    if thread:
        rows.append(("Thread", thread))
    if agent_id:
        rows.append(("Open", f"{agent_id} → {thread or 'main'}"))
    return _note(labels.get(state, "Job"), who, rows)


def _notify(realm_root, event: str, title: str, body: str = "", href: str = "") -> None:
    """Announce an event: archive it in the in-app feed and, if it warrants interrupting, raise a
    desktop notification too. Never raises, never blocks — a failure to notify must not disturb the
    run that triggered it."""
    try:
        from . import notify as _n
        _n.emit(realm_root, event, title, body, href)
    except Exception:  # noqa — notifications are strictly cosmetic
        swallowed(log, '_notify: failed; ignored')


def _cap_request_note(agent_disp: str, agent_id: str, req: dict) -> tuple:
    """What the owner needs to decide on a capability request without opening the app.

    The reason is the whole message — "Warren wants the filesystem extension" is not a decision,
    "Warren wants it to read the quarterly CSVs you asked about" is. So the reason is quoted as the
    agent gave it, and a request with no reason says so rather than looking like a formatting slip.
    """
    return _note("Capability requested", agent_disp, (
        ("Capability", req.get("name") or req.get("capability") or "(unnamed)"),
        ("Kind", str(req.get("kind") or "").rstrip("s") or "capability"),
        ("Asked by", f"{agent_disp} ({agent_id})" if agent_disp != agent_id else agent_id),
        ("In thread", req.get("thread") or "—"),
        ("Why", " ".join(str(req.get("reason") or "").split())[:280] or "(no reason given)"),
        ("If approved", f"{agent_disp} can use it from its next run. Until then it cannot."),
    ))


def _sync_cap_requests(realm_root, agent_id: str, thread: str = "") -> None:
    """Notice a capability the agent just asked for, and tell the owner.

    The agent writes the request file itself during its turn (same contract as a job proposal), so
    nothing here grants anything — it stamps the thread if the agent left it out and raises the
    approval. An unnoticed request is worse than no request: the agent has said it's blocked, told
    the owner it asked, and then nothing ever arrives.
    """
    try:
        from . import capabilities as _caps
        d = _caps.requests_dir(realm_root, agent_id)
        if not d.is_dir():
            return
        adir = Path(realm_root) / "agents" / agent_id
        disp = _load_json(adir / "agent.json").get("display") or agent_id
        for f in sorted(d.glob("*.json")):
            req = _load_json(f)
            if not req or req.get("notified"):
                continue
            if thread and not req.get("thread"):
                req["thread"] = thread      # the agent rarely knows its own thread name
            req["notified"] = True
            from . import util as _util
            _util.write_json_atomic(f, req)
            _notify(realm_root, "approval_needed",
                    *_cap_request_note(disp, agent_id, req), href="/skills")   # the Capabilities page
    except Exception:  # noqa — telemetry, never break a turn
        swallowed(log, '_sync_cap_requests: failed; ignored')


def _sync_proposals(realm_root, agent_id: str) -> None:
    """Best-effort: record 'proposed' ledger events for any job the agent just wrote to _pending."""
    try:
        from . import jobs as _jobs
        before = len(_jobs.status_for_agent(realm_root, agent_id).get("pending") or [])
        _jobs.sync_proposals(realm_root, agent_id)
        after = _jobs.status_for_agent(realm_root, agent_id).get("pending") or []
        if len(after) > before:                  # the agent just proposed something new
            newest = after[-1]
            # status_for_agent() summarises to {id, name}; the notification needs the proposal
            # itself — what it would run, and when — so read the pending file.
            adir = Path(realm_root) / "agents" / agent_id
            full = _load_json(adir / "jobs" / _jobs.PENDING / f'{newest.get("id")}.json') or newest
            disp = _load_json(adir / "agent.json").get("display") or agent_id
            _notify(realm_root, "approval_needed",
                    *_approval_note(disp, agent_id, full), href="/approvals")
    except Exception:  # noqa — telemetry, never break a turn
        swallowed(log, '_sync_proposals: failed; ignored')


def _jobs_status_text(realm_root: Path, agent_dir: Path) -> str:
    """A live, authoritative snapshot of this agent's own proposals (pending/approved/rejected),
    so it can answer accurately instead of guessing from the thread history."""
    try:
        from . import jobs as _jobs
        st = _jobs.status_for_agent(realm_root, Path(agent_dir).name)
    except Exception:  # noqa — never let a status read break a turn
        swallowed(log, '_jobs_status_text: failed; returning a fallback')
        return ""
    timing = ("(This snapshot reflects the state at the START of this turn. A proposal you write "
              "during this turn will not appear until your next turn — so if you just created one, "
              "do NOT conclude the pipeline is broken; trust that your Write succeeded.)")
    def fmt(items):
        return ", ".join(f'"{i["name"]}" ({i["id"]})' for i in items) if items else "none"
    if not (st["pending"] or st["approved"] or st["rejected"] or st.get("history")):
        return ("[Your scheduled jobs — current status] No proposals of yours are on record yet. "
                + timing + "\n")
    lines = ["[Your scheduled jobs — current status, authoritative]",
             f"- Awaiting the owner's approval now: {fmt(st['pending'])}.",
             f"- Approved and now live: {fmt(st['approved'])}.",
             f"- Rejected by the owner: {fmt(st['rejected'])}."]
    hist = st.get("history") or []
    if hist:
        lines.append("- Recent event trail (newest first): "
                     + "; ".join(f'"{h["name"]}" ({h["id"]}) {h["event"]}' + (f' {h["ts"]}' if h.get("ts") else "")
                                 for h in hist) + ".")
    lines.append("Use ONLY this record when talking about your proposals; it is ground truth. " + timing)
    return "\n".join(lines) + "\n"


_CAP_LABELS = [("connectors", "Connectors (remote services)"),
               ("extensions", "Extensions (local tools)"),
               ("skills", "Skills"), ("plugins", "Plugins")]


def _cap_lines(inv: dict) -> list:
    out = []
    for key, label in _CAP_LABELS:
        names, seen = [], set()
        for it in inv.get(key) or []:
            n = (it.get("name") or it.get("id") or "").strip()
            if n and n.lower() not in seen:
                if (it.get("permission") or "").lower() == "ask":
                    n += " (propose to the owner and get approval before using)"
                names.append(n)
                seen.add(n.lower())
        if names:
            out.append(f"- {label}: {', '.join(names)}")
    return out


def _capabilities_context(realm_root: Path, agent_dir: Path) -> str:
    """What this agent has, what else the realm has, and how to ask for the difference.

    Two lists, never one. An agent shown a single merged inventory will reach for anything on it,
    and then a denial arrives as a tool error it can't interpret — so it retries, or invents a
    workaround, or reports a failure that reads like a bug. Naming the second list as *not yours,
    ask for it* turns the same situation into a decision the owner gets to make, which is the whole
    point of granting capabilities one at a time.
    """
    from . import capabilities
    agent = _load_json(Path(agent_dir) / "agent.json")
    try:
        mine = capabilities.usable(realm_root, agent)
        others = capabilities.requestable(realm_root, agent)
    except Exception:  # noqa
        swallowed(log, '_capabilities_context: failed; returning a fallback')
        return ""

    mine_lines, other_lines = _cap_lines(mine), _cap_lines(others)
    if not mine_lines and not other_lines:
        return ""

    out = []
    if mine_lines:
        out.append("[Your capabilities — review these against the request and use any that are relevant]")
        out += mine_lines
        out.append("If the request calls for one of these, use it (or say which one you'd use and why).")
    else:
        out.append("[Your capabilities]\n- None yet. You have not been granted any capability in "
                   "this realm.")

    if other_lines:
        me = Path(agent_dir).name
        req = Path(agent_dir) / capabilities.REQUESTS_DIR
        out.append("")
        out.append("[Also in this realm — you may NOT use these yet]")
        out += other_lines
        out.append(
            "These exist in the realm but are not yours. Do NOT attempt to use one: the tools are "
            "withheld, so trying wastes the run and tells you nothing.\n"
            "If one of them would genuinely help with the CURRENT task, ask for it: write "
            f"{req}\\<capability>.json containing "
            '{"capability": "<id or name exactly as listed>", "reason": "<one sentence on what '
            'you need it for, in this task>"}'
            f" (create the folder if needed), and say in your reply that you have asked the owner "
            f"to grant it. The owner approves or declines; if approved you will have it on your "
            f"next run. Ask only when the task actually needs it — a request the owner has to "
            f"read is a cost, and asking for things speculatively is how people stop reading them."
        )
    return "\n".join(out) + "\n"


def _norm_cap(s) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _capability_index(realm_root: Path, agent_dir: Path) -> list:
    """(kind, cap, keys) for each capability this agent may USE — for recognising which one a tool
    call exercised. `keys` are normalised id/name tokens.

    Indexed on what the agent is allowed, not on the whole catalogue, so the thread's "capabilities
    used" list reports the agent's own reach. A call to something ungranted shouldn't reach the
    engine at all (see _disallowed_tools); if one somehow does, it is better that it fails to match
    here and shows up as unaccounted for than that it is quietly filed as normal use.
    """
    from . import capabilities
    try:
        use = capabilities.usable(realm_root, _load_json(Path(agent_dir) / "agent.json"))
    except Exception:  # noqa
        swallowed(log, '_capability_index: failed; returning a fallback')
        return []
    idx = []
    for kind in capabilities.KINDS:
        for it in use.get(kind) or []:
            keys = {k for k in (_norm_cap(it.get("id")), _norm_cap(it.get("name"))) if len(k) >= 4}
            if keys:
                idx.append((kind, {"id": it.get("id", ""), "name": it.get("name") or it.get("id", ""),
                                   "description": it.get("description", "")}, keys))
    return idx


_WEB_TOOLS = {"websearch", "webfetch"}   # Claude's built-in web research (not an MCP/plugin)


def _match_capabilities(tool_name: str, tool_input, index: list) -> list:
    """Which capabilities a single tool call exercised. Real capability tools count: MCP tools
    (`mcp__<server>__…`), skill invocations, and Claude's built-in web research (WebSearch/WebFetch,
    surfaced as a 'built-in' capability) — NOT plumbing like Bash/Read/Write. Returns a list of
    (kind, cap). Empty for the common case where the agent used no capability at all."""
    name = tool_name or ""
    if name.lower() in _WEB_TOOLS:
        return [("builtin", {"id": "web-research", "name": "Web research",
                             "description": "Claude's built-in web search & fetch."})]
    probes = set()
    if name.startswith("mcp__"):
        parts = name.split("__")
        if len(parts) >= 2:
            probes.add(_norm_cap(parts[1]))                 # the MCP server slug
    elif name.lower() in ("skill", "skills") and isinstance(tool_input, dict):
        for v in (tool_input.get("skill"), tool_input.get("name"), tool_input.get("command")):
            if v:
                probes.add(_norm_cap(str(v)))
    probes = {p for p in probes if len(p) >= 4}
    hits = []
    for kind, cap, keys in index:
        if any(p == k or p in k or k in p for p in probes for k in keys):
            hits.append((kind, cap))
    return hits


# How long an agent run gets when nothing else says. This mirrors EngineAdapter.run()'s own default,
# which run_stream() does NOT share (it defaults to half). Jobs may take either path, and a job's
# time limit must not depend on which one we happened to call, so the job path passes this
# explicitly. test_turn_capture asserts the two stay equal.
_DEFAULT_RUN_TIMEOUT = 1200


class _TurnCapture:
    """Records what a single agent turn produced: the files it wrote, and which of its declared
    capabilities it actually exercised.

    Both the chat path and the job path need this. Artefacts were previously captured only for
    chat, which is backwards: when the owner is sitting there they can see the file appear, and
    when a job runs at 03:00 the thread entry is the only account of what it left behind.

    Two sources, because neither alone is enough. The tool-event stream names the capabilities
    (the only place tool names exist) and catches Write/Edit. The before/after scan of the agent's
    folder catches everything else — a file written by Bash, or by a script the agent ran.
    """

    def __init__(self, realm_root, agent_dir, use_tools: bool):
        self.realm_root = realm_root
        self.agent_dir = Path(agent_dir)
        self.use_tools = bool(use_tools)
        self.outputs: list[dict] = []
        self.caps: list[dict] = []
        self.tools: list = []
        self.stray: list = []          # files written outside the app root, for the run report
        self._seen: set = set()
        self._index = _capability_index(realm_root, agent_dir) if self.use_tools else []
        self._before = _fs_snapshot(self.agent_dir) if self.use_tools else {}

    def _add_output(self, path: str) -> None:
        p = str(path)
        if not p or _is_internal_artifact(p, self.agent_dir):
            return
        if any(o["path"] == p for o in self.outputs):
            return
        rec = {"kind": "output", "name": os.path.basename(p), "path": p}
        # Mark, don't block. The boundary is a working agreement — the agent's own capabilities can
        # reach the whole machine — so the useful thing ARMADA can do is notice and say so, rather
        # than pretend to a veto it hasn't got. A stray file you know about is a filing problem; one
        # you don't is how a realm quietly stops being self-contained.
        try:
            from . import approot
            if approot.configured() and not approot.contains(p):
                rec["outside_root"] = True
                self.stray.append(p)
        except Exception:  # noqa — a failed check must not lose the artefact record
            swallowed(log, '_add_output: failed; ignored')
        self.outputs.append(rec)

    def on_event(self, ev) -> None:
        """Sniff one streamed engine event. Never raises — it sits directly in the event path, so
        a capture bug must not be able to kill the run it is only observing."""
        try:
            if (ev or {}).get("kind") != "tool":
                return
            inp = ev.get("input") or {}
            name = ev.get("name")
            if name:
                self.tools.append(name)
            if name in _OUT_TOOLS:
                fp = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
                if fp:
                    self._add_output(str(fp))
            for kind, capd in _match_capabilities(name, inp, self._index):
                key = (kind, capd["id"] or capd["name"])
                if key not in self._seen:
                    self._seen.add(key)
                    self.caps.append({"type": kind, "id": capd["id"], "name": capd["name"],
                                      "description": capd.get("description", "")})
        except Exception:  # noqa — capture must never break the stream
            log.debug('on_event: failed; ignored', exc_info=True)

    def finish(self) -> "_TurnCapture":
        """Fold in files the event stream couldn't see, and register tools used as capabilities.

        Call AFTER the memory guardrail has restored any out-of-bounds writes, or reverted files
        get listed as artefacts of a turn that no longer owns them.
        """
        if not self.use_tools:
            return self
        try:
            for p, mt in _fs_snapshot(self.agent_dir).items():
                if p not in self._before or self._before[p] < mt:
                    self._add_output(p)
        except Exception:  # noqa
            swallowed(log, 'finish: failed; ignored')
        try:
            _record_used_capabilities(self.realm_root, self.tools)   # used ⇒ listed (auto-discover)
        except Exception:  # noqa — telemetry must never break the turn
            swallowed(log, 'finish: failed; ignored')
        return self


def _publish_boundary(realm_root: Path, agent_dir: Path) -> str:
    """Tell the agent where its own output belongs.

    A convention, not a cage, and the wording says so rather than bluffing: the capabilities an
    agent has can reach the whole machine, and a rule an agent could step over is better stated as
    the working agreement it is. What it buys is that everything a realm produces is in one place —
    findable, backed up together, and gone when the realm is deleted. Reading outside is normal
    work; writing outside is the thing that scatters a realm across a disk.
    """
    from . import approot
    root = approot.root()
    if not root:
        return ""
    return (
        "[Where your output goes]\n"
        f"- ARMADA's root folder on this machine is {root}. Everything this realm produces lives "
        f"inside it.\n"
        f"- Your own working folder is {agent_dir}. Write files you create — reports, data, logs, "
        f"scratch — there, or elsewhere under {root} if the owner names a specific place.\n"
        f"- Do NOT write outside {root}. Reading outside is fine when the task calls for it; "
        "writing outside scatters the realm across the disk, so it ends up un-findable, missing "
        "from a backup, and left behind when the realm is deleted.\n"
        "- If a task seems to require writing outside, say so and ask rather than doing it "
        "quietly. ARMADA records when a run writes outside the root, so it will be noticed.\n")


def _memory_boundary(agent_dir: Path) -> str:
    """Tell the agent where it may and may not write memory. Pairs with the runtime guardrail that
    reverts any writes it makes outside its own memory folder."""
    own = str(Path(agent_dir) / "memory")
    return (
        "[Memory boundaries — respect these]\n"
        f"- Your OWN memory folder is {own} (`./memory/` in your working dir). When the owner asks you "
        "to remember something, you MAY add a short Markdown note there — put `updated_by: "
        f"{Path(agent_dir).name}` and `updated: <YYYY-MM-DD>` in its frontmatter. Write ONLY inside this "
        "folder.\n"
        "- Do NOT edit the realm's System memory (memory/core-context.md), any realm-level memory, or "
        "another agent's memory. The System memory is auto-generated from the realm's real data and is "
        "rewritten on a schedule, so an edit there is pointless — and ARMADA reverts writes you make "
        "outside your own memory folder.\n"
        "- To change realm-level facts (owner details, goals, the agent roster, the environment), don't "
        "edit memory — tell the owner so they change it at the source (Settings, Goals, Appoint). "
        "Propose; the owner disposes.\n")


def _tool_preamble(realm_root: Path, agent_dir: Path) -> str:
    """Everything a tool-using turn should see before ARMADA's assembled core: host/path parity,
    the self-service job-proposal contract, a live status snapshot of this agent's proposals, the
    agent's capability inventory, and the write boundaries — memory, and where output belongs."""
    return (_host_preamble(realm_root) + "\n" + _jobs_capability(agent_dir)
            + _jobs_status_text(realm_root, agent_dir)
            + _inbox_capability(realm_root, agent_dir)
            + _capabilities_context(realm_root, agent_dir)
            + _skill_registry_contract(agent_dir)
            + _publish_boundary(realm_root, agent_dir)
            + _memory_boundary(agent_dir))


def _skill_registry_contract(agent_dir: Path) -> str:
    """Every agent records where a skill it wrote or fetched came from.

    Injected rather than granted. A grantable skill would be the natural home for this, and it is
    the wrong one: a register only works if everybody keeps it, and one ungranted agent silently
    not filing anything leaves the owner with a list that looks complete and isn't.

    The text is read from the bundled system skill rather than written out here, so what the agent
    is told and what the owner reads on Capabilities > System are the same words, and both update
    when ARMADA does. If the bundle is missing this degrades to nothing at all — an agent that
    doesn't know to register is no worse than today, and a broken turn would be.
    """
    try:
        from . import sysskills
        it = sysskills.get_system_skill("skill-registry")
        if not it or not it.get("body"):
            return ""
        me = Path(agent_dir).name
        return ("\n[Recording a skill you write or fetch \u2014 this applies to every agent, always]\n"
                + str(it["body"]).replace("<your-agent-id>", me).strip() + "\n")
    except Exception:  # noqa — the preamble must never be the thing that fails a run
        swallowed(log, '_skill_registry_contract: failed; returning a fallback')
        return ""


def _inbox_capability(realm_root: Path, agent_dir: Path) -> str:
    """How this agent hands a task to a teammate — the delegation contract, addressed to THIS
    agent. Same shape as the job-proposal contract: write one file, no exploration needed."""
    try:
        from . import inbox
        if not inbox.enabled(realm_root):
            return ""
        me = Path(agent_dir).name
        mates = []
        adir = Path(realm_root) / "agents"
        if adir.is_dir():
            for d in sorted(p for p in adir.iterdir() if p.is_dir()):
                if d.name == me or inbox.accepts_from(realm_root, d.name) == "nobody":
                    continue
                nm = (_load_json(d / "agent.json") or {}).get("display") or d.name
                role = (_load_json(d / "agent.json") or {}).get("theme_role") or ""
                mates.append(f"{d.name} ({nm}{', ' + role if role else ''})")
        if not mates:
            return ""
        box = str(Path(realm_root) / "agents" / "<teammate>" / "inbox" / "pending")
        return (
            "\n[Asking a teammate to do something — you can do this yourself]\n"
            "- When a task belongs to another agent's expertise (they own the job, the data or the "
            "relationship), hand it to them instead of doing it yourself or explaining how.\n"
            f"- Teammates who accept tasks: {'; '.join(mates)}.\n"
            f"- Write ONE file with your Write tool to: {box}\\<slug>.json  (create the folder if "
            "it isn't there). Do not use Bash/PowerShell for this.\n"
            "- File contents (JSON):\n"
            "    {\n"
            "      \"id\": \"<lowercase-kebab-slug>\",      // also the file name\n"
            f"      \"from\": \"{me}\",\n"
            "      \"to\": \"<teammate-id>\",\n"
            "      \"ask\": \"what you want them to do, in full — they cannot see this conversation\",\n"
            "      \"context\": \"anything they need that they wouldn't already know\",\n"
            "      \"state\": \"pending\",\n"
            "      \"hops\": 1\n"
            "    }\n"
            "- Write the ask so it stands alone. They have their own context and history; they do "
            "NOT have yours.\n"
            "- They act on their own schedule (minutes to a day), not immediately. Tell the owner "
            "you've asked <teammate> to do it — don't wait for it or claim it's done.\n"
            "- Their answer comes back to your own inbox, and the owner sees the exchange.\n"
            "- Only delegate real work. Don't send acknowledgements, thanks, or 'just checking' "
            "messages: every one of them wakes an agent and spends the owner's subscription.\n")
    except Exception:  # noqa — the preamble must never break a run
        swallowed(log, '_inbox_capability: failed; returning a fallback')
        return ""


def run_job_prompt(realm_root, agent_id: str, prompt: str, thread: str = "main",
                   engine="claude", allow_tools: bool = True, label: str = "adhoc") -> dict:
    """Run a one-off prompt as this agent, through exactly the same path a scheduled job takes.

    Deliberately not a shortcut: reusing _run_job_inner means an inbox task gets the same context
    assembly, the same capability gating, the same guardrails and the same proposal handling as any
    other run. Delegated work must not be more privileged than work the agent does for its owner.
    """
    realm_root = Path(realm_root)
    eng = get_engine(engine) if isinstance(engine, str) else engine
    agent_dir = realm_root / "agents" / agent_id
    agent = _load_json(agent_dir / "agent.json")
    if not agent:
        raise SystemExit(f"ARMADA: no agent '{agent_id}' at {agent_dir}")
    job = {"id": label, "name": "Inbox task", "kind": "agent", "prompt": prompt}
    return _run_job_inner(realm_root, agent_id, label, engine, thread, allow_tools,
                          eng, agent_dir, agent, job)


def run_inbox(realm_root, agent_id: str, engine="claude") -> dict:
    """Act on whatever is waiting in one agent's inbox.

    Only ever called once a cheap file check has found mail, so no tokens are spent discovering an
    empty inbox. Each message is claimed (atomic rename) before the engine runs, so a restart
    mid-task can't replay it, and every outcome is reported back to the sender.
    """
    from . import inbox
    realm_root = Path(realm_root)
    batch = inbox.next_batch(realm_root, agent_id)
    inbox.mark_checked(realm_root, agent_id)
    if not batch:
        return {"ok": True, "handled": 0}
    agent_dir = realm_root / "agents" / agent_id
    agent = _load_json(agent_dir / "agent.json") or {}
    who = agent.get("display") or agent_id
    handled, failed = 0, 0
    for msg in batch:
        ok_to_run, why = inbox.screen(realm_root, agent_id, msg)
        if not ok_to_run:
            # Rejected before any engine call — file it with the reason and tell the sender.
            claimed = inbox.claim(realm_root, agent_id, msg)
            if claimed:
                inbox.complete(realm_root, agent_id, claimed, False, f"Not actioned: {why}.")
            continue
        claimed = inbox.claim(realm_root, agent_id, msg)
        if not claimed:                     # someone else took it
            continue
        sender = claimed.get("from", "")
        _notify(realm_root, "inbox_task", f"{who} picked up a task from {sender}",
                str(claimed.get("ask", ""))[:200], _thread_href(agent_id, inbox.INBOX_THREAD))
        try:
            report = run_job_prompt(realm_root, agent_id, inbox.prompt_for(claimed),
                                    thread=inbox.INBOX_THREAD, engine=engine,
                                    allow_tools=True, label=f"inbox:{claimed.get('id')}")
            ok = (report or {}).get("status") == "ok"
            detail = (report or {}).get("summary") or ""
        except Exception as e:  # noqa — one bad task must not stop the rest of the batch
            swallowed(log, 'run_inbox: failed; recorded as an error')
            ok, detail = False, f"{type(e).__name__}: {e}"[:300]
        inbox.complete(realm_root, agent_id, claimed, ok, detail)
        handled += 1
        if not ok:
            failed += 1
            _notify(realm_root, "inbox_failed", f"{who} couldn't complete {sender}'s task",
                    detail[:200], _thread_href(agent_id, inbox.INBOX_THREAD))
    return {"ok": failed == 0, "handled": handled, "failed": failed}


def process_message_now(realm_root, agent_id: str, msg_id: str, engine="claude") -> dict:
    """Run one waiting message immediately, ignoring the agent's cadence.

    Cadence is a "how soon at the latest" promise; asking for it now is the owner overriding that,
    so it skips the wait but keeps every other rule — the message is still screened and still
    claimed before running, so this can't be used to bypass the hop limit or double-run a task.
    """
    from . import inbox
    realm_root = Path(realm_root)
    if not inbox.enabled(realm_root):
        return {"ok": False, "error": "Agent-to-agent tasks are switched off for this realm."}
    target = None
    for m in inbox._list(realm_root, agent_id, inbox.PENDING):
        if m.get("id") == msg_id:
            target = m
            break
    if not target:
        return {"ok": False, "error": "That message isn't waiting any more."}
    ok_to_run, why = inbox.screen(realm_root, agent_id, target)
    if not ok_to_run:
        claimed = inbox.claim(realm_root, agent_id, target)
        if claimed:
            inbox.complete(realm_root, agent_id, claimed, False, f"Not actioned: {why}.")
        return {"ok": False, "error": why}
    claimed = inbox.claim(realm_root, agent_id, target)
    if not claimed:
        return {"ok": False, "error": "That message was just picked up by the scheduler."}

    def _go():
        agent = _load_json(realm_root / "agents" / agent_id / "agent.json") or {}
        who = agent.get("display") or agent_id
        try:
            report = run_job_prompt(realm_root, agent_id, inbox.prompt_for(claimed),
                                    thread=inbox.INBOX_THREAD, engine=engine, allow_tools=True,
                                    label=f"inbox:{claimed.get('id')}")
            ok = (report or {}).get("status") == "ok"
            detail = (report or {}).get("summary") or ""
        except Exception as e:  # noqa
            swallowed(log, '_go: failed; recorded as an error')
            ok, detail = False, f"{type(e).__name__}: {e}"[:300]
        inbox.complete(realm_root, agent_id, claimed, ok, detail)
        if not ok:
            _notify(realm_root, "inbox_failed", f"{who} couldn't complete that task",
                    detail[:200], _thread_href(agent_id, inbox.INBOX_THREAD))
    # Off the request thread: an agent turn takes far longer than a click should wait.
    threading.Thread(target=_go, daemon=True).start()
    return {"ok": True, "started": True}


def dispatch_inboxes(realm_root, engine="claude") -> dict:
    """One pass across every agent. The expensive part happens only where mail is actually
    waiting — everything else is a directory listing."""
    from . import inbox
    realm_root = Path(realm_root)
    if not inbox.enabled(realm_root):
        return {"ok": True, "checked": 0, "handled": 0, "skipped": "disabled"}
    adir = realm_root / "agents"
    checked = handled = failed = 0
    if not adir.is_dir():
        return {"ok": True, "checked": 0, "handled": 0, "failed": 0}
    for d in sorted(p for p in adir.iterdir() if p.is_dir()):
        aid = d.name
        checked += 1
        if not inbox.has_mail(realm_root, aid):      # free
            continue
        if not inbox.due(realm_root, aid):           # its cadence hasn't elapsed yet
            continue
        r = run_inbox(realm_root, aid, engine=engine)
        handled += int(r.get("handled") or 0)
        failed += int(r.get("failed") or 0)
    # ok describes DELIVERY, not the tasks: a task that fails is reported to its sender and to the
    # bell, but the dispatcher did its job. Marking the pass failed would make the Jobs page say
    # inbox delivery is broken when it's working perfectly.
    return {"ok": True, "checked": checked, "handled": handled, "failed": failed}


def _write_report(agent_dir: Path, agent_id: str, report: dict) -> Path:
    runs = agent_dir / "runs"
    runs.mkdir(exist_ok=True)
    f = runs / f"{agent_id}.jsonl"
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report, ensure_ascii=False) + "\n")
    return f


def _run_command(realm_root: Path, agent_id: str, job_id: str, job: dict, agent_dir: Path) -> dict:
    """Deterministic job: run a shell command / script, capture status+output. No engine, no tokens.
    This is what runs the cabinet's Python collectors (collect_*.py, render_status.py, telegram push)."""
    cmd = job.get("run") or job.get("command", "")
    if not cmd:
        raise SystemExit(f"ARMADA: command job '{job_id}' has no 'run' field")
    # cwd defaults to the realm root (the cabinet scripts assume D:\Work\Hand-relative paths).
    cwd = job.get("cwd")
    cwd = str((realm_root / cwd) if cwd and not Path(cwd).is_absolute() else (cwd or realm_root))
    timeout = int(job.get("timeout", 300))
    argv = cmd if isinstance(cmd, list) else shlex.split(cmd, posix=(os.name != "nt"))
    # Force UTF-8 in the child: captured stdout is a pipe, so Windows defaults it to cp1252 and
    # any script that prints Unicode (─, ⚡, €, …) dies with UnicodeEncodeError. The cabinet's
    # scripts all print Unicode, so this makes them survive capture. Job env overrides last.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    # Make `python -m armada ...` work from a command job. Python only puts the CURRENT directory on
    # sys.path, and a command job runs in the realm (or a job-specified cwd), not in ARMADA's source
    # tree — so a job invoking ARMADA's own CLI died with "No module named armada" unless the
    # package happened to be pip-installed into the interpreter it named. ARMADA knows where it
    # lives; saying so costs nothing and removes a class of failure that looks like a broken venv.
    _pkg_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(
        [p for p in (_pkg_root, os.environ.get("PYTHONPATH", "")) if p])
    env.update({str(k): str(v) for k, v in (job.get("env") or {}).items()})
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", env=env,
                           creationflags=(0x08000000 if os.name == "nt" else 0))  # CREATE_NO_WINDOW
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        ok = p.returncode == 0
        rc = p.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        out, err, ok, rc = "", f"{type(e).__name__}: {e}", False, -1
    dur = round(time.time() - t0, 2)
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    # On failure the useful line is in stderr, even when the script also printed to stdout — taking
    # stdout's last line first meant a crashed job reported its last bit of progress as its summary.
    def _tail(s, n=2):
        lines = [ln for ln in (s or "").splitlines() if ln.strip()]
        return " · ".join(lines[-n:])[:300]
    tail = (_tail(err) or _tail(out)) if not ok else (_tail(out, 1) or _tail(err, 1))
    if not ok and rc not in (0, -1) and "exit" not in tail.lower():
        tail = f"{tail} (exit code {rc})" if tail else f"exited with code {rc}"
    report = {"ts": ts, "agent": agent_id, "task": job_id, "kind": "command",
              "cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
              "status": "ok" if ok else "error", "returncode": rc, "duration_s": dur,
              "summary": tail}
    f = _write_report(agent_dir, agent_id, report)
    _say(f"ARMADA run · {agent_id}/{job_id} · kind=command · {'OK' if ok else 'ERROR'} "
          f"(rc={rc}) · {dur}s")
    _say("─" * 60)
    _say(out or err or "(no output)")
    _say("─" * 60)
    _say(f"run-report → {f}")
    return report


def chat(realm_root, agent_id: str, thread: str, message: str,
         engine: EngineAdapter | str = "mock", allow_tools: bool = False) -> dict:
    """Ad-hoc owner↔agent turn in a thread (SPEC §5). Same context assembly as a job run:
    always-on core as system + thread history + the owner's message; appends the turn."""
    realm_root = Path(realm_root)
    eng = get_engine(engine) if isinstance(engine, str) else engine
    agent_dir = realm_root / "agents" / agent_id
    agent = _load_json(agent_dir / "agent.json")
    if not agent:
        raise SystemExit(f"ARMADA: no agent '{agent_id}'")
    core = memory.assemble_core(realm_root, agent_dir, agent)
    if allow_tools or bool(agent.get("allow_tools")):
        core = _tool_preamble(realm_root, agent_dir) + "\n" + core
    th = Thread(agent_dir, thread)
    th.compact_if_needed(eng, threshold_chars=_compact_threshold(realm_root, agent))
    convo = th.render()
    prompt = (convo + "\n\n---\nOwner: " + message) if convo else message
    _uses_tools = allow_tools or bool(agent.get("allow_tools"))
    # This is the non-streaming turn — it serves Telegram, which is as unattended as a job. It gets
    # the same capture and the same memory guardrail as the other two paths; it previously had
    # neither, so a turn arriving by Telegram recorded nothing it produced and was the one entry
    # point where a write into another agent's memory folder would not be reverted.
    mguard = _guard_snapshot(realm_root, agent_dir) if _uses_tools else None
    cap = _TurnCapture(realm_root, agent_dir, _uses_tools)
    _args = dict(system=core, prompt=prompt, model=_resolve_model(realm_root, agent) or None,
                 cwd=str(agent_dir), allow_tools=_uses_tools,
                 effort=_resolve_effort(realm_root, agent),
                 fallback_model=_resolve_fallback_model(realm_root, agent) or None,
                 max_budget_usd=_resolve_max_budget(realm_root, agent),
                 disallowed_tools=_disallowed_tools(realm_root, agent))
    if hasattr(eng, "run_stream"):
        # Stream only to see the tool events; nothing consumes them live here. Timeout passed
        # explicitly because run_stream's default is half of run's (see _DEFAULT_RUN_TIMEOUT).
        res = eng.run_stream(**_args, on_event=cap.on_event, timeout=_DEFAULT_RUN_TIMEOUT)
    else:
        res = eng.run(**_args)
    if mguard:
        n = _guard_restore(mguard)
        if n:
            log.warning("guardrail: reverted %d out-of-bounds memory write(s) by agent %s", n, agent_id)
    cap.finish()        # after the restore, so reverted files aren't listed as this turn's output
    # Same rule as the streaming path: the owner said something, so the thread records that they
    # said it, whether or not the agent managed to answer. This path serves Telegram, where a
    # message swallowed by a failed run is a message the owner has no way to see again.
    if res.ok and res.output:
        th.append(message, res.output, outputs=cap.outputs or None, caps=cap.caps or None)
    else:
        why = (res.error or "").strip() or "The run ended without producing a reply."
        t = th.begin_turn(message)
        th.complete_turn(t, why, status="error")
    _sync_proposals(realm_root, agent_id)
    _sync_cap_requests(realm_root, agent_id, thread)
    # Same run-report the streaming turn writes. This path serves Telegram and the plain /api/chat
    # endpoint, and it was the last one spending tokens that never reached the Usage widget — the
    # turn happened, the quota went down, and the day showed nothing. Best-effort, as there too:
    # telemetry must never be the reason a turn fails.
    try:
        _write_report(agent_dir, agent_id, {
            "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "agent": agent_id, "task": f"chat:{thread}", "thread": thread, "kind": "chat",
            "engine": getattr(eng, "name", "claude"), "model": res.model,
            "status": "ok" if res.ok else "error",
            "summary": (res.output.splitlines()[0][:200] if res.output else (res.error or "")[:200]),
            "tokens": res.usage.as_dict(),
        })
    except Exception:  # noqa — telemetry is not worth failing a chat turn over
        log.exception("usage log failed for %s chat turn on thread %s", agent_id, thread)
    return {"ok": res.ok, "output": res.output or res.error, "tokens": res.usage.as_dict(), "model": res.model}


def _save_images(agent_dir: Path, thread: str, images: list) -> list[dict]:
    """Decode data-URL images from the composer to files under the thread.
    Returns [{"path": abs, "file": basename, "name": original}] for saved images."""
    import base64
    out = []
    if not images:
        return out
    d = agent_dir / "threads" / thread / "attachments"
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for i, im in enumerate(images):
        data = str(im.get("data", ""))
        if "," in data and data.startswith("data:"):
            head, b64 = data.split(",", 1)
            ext = "png"
            if "image/" in head:
                ext = head.split("image/", 1)[1].split(";", 1)[0][:5] or "png"
            try:
                raw = base64.b64decode(b64)
            except Exception:  # noqa
                swallowed(log, '_save_images: failed; skipping this one')
                continue
            name = im.get("name") or f"image-{i}.{ext}"
            safe = "".join(c for c in name if c.isalnum() or c in "-_.") or f"image-{i}.{ext}"
            p = d / f"{stamp}-{i}-{safe}"
            if not p.suffix:
                p = p.with_suffix("." + ext)
            try:
                p.write_bytes(raw)
                out.append({"path": str(p), "file": p.name, "name": name})
            except Exception:  # noqa
                swallowed(log, '_save_images: failed; ignored')
    return out


def chat_stream(realm_root, agent_id: str, thread: str, message: str, on_event,
                engine: EngineAdapter | str = "claude", allow_tools: bool = False, on_proc=None,
                images: list | None = None, files: list | None = None) -> dict:
    """Streaming version of chat(): emits intermediate steps via on_event(dict) as the agent
    works, then appends the completed turn to the thread. Falls back to a single event for
    engines without run_stream (e.g. mock)."""
    realm_root = Path(realm_root)
    eng = get_engine(engine) if isinstance(engine, str) else engine
    agent_dir = realm_root / "agents" / agent_id
    agent = _load_json(agent_dir / "agent.json")
    if not agent:
        on_event({"kind": "error", "error": f"no agent '{agent_id}'"})
        return {"ok": False, "output": f"no agent '{agent_id}'"}
    # Attached images: save to disk and let the agent view them via its Read tool (which renders
    # images to the model). This turn needs tools even if the agent is otherwise propose-only.
    saved = _save_images(agent_dir, thread, images or [])
    # attachment refs to persist on the user turn (thumbnails for images, names for files)
    attach = [{"kind": "image", "name": s["name"], "file": s["file"]} for s in saved]
    attach += [{"kind": "file", "name": str(fn)} for fn in (files or []) if str(fn).strip()]
    use_tools = allow_tools or bool(agent.get("allow_tools")) or bool(saved)
    core = memory.assemble_core(realm_root, agent_dir, agent)
    if use_tools:
        core = _tool_preamble(realm_root, agent_dir) + "\n" + core
    th = Thread(agent_dir, thread)
    th.compact_if_needed(eng, threshold_chars=_compact_threshold(realm_root, agent))
    convo = th.render()
    msg = message
    if saved:
        paths = "; ".join(s["path"] for s in saved)   # saved is a list of dicts, not strings
        msg = (message + "\n\n" if message else "") + (
            f"[The owner attached {len(saved)} image(s), saved on this machine at: {paths}. "
            f"Use your Read tool to open and view each image, then respond taking them into account.]")
    prompt = (convo + "\n\n---\nOwner: " + msg) if convo else msg
    # Record the owner's message NOW — after rendering the history above, so it isn't in the
    # prompt twice. It used to be written only when the reply landed, which meant it existed
    # nowhere but the open browser tab while the agent worked: walk away from a long turn and the
    # thread you came back to had no record of what you'd asked, and a run that failed lost it for
    # good. The turn is closed below whatever happens, including on an error.
    turn = th.begin_turn(message, attachments=attach or None)
    mdl = _resolve_model(realm_root, agent) or None
    eff = _resolve_effort(realm_root, agent)
    fbm = _resolve_fallback_model(realm_root, agent) or None
    budg = _resolve_max_budget(realm_root, agent)
    # Capture the files the agent creates/edits this turn (Write/Edit tool-use) so the thread can list
    # them as OUTPUT artifacts. We sniff the tool events as they stream past, then persist on the turn.
    cap = _TurnCapture(realm_root, agent_dir, use_tools)

    def _cap(ev):
        cap.on_event(ev)
        on_event(ev)
    mguard = _guard_snapshot(realm_root, agent_dir) if use_tools else None   # protect other memories
    _disallow = _disallowed_tools(realm_root, agent)
    if not hasattr(eng, "run_stream"):
        res = eng.run(system=core, prompt=prompt, model=mdl,
                      cwd=str(agent_dir), allow_tools=use_tools, effort=eff,
                      fallback_model=fbm, max_budget_usd=budg, disallowed_tools=_disallow)
        on_event({"kind": "text", "text": res.output or ""})
    else:
        res = eng.run_stream(system=core, prompt=prompt, model=mdl, cwd=str(agent_dir),
                             allow_tools=use_tools, on_event=_cap, on_proc=on_proc, effort=eff,
                             fallback_model=fbm, max_budget_usd=budg, disallowed_tools=_disallow)
    if mguard:
        n = _guard_restore(mguard)                          # revert any writes outside its own memory
        if n:
            log.warning("guardrail: reverted %d out-of-bounds memory write(s) by agent %s", n, agent_id)
    cap.finish()        # after the restore, so reverted files aren't listed as this turn's output
    # Always close the turn. An owner message with nothing after it reads as the app having lost
    # the message, not as the agent having had a problem — so a failure says so in the thread,
    # where the question is, rather than only in a toast that is gone by the time you look.
    if res.ok and res.output:
        th.complete_turn(turn, res.output, outputs=cap.outputs or None, caps=cap.caps or None)
    else:
        why = (res.error or "").strip() or "The run ended without producing a reply."
        stopped = "stop" in why.lower()[:40]
        th.complete_turn(turn, why, status="stopped" if stopped else "error")
    _sync_proposals(realm_root, agent_id)   # record any job the agent just proposed (Write tool)
    _sync_cap_requests(realm_root, agent_id, thread)   # …and any capability it asked for
    # Log a run-report for this interactive turn so chat usage shows in the Usage widget. Previously
    # only scheduled/manual JOBS were logged, so live chat token use was invisible (and "today" stayed
    # empty even while chatting). Telemetry must never break the turn, so it's best-effort.
    try:
        _write_report(agent_dir, agent_id, {
            "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "agent": agent_id, "task": f"chat:{thread}", "thread": thread, "kind": "chat",
            "engine": getattr(eng, "name", "claude"), "model": res.model,
            "status": "ok" if res.ok else "error",
            "summary": (res.output.splitlines()[0][:200] if res.output else (res.error or "")[:200]),
            "tokens": res.usage.as_dict(),
        })
    except Exception:  # noqa — telemetry is not worth failing a chat turn over
        log.exception("usage log failed for %s chat turn on thread %s", agent_id, thread)
    return {"ok": res.ok, "output": res.output or res.error, "tokens": res.usage.as_dict(), "model": res.model}


def run_job(realm_root, agent_id: str, job_id: str, engine: EngineAdapter | str = "mock",
            thread: str = "main", allow_tools: bool = False) -> dict:
    realm_root = Path(realm_root)
    eng = get_engine(engine) if isinstance(engine, str) else engine
    agent_dir = realm_root / "agents" / agent_id
    agent = _load_json(agent_dir / "agent.json")
    if not agent:
        raise SystemExit(f"ARMADA: no agent '{agent_id}' at {agent_dir}")
    job = _load_json(agent_dir / "jobs" / f"{job_id}.json")
    if not job:
        raise SystemExit(f"ARMADA: no job '{job_id}' for agent '{agent_id}'")

    who = agent.get("display") or agent.get("name") or agent_id
    what = job.get("title") or job.get("name") or job_id
    link = _thread_href(agent_id, thread)     # the run's output and errors land in this thread
    _running_marker(agent_dir, job_id, True)
    _t0 = time.time()
    _notify(realm_root, "job_started", *_job_note("started", who, what, thread=thread), href=link)
    try:
        report = _run_job_inner(realm_root, agent_id, job_id, engine, thread, allow_tools,
                                eng, agent_dir, agent, job)
    except BaseException as e:  # noqa — tell the owner the job died, then let it propagate
        _notify(realm_root, "job_failed",
                *_job_note("failed", who, what, why=f"{type(e).__name__}: {e}"[:400],
                           took=time.time() - _t0, thread=thread), href=link)
        raise
    finally:
        _running_marker(agent_dir, job_id, False)
    _dur = (report or {}).get("duration_s") or (time.time() - _t0)
    if (report or {}).get("status") == "ok":
        _notify(realm_root, "job_finished",
                *_job_note("finished", who, what, why=(report.get("summary") or "")[:300],
                           took=_dur, thread=thread), href=link)
    else:
        # The summary IS the error for a failed run — the engine's message, or the script's last
        # line of stderr. Passing the job name instead (the old fallback) said nothing at all.
        _notify(realm_root, "job_failed",
                *_job_note("failed", who, what, why=(report or {}).get("summary") or "",
                           took=_dur, thread=thread), href=link)
    return report


def _run_job_inner(realm_root, agent_id, job_id, engine, thread, allow_tools,
                   eng, agent_dir, agent, job) -> dict:
    # Command jobs are deterministic scripts — no engine, no context, no tokens.
    if job.get("kind") == "command" or job.get("run") or job.get("command"):
        return _run_command(realm_root, agent_id, job_id, job, agent_dir)

    # SPEC §5 context assembly: always-on core (memory) as system + thread history in the prompt.
    core = memory.assemble_core(realm_root, agent_dir, agent)
    if allow_tools or bool(agent.get("allow_tools")):
        core = _tool_preamble(realm_root, agent_dir) + "\n" + core     # host/path parity + job-proposal contract
    th = Thread(agent_dir, thread)
    compacted = th.compact_if_needed(eng, threshold_chars=_compact_threshold(realm_root, agent, job))  # keep lean
    convo = th.render()
    # {workspace} is expanded here, at run time, and never written back to the job file: the stored
    # prompt stays portable however many times it runs.
    ask = workspace.expand(job.get("prompt", ""), realm_root)
    prompt = (convo + "\n\n---\nRequest: " + ask) if convo else ask

    job_model = _cli_model(job.get("model"), realm_root) if job.get("model") else _resolve_model(realm_root, agent)
    _uses_tools = allow_tools or bool(agent.get("allow_tools"))
    mguard = _guard_snapshot(realm_root, agent_dir) if _uses_tools else None
    cap = _TurnCapture(realm_root, agent_dir, _uses_tools)
    _tmo = _resolve_timeout(realm_root, job)      # per-job, else the realm default, else ours
    _args = dict(system=core, prompt=prompt, model=job_model or None,
                 cwd=str(agent_dir), allow_tools=_uses_tools, effort=_resolve_effort(realm_root, agent),
                 fallback_model=_resolve_fallback_model(realm_root, agent) or None,
                 max_budget_usd=_resolve_max_budget(realm_root, agent),
                 disallowed_tools=_disallowed_tools(realm_root, agent))
    if hasattr(eng, "run_stream"):
        # Stream the run so the turn can record which capabilities the job exercised: tool names
        # exist only in the event stream, so a non-streamed job could never report them. Pass the
        # timeout explicitly — run_stream's own default is half of run's, and a job's time limit
        # must not change because of which method happened to be called.
        res = eng.run_stream(**_args, on_event=cap.on_event, timeout=_tmo or _DEFAULT_RUN_TIMEOUT)
    else:
        res = eng.run(**_args, **({"timeout": _tmo} if _tmo else {}))
    if mguard:
        n = _guard_restore(mguard)
        if n:
            log.warning("guardrail: reverted %d out-of-bounds memory write(s) by job %s/%s", n, agent_id, job_id)
    cap.finish()        # after the restore, so reverted files aren't listed as this job's output
    if res.ok and res.output:
        # Record what the run produced. A job is the case that needs this most: nobody watched it
        # happen, so this entry is the only account of the files it wrote and the tools it used.
        th.append(ask, res.output, outputs=cap.outputs or None, caps=cap.caps or None)
    _sync_proposals(realm_root, agent_id)
    _sync_cap_requests(realm_root, agent_id, thread)

    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    report = {
        "ts": ts, "agent": agent_id, "task": job_id, "thread": thread, "engine": eng.name,
        "model": res.model, "status": "ok" if res.ok else "error", "compacted": compacted,
        "summary": (res.output.splitlines()[0][:200] if res.output else res.error[:200]),
        "tokens": res.usage.as_dict(),
    }
    if cap.stray:
        # The realm is meant to be self-contained. It can't be enforced, so it's recorded: on the
        # run report, so it survives, and in the log now, so it isn't only discoverable by someone
        # already looking for it.
        report["outside_root"] = cap.stray[:20]
        log.warning("job %s/%s wrote %d file(s) outside the app root: %s",
                    agent_id, job_id, len(cap.stray), "; ".join(cap.stray[:5]))
    runs = agent_dir / "runs"
    runs.mkdir(exist_ok=True)
    with (runs / f"{agent_id}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")

    st = memory.core_stats(realm_root, agent_dir, agent)
    _say(f"ARMADA run · {agent_id}/{job_id} · thread={thread} · engine={eng.name} model={res.model or '-'} · "
          f"{'OK' if res.ok else 'ERROR'} · tokens={res.usage.total} "
          f"(api-equiv ${res.usage.cost_usd:.4f} — subscription quota, not a $ charge)")
    _say(f"context · core: realm+{st['realm_memories']} realm-mem + agent+{st['agent_memories']} agent-mem"
          f" · thread history: {len(convo)} chars{' · COMPACTED' if compacted else ''}")
    _say("─" * 60)
    _say(res.output or res.error)
    _say("─" * 60)
    _say(f"run-report → {runs / (agent_id + '.jsonl')}  ·  thread → {th.dir}")
    return report
