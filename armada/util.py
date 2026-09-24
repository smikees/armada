"""Small shared utilities: filesystem-path safety and atomic writes.

Kept dependency-free (stdlib only) so every module can import it cheaply.
"""
from __future__ import annotations
import contextlib, json, logging, os, re, sys, tempfile, threading, time
from pathlib import Path
log = logging.getLogger(__name__)

# realm ids/slugs are lowercase alnum with -/_ (see setup.scaffold, _new_thread slugging).
_SEG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class UnsafeSegment(ValueError):
    """A request-supplied path segment that would escape or is malformed."""


def safe_seg(value, what: str = "segment") -> str:
    """Return `value` as a str if it's a single safe path segment, else raise.

    Blocks path traversal and separators: no '', '.', '..', '/', '\\', or NUL, and the
    whole thing must match [A-Za-z0-9][A-Za-z0-9_-]*. Use this on ANY agent id, thread
    slug, job id, or filename that arrives from an HTTP request before it touches disk.
    """
    s = "" if value is None else str(value)
    if not _SEG_RE.match(s):
        raise UnsafeSegment(f"unsafe {what}: {s!r}")
    return s


def is_safe_seg(value) -> bool:
    try:
        safe_seg(value)
        return True
    except UnsafeSegment:
        return False


_BUSY = (5, 32, 33)          # Windows: access denied / sharing violation / lock violation


def _replace_retrying(src, dst, attempts: int = 12) -> None:
    """os.replace, patient with Windows' momentary locks.

    On Windows a rename onto a file fails while any other process has that file open without
    FILE_SHARE_DELETE — which is every ordinary Python open(). So the server reading
    telegram_state.json for the Settings page, at the instant the scheduler's listener rewrites
    it, made the write fail ("[WinError 32] … being used by another process", seen in
    scheduler.log 2026-09-24). Antivirus scanners and the search indexer cause the same thing.
    Those holds last milliseconds; waiting briefly and trying again is the standard remedy. About
    1.5 s in all before giving up and raising as before. Other errors raise at once.
    """
    delay = 0.02
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:
            if getattr(e, "winerror", None) not in _BUSY or i == attempts - 1:   # only Windows sets winerror
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)


