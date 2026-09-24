"""Local scheduler (SPEC §8/§12) — the missing heart: fire jobs on their cadence.

ARMADA owns scheduling itself (no OS cron required), so a realm is self-contained and portable.
A job declares a `schedule` string; the scheduler decides when it's due, checks it hasn't already
run today (idempotent — via the run-reports the runner writes), and fires it through the runner
(command or agent). Timezone + grace window come from realm.json (matching the reference cabinet's
`timezone` + `grace_minutes`), so a job missed by a reboot still fires if we're inside the grace.

Two run modes (CLI):
  * daemon  — loop forever, tick every --interval seconds (the "runs on its own" experience).
  * --once  — a single pass: fire everything due right now, then exit (drive from Task Scheduler,
              or use in tests). Both share the same due-logic, so behaviour is identical.

Schedule grammar (deliberately small + human):
    "manual"                 never auto-fires
    "daily 14:00"            every day at 14:00
    "mon-fri 09:30"          weekdays
    "mon,wed,fri 08:00"      a day list
    "sat 09:00"              a single day
    "mon-sun 00:00"          explicit all-week
Days: mon tue wed thu fri sat sun · ranges (mon-fri) · lists (mon,wed) · daily/everyday = all 7.
"""
from __future__ import annotations
import contextlib, json, os, time, datetime, traceback
from pathlib import Path
from typing import Optional

from . import util as _util
import logging
from .util import swallowed
log = logging.getLogger(__name__)

_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAYIX = {d: i for i, d in enumerate(_DAYS)}
_CRON_DOW = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
_CRON_MON = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _cron_field(field: str, lo: int, hi: int, names: dict | None = None) -> set[int]:
    """Expand one cron field (*, a, a-b, a-b/n, */n, lists) into the set of values it matches."""
    field = field.strip().lower()
    out: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part in ("*", ""):
            a, b = lo, hi
        elif "-" in part:
            aa, bb = part.split("-", 1)
            a = names.get(aa, None) if names else None
            a = int(aa) if a is None else a
            b = names.get(bb, None) if names else None
            b = int(bb) if b is None else b
        else:
            v = names.get(part) if names else None
            v = int(part) if v is None else v
            a = b = v
        for x in range(a, b + 1, step):
            out.add(x)
    return {x for x in out if lo <= x <= hi}


def is_cron(s: str) -> bool:
    return len(s.strip().split()) == 5


def cron_match(expr: str, dt: datetime.datetime) -> bool:
    """Standard 5-field cron match (min hour dom month dow), Vixie DOM/DOW OR-semantics."""
    f = expr.strip().split()
    if len(f) != 5:
        return False
    mins = _cron_field(f[0], 0, 59)
    hours = _cron_field(f[1], 0, 23)
    doms = _cron_field(f[2], 1, 31)
    months = _cron_field(f[3], 1, 12, _CRON_MON)
    dows = {d % 7 for d in _cron_field(f[4], 0, 7, _CRON_DOW)}   # 7 -> 0 (Sunday)
    if dt.minute not in mins or dt.hour not in hours or dt.month not in months:
        return False
    dom_star = f[2].strip() == "*"
    dow_star = f[4].strip() == "*"
    dom_ok = dt.day in doms
    dow_ok = (dt.isoweekday() % 7) in dows          # cron dow: Sun=0..Sat=6
    if not dom_star and not dow_star:
        return dom_ok or dow_ok                      # Vixie: OR when both restricted
    return (dom_star or dom_ok) and (dow_star or dow_ok)


def cron_dow_days(field: str) -> set[int]:
    """The set of weekdays a cron day-of-week field covers (Sun=0 … Sat=6), or an empty set if it
    can't be read. Exposed so callers can reason about how often a schedule fires rather than
    comparing its spelling: '1-5', '1,2,3,4,5' and 'mon-fri' are one schedule written three ways."""
    try:
        return {d % 7 for d in _cron_field(field, 0, 7, _CRON_DOW)}
    except (ValueError, AttributeError, TypeError):
        return set()


_CRON_CACHE: dict = {}


