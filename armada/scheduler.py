"""Local scheduler (SPEC §8/§12) — the missing heart: fire jobs on their cadence.

ARMADA owns scheduling itself (no OS cron required), so a realm is self-contained and portable.
A job declares a `schedule` string; the scheduler decides when it's due, checks today's reports,
durably claims today's attempt before dispatch, and fires it through the runner
(command or agent). Timezone and grace window come from realm.json, so a job
missed by a reboot still fires within the configured grace window.

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
    "0 8 * * sat#1"         first Saturday of each month (Armada cron extension)
Days: mon tue wed thu fri sat sun · ranges (mon-fri) · lists (mon,wed) · daily/everyday = all 7.
"""
from __future__ import annotations
import json, time, datetime, traceback
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


def _nth_weekday(field: str) -> tuple[int, int] | None:
    """Armada's ``weekday#occurrence`` extension, e.g. ``sat#1`` for first Saturday."""
    if "#" not in field:
        return None
    weekday, separator, ordinal = field.lower().partition("#")
    if not separator or not ordinal.isdigit() or not 1 <= int(ordinal) <= 5:
        raise ValueError(f"Invalid nth-weekday cron field: {field}")
    days = _cron_field(weekday, 0, 7, _CRON_DOW)
    if len(days) != 1:
        raise ValueError(f"Invalid nth-weekday cron field: {field}")
    return (next(iter(days)) % 7, int(ordinal))


def _weekday_matches(field: str, day: "datetime.date") -> bool:
    nth = _nth_weekday(field)
    weekday = day.isoweekday() % 7
    if nth is not None:
        return weekday == nth[0] and (day.day - 1) // 7 + 1 == nth[1]
    return weekday in {d % 7 for d in _cron_field(field, 0, 7, _CRON_DOW)}


def cron_match(expr: str, dt: datetime.datetime) -> bool:
    """Standard 5-field cron match (min hour dom month dow), Vixie DOM/DOW OR-semantics."""
    f = expr.strip().split()
    if len(f) != 5:
        return False
    mins = _cron_field(f[0], 0, 59)
    hours = _cron_field(f[1], 0, 23)
    doms = _cron_field(f[2], 1, 31)
    months = _cron_field(f[3], 1, 12, _CRON_MON)
    if dt.minute not in mins or dt.hour not in hours or dt.month not in months:
        return False
    dom_star = f[2].strip() == "*"
    dow_star = f[4].strip() == "*"
    dom_ok = dt.day in doms
    dow_ok = _weekday_matches(f[4], dt.date())
    if not dom_star and not dow_star:
        return dom_ok or dow_ok                      # Vixie: OR when both restricted
    return (dom_star or dom_ok) and (dow_star or dow_ok)


def cron_dow_days(field: str) -> set[int]:
    """The set of weekdays a cron day-of-week field covers (Sun=0 … Sat=6), or an empty set if it
    can't be read. Exposed so callers can reason about how often a schedule fires rather than
    comparing its spelling: '1-5', '1,2,3,4,5' and 'mon-fri' are one schedule written three ways."""
    try:
        nth = _nth_weekday(field)
        if nth is not None:
            return {nth[0]}
        return {d % 7 for d in _cron_field(field, 0, 7, _CRON_DOW)}
    except (ValueError, AttributeError, TypeError):
        return set()


_CRON_CACHE: dict = {}


