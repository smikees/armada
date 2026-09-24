"""ARMADA CLI. Verbs: open (P1 cockpit) · run (P2) · doctor (P2) · serve (P2 dogfood).
Later: new, provision.
"""
from __future__ import annotations
import argparse, sys, datetime
from pathlib import Path
import logging
log = logging.getLogger(__name__)


def _print_fired(fired: list, now) -> None:
    stamp = now.strftime("%a %H:%M") if hasattr(now, "strftime") else str(now)
    if not fired:
        print(f"ARMADA schedule · {stamp} · nothing due.")
        return
    verb = "would fire" if any(r.get("status") == "would-fire" for r in fired) else "fired"
    print(f"ARMADA schedule · {stamp} · {verb} {len(fired)} job(s):")
    for r in fired:
        print(f"  · {r['agent']}/{r['job']} ({r.get('kind','agent')}) [{r.get('schedule')}] → {r.get('status')}")


def _utf8_console() -> None:
    """Make stdout/stderr able to carry the characters ARMADA actually prints.

    Its output uses '─', '·' and '→'. On Windows the stream we inherit is frequently cp1252 — a
    pipe, a redirected file, or a handle passed down by whatever launched us — and encoding those
    characters raises. Guarding every print is the safety net (see runner._say); this is the fix
    that keeps the output readable instead of merely non-fatal.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa — an unreconfigurable stream is fine; _say still guards it
            log.debug('_utf8_console: failed; ignored', exc_info=True)


def main(argv=None):
    _utf8_console()
    # Force UTF-8 stdout/stderr: ARMADA prints ─/✓/● etc., which crash under Windows' default
    # cp1252 when output is captured or redirected (not a live console). Never let a glyph kill a run.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa
            log.debug('main: failed; ignored', exc_info=True)

    from . import __version__
    ap = argparse.ArgumentParser(prog="armada",
                                 description=f"ARMADA — your standing team of minds (v{__version__})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open", help="render a read-only cockpit HTML for a realm")
    o.add_argument("realm")
    o.add_argument("--out", default=None)

    r = sub.add_parser("run", help="run one agent job through an engine (writes a tokenized run-report)")
    r.add_argument("realm"); r.add_argument("agent"); r.add_argument("job")
    r.add_argument("--engine", default="mock", help="mock (offline, default) | claude")
    r.add_argument("--thread", default="main", help="thread to run in (default: main; sub-threads scope context)")
    r.add_argument("--allow-tools", action="store_true", help="let the agent use tools (autonomy-gated)")

    t = sub.add_parser("threads", help="list an agent's threads and their sizes")
    t.add_argument("realm"); t.add_argument("agent")

    n = sub.add_parser("new", help="scaffold a new realm from a template")
    n.add_argument("folder")
    n.add_argument("--template", default="scratch", help="state | company | crew | scratch")
    n.add_argument("--name", default=None, help="realm display name")

    sk = sub.add_parser("skills", help="provision agent skills (pinned + scoped) and the manifest.lock")
    sksub = sk.add_subparsers(dest="skcmd", required=True)
    skl = sksub.add_parser("list", help="show skills per agent + lockfile warnings")
    skl.add_argument("realm"); skl.add_argument("agent", nargs="?", default=None)
    ska = sksub.add_parser("add", help="add/replace a skill on an agent")
    ska.add_argument("realm"); ska.add_argument("agent"); ska.add_argument("skill")
    ska.add_argument("--source", default="builtin", help="builtin | npx:<pkg> | uvx:<pkg> | path:<...>")
    ska.add_argument("--version", default="*", help="pin a version (default '*' = unpinned)")
    ska.add_argument("--scope", default="", help="comma list: files,network,connectors,shell")
    skr = sksub.add_parser("rm", help="remove a skill from an agent")
    skr.add_argument("realm"); skr.add_argument("agent"); skr.add_argument("skill")
    skk = sksub.add_parser("lock", help="regenerate manifest.lock from all agents' skills")
    skk.add_argument("realm")

    # Like serve/app, `realm` is optional — but it means something different here. There it is
    # "which realm am I looking at" (one). Here it is "whose jobs do I fire", and the answer with
    # nothing named is every realm ARMADA knows about: a realm's schedule is its own commitment and
    # doesn't pause because you're viewing somewhere else.
    sc = sub.add_parser("schedule", help="fire jobs on their cadence (daemon, or a single --once pass)")
    sc.add_argument("realm", nargs="?", default="",
                    help="realm folder (default: every realm ARMADA knows about)")
    sc.add_argument("--engine", default="claude", help="engine for agent jobs (mock | claude)")
    sc.add_argument("--once", action="store_true", help="single pass: fire what's due now, then exit")
    sc.add_argument("--interval", type=int, default=60, help="daemon tick seconds (default 60)")
    sc.add_argument("--grace", type=int, default=None, help="override grace minutes")
    sc.add_argument("--dry-run", action="store_true", help="show what would fire; run nothing")
    sc.add_argument("--at", default=None, help="simulate a wall-clock time (ISO or HH:MM) — testing")

    v = sub.add_parser("validate", help="is this folder a runnable native realm? what's present/missing?")
    v.add_argument("folder")

    d = sub.add_parser("doctor", help="preflight: check Python, Git, the engine, and the realm")
    d.add_argument("--realm", default=None)
    d.add_argument("--engine", default="claude")

    # `realm` is optional on serve/app: with no folder named they reopen the last realm you were
    # in (~/.armada/config.json). Naming one still wins, and becomes the remembered one.
    s = sub.add_parser("serve", help="local web cockpit with Update & Restart (dogfood loop)")
    s.add_argument("realm", nargs="?", default="", help="realm folder (default: the last one opened)")
    s.add_argument("--port", type=int, default=8756)

    aw = sub.add_parser("app", help="open ARMADA in a native desktop window (pywebview)")
    aw.add_argument("realm", nargs="?", default="", help="realm folder (default: the last one opened)")
    aw.add_argument("--port", type=int, default=8756)

    sr = sub.add_parser("system-refresh", help="regenerate the read-only System memory from live realm data")
    sr.add_argument("realm", nargs="?", default=".")
    sr.add_argument("--trigger", default="daily-job")

    rm = sub.add_parser("refresh-models", help="sync the model catalog from Claude's live /v1/models list")
    rm.add_argument("realm", nargs="?", default=".")

    args = ap.parse_args(argv)

    if args.cmd == "system-refresh":
        from . import memory
        r = memory.refresh_system_memory(args.realm, trigger=args.trigger)
        print(f"ARMADA system-refresh: {'updated' if r['changed'] else 'no change'} · {r['path']}")
        return 0

    if args.cmd == "refresh-models":
        from . import models
        r = models.refresh(args.realm)
        if r.get("ok"):
            print(f"ARMADA refresh-models: {r['count']} models ({r['active']} active)"
                  + (f" · added {r['added']}" if r['added'] else "")
                  + (f" · retired {r['retired']}" if r['retired'] else ""))
        else:
            print(f"ARMADA refresh-models: skipped ({r.get('reason', 'unavailable')}) — "
                  "token expired/absent; runs refresh it")
        return 0

    if args.cmd == "open":
        from . import reader, render
        realm = reader.read(args.realm)
        out = Path(args.out) if args.out else Path(__file__).resolve().parents[1] / "prototype-output" / "cockpit.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render.render(realm), encoding="utf-8")
        print(f"ARMADA: {len(realm.members)} agents / {sum(len(a.jobs) for a in realm.agents)} jobs -> {out}")
        return 0

    if args.cmd == "run":
        from .runner import run_job
        run_job(args.realm, args.agent, args.job, engine=args.engine,
                thread=args.thread, allow_tools=args.allow_tools)
        return 0

    if args.cmd == "threads":
        from .threads import Thread
        adir = Path(args.realm) / "agents" / args.agent
        names = Thread.list_threads(adir)
        if not names:
            print(f"{args.agent}: no threads yet.")
            return 0
        print(f"{args.agent} threads:")
        for n in names:
            th = Thread(adir, n)
            msgs = len(th._messages())
            has_sum = "summary" if th.summary() else "—"
            print(f"  · {n:16s} {msgs} msgs · {len(th.render())} chars · {has_sum}")
        return 0

    if args.cmd == "schedule":
        from . import activerealm, scheduler, util as _util
        # The scheduler is its own process (windowless under SCHEDULER.vbs): without its own log
        # file, every failure the runner and the system jobs log would go nowhere.
        _util.init_logging("scheduler.log")
        # With no realm named, fire every realm ARMADA knows about — the active one first, so it
        # owns the Telegram listener and its jobs go first in each pass.
        every = activerealm.every() if not args.realm else []
        if not args.realm:
            if not every:
                print(activerealm.no_realm_message())
                return 2
            args.realm, extra = every[0], every[1:]
        else:
            extra = []
        if args.at is not None:
            # allow "HH:MM" (today) or a full ISO datetime, for deterministic testing
            cfg = scheduler._load_json(Path(args.realm) / "realm.json")
            base = scheduler.now_in(cfg)
            if ":" in args.at and "T" not in args.at and len(args.at) <= 5:
                hh, mm = args.at.split(":"); at = base.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            else:
                at = datetime.datetime.fromisoformat(args.at)
                if at.tzinfo is None and base.tzinfo is not None:
                    at = at.replace(tzinfo=base.tzinfo)
            fired = []
            for _r in [args.realm, *extra]:
                fired += scheduler.tick(_r, engine=args.engine, grace_min=args.grace,
                                        at=at, dry_run=args.dry_run)
            _print_fired(fired, at)
            return 0
        if args.once or args.dry_run:
            fired = []
            for _r in [args.realm, *extra]:
                fired += scheduler.tick(_r, engine=args.engine, grace_min=args.grace,
                                        dry_run=args.dry_run)
            _print_fired(fired, scheduler.now_in(scheduler._load_json(Path(args.realm) / "realm.json")))
            return 0
        return scheduler.run_daemon(args.realm, also=extra, engine=args.engine, interval=args.interval,
                                    grace_min=args.grace,
                                    rescan=activerealm.every if every else None)

    if args.cmd == "new":
        from .setup import scaffold
        scaffold(args.folder, args.template, args.name)
        return 0

    if args.cmd == "skills":
        from . import skills as sk
        from pathlib import Path as _P
        if args.skcmd == "add":
            scopes = [s.strip() for s in args.scope.split(",") if s.strip()]
            sk.add(args.realm, args.agent, args.skill, source=args.source,
                   version=args.version, scopes=scopes)
            print(f"ARMADA: {args.agent} ← {args.skill}@{args.version} "
                  f"[{args.source}]{' scopes: ' + ','.join(scopes) if scopes else ''}  ·  manifest.lock updated")
            return 0
        if args.skcmd == "rm":
            sk.remove(args.realm, args.agent, args.skill)
            print(f"ARMADA: {args.agent} ✕ {args.skill}  ·  manifest.lock updated")
            return 0
        if args.skcmd == "lock":
            f = sk.lock(args.realm)
            print(f"ARMADA: manifest.lock regenerated → {f}")
            return 0
        # list
        adir = _P(args.realm) / "agents"
        agents = [args.agent] if args.agent else [
            p.name for p in sorted(adir.iterdir()) if p.is_dir()] if adir.is_dir() else []
        any_sk = False
        for aid in agents:
            skl = sk.load(args.realm, aid)
            if not skl:
                print(f"  {aid}: (no skills)")
                continue
            any_sk = True
            print(f"  {aid}:")
            for s in skl:
                pin = s.version if s.version != "*" else "*(unpinned)"
                sc = ("  scopes=" + ",".join(s.scopes)) if s.scopes else ""
                print(f"    · {s.id}@{pin}  [{s.source}]{sc}")
        sk.lock(args.realm)  # keep the lock fresh
        if not any_sk:
            print("  No skills declared. Add one:  armada skills add <realm> <agent> <id> --version 1.0 --scope files,network")
        return 0

    if args.cmd == "validate":
        from . import validate
        return validate.run(args.folder)

    if args.cmd == "doctor":
        from . import doctor
        return doctor.run(args.realm, args.engine)

    if args.cmd in ("serve", "app"):
        # No folder on the command line means "open where I left off" — see activerealm. A
        # launcher (shortcut, .vbs, Start menu entry) is written once and then points at whatever
        # realm existed that day; leaving the path out of it is what lets switching realms in the
        # app survive closing the app.
        from . import activerealm
        realm = activerealm.resolve(args.realm)
        note = ""
        if realm and not activerealm.is_realm(realm):
            # Named (or remembered) but not a realm any more — moved, deleted, a drive not mounted.
            note = f"{realm} isn't a realm folder any more. Open another realm, or create one."
            realm = ""
        if not realm:
            # First run, or nothing to open (5.3). Under pythonw a printed sentence reaches no one
            # and the app seemed not to start at all; the window opens on the welcome page instead.
            print(note or activerealm.no_realm_message())
            from .serve import Handler
            Handler.welcome_note = note
        else:
            activerealm.remember(realm)
        # Under pythonw (the launchers, and Update & Restart's re-exec) there's no console, so a
        # start-up failure that isn't logged is invisible: the window or server just never appears.
        try:
            if args.cmd == "serve":
                from .serve import serve
                serve(realm, args.port)
                return 0
            from .app import run
            return run(realm, args.port)
        except Exception:
            import logging
            from . import util as _util
            _util.init_logging("armada.log")
            logging.getLogger("armada.cli").exception("%s failed to start (realm=%r)", args.cmd, realm)
            raise


if __name__ == "__main__":
    sys.exit(main())