def _cron_parse(expr: str):
    """Parse a 5-field cron once (cached): -> (mins, hours, doms, months, dows, dom_star, dow_star)."""
    if expr in _CRON_CACHE:
        return _CRON_CACHE[expr]
    f = expr.strip().split()
    if len(f) != 5:
        _CRON_CACHE[expr] = None
        return None
    parsed = (
        _cron_field(f[0], 0, 59), _cron_field(f[1], 0, 23), _cron_field(f[2], 1, 31),
        _cron_field(f[3], 1, 12, _CRON_MON), {d % 7 for d in _cron_field(f[4], 0, 7, _CRON_DOW)},
        f[2].strip() == "*", f[4].strip() == "*",
    )
    _CRON_CACHE[expr] = parsed
    return parsed


def cron_day_times(expr: str, day: "datetime.date") -> list[tuple[int, int]]:
    """The (hour, minute) fire times of `expr` on `day` — O(hours×minutes), not a 1440-min scan.
    Returns [] if the day doesn't match. Used to project a calendar cheaply."""
    p = _cron_parse(expr)
    if not p:
        return []
    mins, hours, doms, months, dows, dom_star, dow_star = p
    if day.month not in months:
        return []
    dom_ok = day.day in doms
    dow_ok = (day.isoweekday() % 7) in dows
    if not dom_star and not dow_star:
        day_ok = dom_ok or dow_ok
    else:
        day_ok = (dom_star or dom_ok) and (dow_star or dow_ok)
    if not day_ok:
        return []
    return [(h, m) for h in sorted(hours) for m in sorted(mins)]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


def _load_json(p: Path) -> dict:
    try:
        return json.loads(_read(p)) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


# --- the scheduler lock ------------------------------------------------------------------------
#
# The double-fire case: two schedulers ticking the same realm — a daemon left running in a
# forgotten terminal plus a second one started later, or a persistent daemon plus a Task
# Scheduler `--once` run landing in the same minute. `ran_today()` only closes the race after a
# job's run-report is written; a job that takes any real time to run is visible as "not yet run
# today" to a second ticker the whole time it's in flight, and both fire it. One lock file per
# realm, naming the pid that currently owns ticking it, closes that window regardless of which
# entry point (daemon loop or a one-shot CLI call) got there first.

def _lock_path(realm_root) -> Path:
    return Path(realm_root) / "scheduler.lock.json"