def _cron_parse(expr: str):
    """Parse a 5-field cron once (cached): -> (mins, hours, doms, months, dow_field, dom_star, dow_star)."""
    if expr in _CRON_CACHE:
        return _CRON_CACHE[expr]
    f = expr.strip().split()
    if len(f) != 5:
        _CRON_CACHE[expr] = None
        return None
    parsed = (
        _cron_field(f[0], 0, 59), _cron_field(f[1], 0, 23), _cron_field(f[2], 1, 31),
        _cron_field(f[3], 1, 12, _CRON_MON), f[4],
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
    dow_ok = _weekday_matches(dows, day)
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


# Keep the historical helper names for callers; ownership itself lives in a small state module.
from . import scheduler_state as _state
from .scheduler_state import acquire as _lock_acquire, release as _lock_release, holder as lock_holder


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


class TimezoneError(ValueError):
    """A configured realm clock must never silently become the machine clock."""


def _tz(realm_cfg: dict):
    name = realm_cfg.get("timezone")
    if not name or name == "local":
        return None  # Both existing local settings and an unset zone follow the machine.
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except (ValueError, KeyError, TypeError) as exc:
        raise TimezoneError(f"Cannot resolve realm timezone {name!r}. Choose a valid IANA timezone in Settings, or repair the installation's timezone data.") from exc


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


def ran_today(realm_root: Path, agent_id: str, job_id: str, day_iso: str,
              not_before: datetime.datetime | None = None) -> bool:
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
            if not_before is not None:
                try:
                    recorded = datetime.datetime.fromisoformat(ev["ts"])
                    if recorded.tzinfo is None:
                        recorded = recorded.replace(tzinfo=not_before.tzinfo)
                    elif not_before.tzinfo is None:
                        recorded = recorded.replace(tzinfo=None)
                    if recorded < not_before:
                        continue  # Overnight catch-up is not today's later scheduled run.
                except (ValueError, TypeError):
                    continue
            return True
    return False


def due_now(job: dict, now: datetime.datetime, grace_min: int) -> bool:
    return _due_time(job, now, grace_min) is not None


def _due_time(job: dict, now: datetime.datetime, grace_min: int):
    """Most recent due fire time. Catch-up claims belong to its day, even after midnight."""
    if job.get("enabled") is False:
        return None
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
                return base - datetime.timedelta(minutes=back)
        return None
    # Simple grammar path: "<days> HH:MM".
    parsed = parse_schedule(sched)
    if not parsed:
        return None
    days, hh, mm = parsed
    for back in range(grace_min // 1440 + 2):
        day = now - datetime.timedelta(days=back)
        if day.weekday() not in days:
            continue
        fire = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if 0 <= (now - fire).total_seconds() <= grace_min * 60:
            return fire
    return None


def _first_fire(job, fire):
    """Keep the once-per-scheduled-day contract for cadences with multiple daily fires."""
    cron = job.get("cron") or job.get("schedule", "")
    times = cron_day_times(cron, fire.date()) if is_cron(cron) else []
    return fire.replace(hour=times[0][0], minute=times[0][1]) if times else fire


def tick(realm_root, engine: str = "auto", grace_min: Optional[int] = None,
         at: Optional[datetime.datetime] = None, dry_run: bool = False,
         *, _lease: _state.Lease | None = None) -> list[dict]:
    """One pass, with at most one automatic attempt per job and realm-local day.

    A daemon passes its actual lease, never a boolean bypass. Every caller also takes that
    lease's non-reentrant gate, so overlapping calls within the daemon cannot dispatch twice.
    An uncompleted durable claim is held for inspection, not retried after a crash.
    """
    from .runner import run_job
    realm_root = Path(realm_root)
    from . import realmops
    if not ((realm_root / "realm.json").is_file() or (realm_root / "cabinet" / "schedule.json").is_file()):
        return [{"agent": "system", "job": "realm-missing", "kind": "system", "status": "held",
                 "detail": "This realm no longer exists."}]
    try:
        if realmops.archived(realm_root):
            return [{"agent": "system", "job": "realm-archived", "kind": "system", "status": "held",
                     "detail": "This realm is archived. All jobs are switched off."}]
    except (OSError, ValueError) as exc:
        return [{"agent": "system", "job": "schema-hold", "kind": "system", "status": "held", "detail": str(exc)}]
    if not dry_run:
        try:
            _util.assert_realm_writable(realm_root / "realm.json")
        except OSError as exc:
            return [{"agent": "system", "job": "schema-hold", "kind": "system", "status": "held", "detail": str(exc)}]
        # The scheduler opens every registered realm, not just the one on screen — so a realm
        # nobody has looked at since an upgrade still gets its format brought up to date (2.8).
        # Once per change to realm.json; a stat() on every other pass.
        from . import realmformat
        realmformat.ensure(realm_root)
    cfg = _load_json(realm_root / "realm.json")
    grace = grace_min if grace_min is not None else int(cfg.get("grace_minutes", 120))
    try:
        _tz(cfg)  # Validate even when a caller supplies a preview clock.
        now = at or now_in(cfg)
    except TimezoneError as exc:
        return [{"agent": "system", "job": "timezone-hold", "kind": "system",
                 "status": "held", "detail": str(exc)}]
    day_iso = now.date().isoformat()
    fired = []
    lease = _lease
    locked_here = False
    if not dry_run:
        try:
            if lease is None:
                lease = _lock_acquire(realm_root)
                locked_here = lease is not None
            if lease is None or not lease._gate.acquire(blocking=False):
                info = lock_holder(realm_root) or {}
                return [{"agent": "system", "job": "scheduler-lock", "kind": "system",
                         "status": "skipped", "detail": f"Another scheduler pass (pid {info.get('pid', '?')}) owns this realm."}]
        except OSError as exc:
            return [{"agent": "system", "job": "scheduler-lock", "kind": "system",
                     "status": "held", "detail": str(exc)}]
    try:
        if not dry_run:
            try:
                lease.verify(realm_root)
            except OSError as exc:
                return [{"agent": "system", "job": "scheduler-lock", "kind": "system",
                         "status": "held", "detail": str(exc)}]
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
                                  "status": r.get("status", "ok" if r.get("ok") else "error"),
                                  "detail": r.get("detail") or r.get("error") or ""})
            except Exception:  # noqa — upkeep must never break scheduling
                swallowed(log, 'tick: failed; ignored')
        for agent_id, job_id, job in iter_jobs(realm_root):
            if realmops.archived(realm_root):
                break
            # Switched off in the UI. Checked here rather than in due_now() so a manual "Run now"
            # still works on a disabled job — off means "does not fire on its own", not "cannot run".
            if job.get("enabled") is False:
                continue
            from . import job_retries
            try:
                waiting = job_retries.pending(realm_root, agent_id, job_id)
            except OSError as exc:
                fired.append({"agent": agent_id, "job": job_id, "kind": job.get("kind", "agent"),
                              "status": "held", "detail": str(exc)})
                continue
            fire = _due_time(job, now, grace)
            if waiting:
                # Resume only a recorded backoff, including outside catch-up grace.
                fire = datetime.datetime.fromtimestamp(waiting['started_at'], now.tzinfo)
            if fire is None:
                continue
            day_iso = fire.date().isoformat()
            if not waiting and ran_today(realm_root, agent_id, job_id, day_iso, not_before=_first_fire(job, fire)):
                continue
            rec = {"agent": agent_id, "job": job_id, "kind": job.get("kind", "agent"),
                   "schedule": job.get("schedule") or job.get("cron")}
            if dry_run:
                try:
                    attempt = _state.inspect_attempt(realm_root, agent_id, job_id, day_iso)
                except OSError as exc:
                    rec.update(status="held", detail=str(exc))
                    fired.append(rec)
                    continue
                if attempt:
                    if attempt["state"] == "claimed":
                        rec.update(status="held", detail="Previous attempt has no recorded outcome; inspect before using Run now.")
                        fired.append(rec)
                    continue
                rec["status"] = "would-fire"
                fired.append(rec)
                continue
            try:
                attempt, fresh = _state.claim(lease, agent_id, job_id, day_iso)
            except OSError as exc:
                rec.update(status="held", detail=f"Could not claim job attempt: {exc}")
                fired.append(rec)
                continue
            if not fresh and waiting:
                try:
                    attempt = _state.resume_waiting(lease, agent_id, job_id, day_iso)
                except OSError as exc:
                    rec.update(status="held", detail=str(exc))
                    fired.append(rec)
                    continue
                fresh = True
            if not fresh:
                if attempt["state"] == "claimed":
                    rec.update(status="held", detail="Previous attempt has no recorded outcome; inspect before using Run now.",
                               attempt_id=attempt["attempt_id"])
                    fired.append(rec)
                continue
            rec["attempt_id"] = attempt["attempt_id"]
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
            try:
                _state.finish(lease, attempt, rec["status"])
            except OSError as exc:
                rec.update(status="error", detail=f"Job ran but its outcome could not be recorded; automatic retry is held: {exc}")
            fired.append(rec)
        return fired
    finally:
        if not dry_run:
            lease._gate.release()
        if locked_here:
            _lock_release(lease)