def write_text_atomic(path, text: str, encoding: str = "utf-8") -> None:
    """Write text so a crash/concurrent reader never sees a half-written file.

    Writes to a temp file in the same directory, flushes+fsyncs, then os.replace()s it
    over the target (atomic on the same filesystem).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        _replace_retrying(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def write_json_atomic(path, obj, indent: int = 2) -> None:
    """Serialize `obj` to JSON and write it atomically (see write_text_atomic)."""
    write_text_atomic(path, json.dumps(obj, ensure_ascii=False, indent=indent))


def sweep_temp_files(root, older_than_sec: float = 3600.0) -> int:
    """Delete stale `.tmp-*` files left by an atomic write that never completed. Returns the count.

    write_text_atomic cleans up after itself, but only if its `finally` gets to run. A process
    killed between creating the temp and os.replace()-ing it leaves the file behind, and nothing
    ever collects it: one live realm had 67, five days' worth, mostly from the Telegram listener
    writing its cursor in the scheduler process whenever that process was force-killed.

    A kill can't be cleaned up after, so the sweep happens at startup instead. The age guard is the
    whole safety: a temp younger than an hour may belong to a write happening right now in another
    process, and deleting it would break a save that was about to succeed.
    """
    n = 0
    cutoff = time.time() - max(0.0, older_than_sec)
    try:
        for p in Path(root).rglob(".tmp-*"):
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
                    n += 1
            except OSError:
                continue          # in use, or gone since we listed it — either way, not ours
    except OSError:
        pass
    return n


def pid_alive(pid) -> bool:
    """Best-effort: is a process with this pid currently running on this machine?

    Used to tell a live lock holder from a stale one left behind by a crash (kill -9, a killed
    Task Scheduler run, a closed terminal that didn't get to clean up). Cross-platform: POSIX
    checks via a signal-0 `os.kill` (raises rather than signalling anything); Windows has no
    such call, so it asks the kernel directly via OpenProcess. Either way, "can't tell" reads as
    not-alive — the lock is best-effort, and a false stale reading (taken over one tick early) is
    far cheaper than a false live reading (a dead lock nobody can ever clear).
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True     # exists, just owned by someone else — still alive
    except OSError:
        return False
    return True


@contextlib.contextmanager
def file_lock(target, timeout: float = 5.0, poll: float = 0.05):
    """Best-effort cross-process advisory lock, so the web server and the always-on scheduler
    daemon don't lose each other's updates on a read-modify-write (e.g. appending to the same
    thread, or two edits of realm.json). Creates a sibling `<name>.lock` with O_CREAT|O_EXCL and
    spins up to `timeout`; if it can't acquire (stale/contended) it proceeds anyway rather than
    ever deadlocking the app — atomic writes still prevent corruption in that rare case.
    """
    lock = Path(str(target) + ".lock")
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    fd = None
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.time() >= deadline:
                break  # give up waiting; proceed without the lock
            time.sleep(poll)
        except OSError:
            break  # can't create a lock here (permissions etc.) — proceed
    try:
        yield
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
            with contextlib.suppress(OSError):
                lock.unlink()


# ---- deliberately-swallowed exceptions (Phase 2, 2.5) ---------------------------------------------
#
# ARMADA catches broadly in a lot of places on purpose: a badge must not break a page, a telemetry
# write must not fail a job, one bad agent.json must not blank a roster. The fallback is right; what
# was wrong is that the reason vanished. `swallowed()` is the one call every such `except` block makes
# before it falls back, so the reason lands in ~/.armada/logs with a traceback.
#
# Two judgements live here rather than at 250 call sites:
# - A missing file is almost always the "absent" case the fallback exists for (no inbox marker yet,
#   no feed yet, no credentials store on this machine) — logged at DEBUG, not as an error.
# - The same failure on a render path repeats on every page load and every poll. The first one is
#   logged in full; repeats of the same (logger, message, exception type) inside SWALLOW_WINDOW
#   seconds are counted and summarised on the next one that gets through, so a single corrupt file
#   can't flush the rotating log of everything else.

def data_dir() -> Path:
    """ARMADA's folder on this machine: `~/.armada` — config, the realm registry, logs, caches, the
    Telegram credential store. Never inside a realm; see ARCHITECTURE §4.1.

    A dot-folder in the user's home, like Claude Code's own `~/.claude`, rather than %APPDATA%: one
    path on every platform, and the one the people who use ARMADA already look in.

    Until v0.99.56 the folder was `~/.matcap` (the app's working name). The first call on a machine
    that still has only the old folder moves it — a rename, or a copy if the rename is refused (a
    file held open) — so nothing a user set up is lost. Two processes racing here is harmless: the
    loser finds the new folder already there.
    """
    new = Path.home() / ".armada"
    if not new.exists():
        old = Path.home() / ".matcap"
        if old.is_dir():
            try:
                old.rename(new)
            except OSError:
                try:
                    import shutil
                    shutil.copytree(old, new, dirs_exist_ok=True)
                except OSError:
                    swallowed(logging.getLogger("armada.util"), "data_dir: could not move ~/.matcap")
    return new


def init_logging(filename: str = "armada.log") -> None:
    """Send the `armada` loggers to stderr (when there is one) and to ~/.armada/logs/<filename>.

    Once per process. The server writes armada.log; the scheduler daemon — a separate process, and
    under SCHEDULER.vbs a windowless pythonw with no stderr at all — writes scheduler.log, because
    two processes rotating one file on Windows fail on the rename. Outside the realm on purpose: a
    log is about this machine, not something to commit or carry to another one.
    """
    root = logging.getLogger("armada")
    if getattr(root, "_armada_configured", False):
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.stderr is not None:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    try:
        from logging.handlers import RotatingFileHandler
        logdir = data_dir() / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(logdir / filename, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:  # noqa — file logging is best-effort
        swallowed(root, "init_logging: could not open the log file; logging to stderr only")
    root._armada_configured = True


SWALLOW_WINDOW = 300.0
_swallow_last: dict = {}
_swallow_hidden: dict = {}
_swallow_mu = threading.Lock()


def swallowed(logger, what: str, *, level: int = logging.ERROR,
              quiet: tuple = (FileNotFoundError,)) -> None:
    """Log the exception currently being handled, from an `except` block that falls back on purpose.

    Call it first thing in the block, then do whatever the block always did. Never raises.
    `what` names the function and the fallback ("_nav: pending-proposals count failed; showing 0").
    """
    try:
        et, ev, _tb = sys.exc_info()
        if ev is None:
            return
        if quiet and isinstance(ev, quiet):
            logger.debug(what, exc_info=True)
            return
        key = (logger.name, what, et)
        now = time.monotonic()
        with _swallow_mu:
            last = _swallow_last.get(key)
            if last is not None and now - last < SWALLOW_WINDOW:
                _swallow_hidden[key] = _swallow_hidden.get(key, 0) + 1
                hidden = -1
            else:
                _swallow_last[key] = now
                hidden = _swallow_hidden.pop(key, 0)
        if hidden < 0:
            logger.debug(what, exc_info=True)
            return
        if hidden:
            what = f"{what} (+{hidden} more like this since the last one logged)"
        logger.log(level, what, exc_info=True)
    except Exception:  # silent-ok: the error reporter must never become the error
        swallowed(log, 'swallowed: failed; ignored')