def lock_holder(realm_root) -> Optional[dict]:
    """{"pid": n, "started": iso} for whoever currently owns ticking this realm, or None if
    unowned. A recorded pid that is no longer running is a stale lock from a crash, not a live
    holder, and reads as unowned."""
    try:
        info = json.loads(_lock_path(realm_root).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not _util.pid_alive(info.get("pid")):
        return None
    return info


def _lock_acquire(realm_root) -> bool:
    """Claim the lock for this process. True if claimed — including if this process already held
    it, or the prior holder is dead — False if a different live process holds it."""
    holder = lock_holder(realm_root)
    if holder is not None and holder.get("pid") != os.getpid():
        return False
    try:
        _util.write_json_atomic(_lock_path(realm_root), {
            "pid": os.getpid(),
            "started": datetime.datetime.now().isoformat(timespec="seconds"),
        })
    except OSError:
        pass  # can't write a lock file here (permissions etc.) — proceed unlocked rather than
              # ever stopping a realm from scheduling entirely over a filesystem quirk
    return True


def _lock_release(realm_root) -> None:
    p = _lock_path(realm_root)
    try:
        info = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return
    if info.get("pid") == os.getpid():
        with contextlib.suppress(OSError):
            p.unlink()


def parse_days(spec: str) -> set[int]:
    spec = spec.strip().lower()
    if spec in ("daily", "everyday", "every-day", "all"):
        return set(range(7))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            if a in _DAYIX and b in _DAYIX:
                i, j = _DAYIX[a], _DAYIX[b]
                out.update(range(i, j + 1) if i <= j else list(range(i, 7)) + list(range(0, j + 1)))
        elif part in _DAYIX:
            out.add(_DAYIX[part])
    return out


def parse_schedule(sched: str) -> Optional[tuple[set[int], int, int]]:
    """-> (weekday_set, hour, minute) or None for manual/unparseable."""
    if not sched:
        return None
    s = sched.strip().lower()
    if s in ("manual", "none", "on-demand", ""):
        return None
    parts = s.rsplit(" ", 1)
    if len(parts) != 2 or ":" not in parts[1]:
        return None
    days = parse_days(parts[0])
    try:
        hh, mm = parts[1].split(":", 1)
        hh, mm = int(hh), int(mm)
    except ValueError:
        return None
    if not days or not (0 <= hh < 24 and 0 <= mm < 60):
        return None
    return days, hh, mm


def _tz(realm_cfg: dict):
    name = realm_cfg.get("timezone")
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception:  # noqa - missing tzdata etc.; fall back to local
            log.debug('_tz: failed; ignored', exc_info=True)
    return None  # local time


def now_in(realm_cfg: dict) -> datetime.datetime:
    """The current time in the realm's own timezone.

    Reads the clock through `armada.clock` rather than calling datetime directly: this is what the
    Jobs page uses for its week strip, so a golden render that freezes the clock has to be able to
    freeze this too. Unfrozen it is the same wall time it always was.
    """
    from . import clock
    tz = _tz(realm_cfg)
    n = clock.now()
    return n.astimezone(tz) if tz else n


def iter_jobs(realm_root: Path):
    """Yield (agent_id, job_id, job_dict) for every job in a native realm."""
    adir = realm_root / "agents"
    for ad in (sorted(p for p in adir.iterdir() if p.is_dir()) if adir.is_dir() else []):
        jdir = ad / "jobs"
        if not jdir.is_dir():
            continue
        for jf in sorted(jdir.glob("*.json")):
            jc = _load_json(jf)
            if jc:
                yield ad.name, jc.get("id", jf.stem), jc


def ran_today(realm_root: Path, agent_id: str, job_id: str, day_iso: str) -> bool:
    rf = realm_root / "agents" / agent_id / "runs" / f"{agent_id}.jsonl"
    if not rf.exists():
        return False
    for ln in _read(rf).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if ev.get("task") == job_id and str(ev.get("ts", ""))[:10] == day_iso:
            return True
    return False


def due_now(job: dict, now: datetime.datetime, grace_min: int) -> bool:
    if job.get("enabled") is False:
        return False
    # Cron path: an explicit `cron` field, or a `schedule` that's a 5-field cron expression.
    cron = job.get("cron")
    sched = job.get("schedule", "manual")
    if not cron and isinstance(sched, str) and is_cron(sched):
        cron = sched
    if cron:
        # Due if the cron fired at any minute within [now-grace, now] (grace catch-up after a reboot).
        base = now.replace(second=0, microsecond=0)
        for back in range(0, grace_min + 1):
            if cron_match(cron, base - datetime.timedelta(minutes=back)):
                return True
        return False
    # Simple grammar path: "<days> HH:MM".
    parsed = parse_schedule(sched)
    if not parsed:
        return False
    days, hh, mm = parsed
    if now.weekday() not in days:
        return False
    sched_today = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    delta = (now - sched_today).total_seconds()
    return 0 <= delta <= grace_min * 60      # due at/after the time, within the grace window


def tick(realm_root, engine: str = "claude", grace_min: Optional[int] = None,
         at: Optional[datetime.datetime] = None, dry_run: bool = False,
         *, _daemon_owned: bool = False) -> list[dict]:
    """One scheduling pass. Fire every due job not already run today. Returns fired-job records.

    `ran_today()` alone only closes the double-fire window AFTER a job's run-report lands; a job
    that takes any real time to run reads as "not yet run today" to a second ticker for the whole
    time it's in flight. `_daemon_owned` is set by run_daemon(), which holds the realm's scheduler
    lock for its whole lifetime; a standalone call (the CLI's `--once`/`--at`, or a route) takes
    the lock itself for just this pass, and backs off — firing nothing — if a live process already
    holds it, rather than risk running the same job twice.
    """
    from .runner import run_job
    realm_root = Path(realm_root)
    if not dry_run:
        # The scheduler opens every registered realm, not just the one on screen — so a realm
        # nobody has looked at since an upgrade still gets its format brought up to date (2.8).
        # Once per change to realm.json; a stat() on every other pass.
        from . import realmformat
        realmformat.ensure(realm_root)
    cfg = _load_json(realm_root / "realm.json")
    grace = grace_min if grace_min is not None else int(cfg.get("grace_minutes", 120))
    now = at or now_in(cfg)
    day_iso = now.date().isoformat()
    fired = []
    locked_here = False
    if not dry_run and not _daemon_owned:
        if not _lock_acquire(realm_root):
            holder = lock_holder(realm_root)
            return [{"agent": "system", "job": "scheduler-lock", "kind": "system", "status": "skipped",
                     "detail": f"another scheduler (pid {holder.get('pid') if holder else '?'}) "
                               "is already ticking this realm"}]
        locked_here = True
    try:
        # A realm that can't work here — no engine, or a workspace folder that doesn't exist on
        # this machine — is held rather than left to fail every job every night. Every run would
        # fail identically, and a week of identical failures is indistinguishable from broken.
        # The hold is released automatically the moment the preflight passes again.
        if not dry_run:
            try:
                from . import preflight
                why = preflight.hold_reason(realm_root)
                if why:
                    return [{"agent": "system", "job": "scheduler-hold", "kind": "system",
                             "status": "held", "detail": why}]
            except Exception:  # noqa — a broken check must not stop a realm that was working
                swallowed(log, 'tick: failed; ignored')
        # ARMADA's own recurring upkeep (model catalogue, capability updates, pruning). Interval-
        # based rather than cron, and self-contained: run_due never raises, so a broken
        # housekeeping job can't stop the owner's jobs from firing.
        if not dry_run:
            try:
                from . import sysjobs
                for r in sysjobs.run_due(realm_root):
                    fired.append({"agent": "system", "job": r.get("id"), "kind": "system",
                                  "status": "ok" if r.get("ok") else "error"})
            except Exception:  # noqa — upkeep must never break scheduling
                swallowed(log, 'tick: failed; ignored')
        for agent_id, job_id, job in iter_jobs(realm_root):
            # Switched off in the UI. Checked here rather than in due_now() so a manual "Run now"
            # still works on a disabled job — off means "does not fire on its own", not "cannot run".
            if job.get("enabled") is False:
                continue
            if not due_now(job, now, grace):
                continue
            if ran_today(realm_root, agent_id, job_id, day_iso):
                continue
            rec = {"agent": agent_id, "job": job_id, "kind": job.get("kind", "agent"),
                   "schedule": job.get("schedule") or job.get("cron")}
            if dry_run:
                rec["status"] = "would-fire"
                fired.append(rec)
                continue
            try:
                report = run_job(realm_root, agent_id, job_id, engine=engine,
                                 allow_tools=bool(job.get("allow_tools")))
                rec["status"] = report.get("status", "ok")
            except Exception as e:  # noqa - never let one job kill the loop
                swallowed(log, 'tick: failed; recorded as an error')
                rec["status"] = "error"
                rec["error"] = f"{type(e).__name__}: {e}"
                print(f"ARMADA scheduler: {agent_id}/{job_id} raised: {e}")
                traceback.print_exc()
            fired.append(rec)
        return fired
    finally:
        if locked_here:
            _lock_release(realm_root)


def _adopt_new_realms(rescan, owned: list, others: list) -> None:
    """Take on realms registered since the daemon started (created or added in the app while it
    was running). Without this, a new realm's jobs never fired until the scheduler was restarted —
    and the scheduler is the thing nobody restarts. A realm another live process already owns is
    left to it."""
    try:
        wanted = [Path(p) for p in (rescan() or [])]
    except Exception:  # noqa — a broken registry read must not stop the realms already ticking
        swallowed(log, "run_daemon: realm rescan failed; ignored")
        return
    have = {p.resolve() for p in owned}
    for p in wanted:
        try:
            if p.resolve() in have or not p.is_dir():
                continue
        except OSError:
            continue
        if _lock_acquire(p):
            owned.append(p)
            others.append(p)
            have.add(p.resolve())
            print(f"  also firing ▶ {p} (new since start)", flush=True)


def run_daemon(realm_root, engine: str = "claude", interval: int = 60,
               grace_min: Optional[int] = None, also: Optional[list] = None,
               rescan=None) -> int:
    """Fire due jobs until stopped. `also` names further realms to tick in the same pass.

    A realm's jobs are its own commitment; they do not stop mattering because you are looking at a
    different realm. One process ticks them all because the alternative — a daemon per realm — has
    each one separately discoverable, separately startable and separately forgettable, and the
    failure mode of forgetting is a realm that quietly never runs anything.

    `tick` is already self-contained per realm (its own timezone, grace, preflight hold and
    run-ledger), so this is a loop and not a merge. The Telegram listener is the exception: it
    long-polls one bot with one cursor, so a second listener would steal the first's updates. It
    runs for `realm_root` only, which is why that argument is the primary one rather than just the
    first of a list.

    `rescan`, when given (the CLI passes it when no realm was named, i.e. "every realm"), is called
    each pass for the current list of realms, so one created after start is picked up (5.5).
    """
    realm_root = Path(realm_root)
    others = [Path(p) for p in (also or []) if Path(p).resolve() != realm_root.resolve()]
    cfg = _load_json(realm_root / "realm.json")
    tzname = cfg.get("timezone", "local")
    # Claim the scheduler lock for every realm this process is about to tick, for the whole
    # lifetime of the daemon (released in the `finally` below) — not re-acquired each tick, which
    # is what makes tick() skip firing for _daemon_owned=True calls: this process already holds it.
    # The primary realm is why you ran this command; if it's already owned, refuse to start a
    # second daemon over it rather than silently doing nothing useful. An `also` realm already
    # owned by someone else is dropped from this run instead — the primary realm still gets its
    # scheduler.
    if not _lock_acquire(realm_root):
        holder = lock_holder(realm_root)
        print(f"ARMADA scheduler ▶ {realm_root} is already being scheduled by another process "
              f"(pid {holder.get('pid') if holder else '?'}, started {holder.get('started', '?') if holder else '?'}). "
              "Not starting a second one.", flush=True)
        return 1
    owned = [realm_root]
    for p in others:
        if _lock_acquire(p):
            owned.append(p)
        else:
            holder = lock_holder(p)
            print(f"  ⚠ {p} is already being scheduled by another process "
                  f"(pid {holder.get('pid') if holder else '?'}) — skipping it here", flush=True)
    others = [p for p in others if p in owned]
    # Collect temp files an earlier run left behind when it was killed mid-write. This process is
    # the usual culprit — the Telegram listener rewrites its cursor constantly — and nothing else
    # ever cleans them up.
    try:
        from . import util as _util
        _n = _util.sweep_temp_files(realm_root)
        if _n:
            print(f"  swept {_n} stale temp file(s) from an interrupted write", flush=True)
    except Exception:  # noqa — housekeeping must never stop the scheduler starting
        swallowed(log, 'run_daemon: failed; ignored')
    # Line-buffer stdout so a long-running daemon's output appears live (not stuck in a pipe buffer).
    try:
        import sys as _sys
        _sys.stdout.reconfigure(line_buffering=True)
    except Exception:  # noqa
        log.debug('run_daemon: failed; ignored', exc_info=True)
    # Telegram gets its own long-poll thread rather than riding the tick: an acknowledgement is only
    # as fast as the pass that sends it, and a minute-late "message received" is worse than none.
    # This is the always-on process, so it's where the listener belongs.
    try:
        from . import telegram as _tg
        if _tg.start_listener(realm_root, engine):
            print("  Telegram listener ▶ answering messages as they arrive", flush=True)
    except Exception:  # noqa — Telegram must never stop jobs from running
        swallowed(log, 'run_daemon: failed; ignored')
    print(f"ARMADA scheduler ▶ {realm_root}  ·  engine={engine}  ·  tz={tzname}  ·  "
          f"tick={interval}s  ·  grace={grace_min if grace_min is not None else cfg.get('grace_minutes', 120)}m", flush=True)
    for p in others:
        print(f"  also firing ▶ {p}", flush=True)
    print("  (Ctrl-C to stop. Jobs fire once per day when due; missed jobs catch up within grace.)", flush=True)
    try:
        while True:
            now = now_in(cfg)
            if rescan is not None:
                _adopt_new_realms(rescan, owned, others)
            for p in [realm_root, *others]:
                # One realm's problem is its own. A folder that has been moved or deleted since
                # startup must not take the other realms' jobs down with it.
                try:
                    # _daemon_owned=True: this process already holds p's scheduler lock for the
                    # whole run (acquired above), so tick() fires straight away rather than trying
                    # to re-acquire a lock it's already holding.
                    fired = tick(p, engine=engine, grace_min=grace_min, _daemon_owned=True)
                except Exception as e:  # noqa
                    swallowed(log, 'run_daemon: failed; reported to the caller')
                    print(f"  [{now.strftime('%H:%M')}] {p.name}: tick failed — {e}", flush=True)
                    continue
                where = "" if p == realm_root else f"{p.name}: "
                for r in fired:
                    print(f"  [{now.strftime('%H:%M')}] {where}fired {r['agent']}/{r['job']} "
                          f"({r['kind']}) → {r['status']}", flush=True)
            time.sleep(max(5, interval))
    except KeyboardInterrupt:
        print("\nARMADA scheduler stopped.")
    finally:
        for p in owned:
            _lock_release(p)
        return 0