def _adopt_new_realms(rescan, owned: dict, others: list) -> None:
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
        try:
            lease = _lock_acquire(p)
        except OSError:
            swallowed(log, "run_daemon: cannot acquire new realm")
            continue
        if lease is not None:
            owned[p] = lease
            others.append(p)
            have.add(p.resolve())
            print(f"  also firing ▶ {p} (new since start)", flush=True)


def run_daemon(realm_root, engine: str = "auto", interval: int = 60,
               grace_min: Optional[int] = None, also: Optional[list] = None,
               rescan=None, app_owner: int = 0) -> int:
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
    # Hold each lease for the daemon's lifetime. Every successful acquisition is registered
    # for cleanup immediately, including failures during startup and newly discovered realms.
    try:
        primary = _lock_acquire(realm_root)
    except OSError as exc:
        print(f"ARMADA scheduler: cannot claim {realm_root}: {exc}", flush=True)
        return 1
    if primary is None:
        print(f"ARMADA scheduler: {realm_root} is already being scheduled. Not starting a second one.", flush=True)
        return 1
    owned = {realm_root: primary}
    restart = False
    try:
        for p in others:
            if p.resolve() in {r.resolve() for r in owned}:
                continue
            try:
                lease = _lock_acquire(p)
            except OSError:
                swallowed(log, "run_daemon: cannot acquire additional realm")
                continue
            if lease is not None:
                owned[p] = lease
        others = [p for p in owned if p != realm_root]
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
        _note_running(True)
        while True:
            if app_owner and (not _util.pid_alive(app_owner) or
                              ( _util.data_dir() / f"scheduler-stop-{app_owner}").exists()):
                print("  ARMADA window exited — stopping scheduled jobs", flush=True)
                break
            if _update_wanted():
                restart = not app_owner  # the replacement desktop starts its own scheduler
                break
            from . import updater
            if updater.apply_requested():
                time.sleep(1)
                continue
            from . import clock
            now = clock.now()  # Display-only; each tick validates its own realm clock.
            if rescan is not None:
                _adopt_new_realms(rescan, owned, others)
            for p in [realm_root, *others]:
                # One realm's problem is its own. A folder that has been moved or deleted since
                # startup must not take the other realms' jobs down with it.
                try:
                    fired = tick(p, engine=engine, grace_min=grace_min, _lease=owned[p])
                except Exception as e:  # noqa
                    swallowed(log, 'run_daemon: failed; reported to the caller')
                    print(f"  [{now.strftime('%H:%M')}] {p.name}: tick failed — {e}", flush=True)
                    continue
                where = "" if p == realm_root else f"{p.name}: "
                for r in fired:
                    print(f"  [{now.strftime('%H:%M')}] {where}fired {r['agent']}/{r['job']} "
                          f"({r['kind']}) → {r['status']}", flush=True)
                    if r.get("detail") or r.get("error"):
                        print(f"    {r.get('detail') or r.get('error')}", flush=True)
            if _update_wanted():
                print("  an ARMADA update is in place — restarting on the new version", flush=True)
                restart = not app_owner
                break
            for _ in range(max(5, interval)):
                from . import updater
                if updater.apply_requested():
                    break
                if app_owner and (not _util.pid_alive(app_owner) or
                                  (_util.data_dir() / f"scheduler-stop-{app_owner}").exists()):
                    break
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nARMADA scheduler stopped.")
    finally:
        # Released before the restart too: on Windows the restarted scheduler is a new process, and
        # it must find the realms free rather than held by a pid that's about to exit.
        for lease in owned.values():
            _lock_release(lease)
        _note_running(False)
        from . import updater as _upd
    return _upd.RESTART_RC if restart else 0


def _note_running(on: bool) -> None:
    try:
        from . import updater
        updater.note_scheduler(on)
    except Exception:  # noqa — bookkeeping for the updater must never stop the scheduler
        swallowed(log, "_note_running: failed; ignored")


def _update_wanted() -> bool:
    """Between passes: should this process restart onto new code (5.4)? Only ever for an installed
    copy; a development checkout answers no without looking further."""
    try:
        from . import updater, telegram
        if not updater.installed():
            return False
        return updater.scheduler_pass(telegram_busy=telegram.busy())
    except Exception:  # noqa
        swallowed(log, "_update_wanted: failed; carrying on")
        return False
