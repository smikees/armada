"""Automatic updates for an installed ARMADA (launch plan 5.4, ADR-011).

The installed app (ADR-009) is a private Python plus this package in `<install>\\armada\\`. An update
replaces that one folder. Nothing else changes: the Python runtime and its packages only change with
a new installer, and the updater refuses a release that needs one (see `runtime_tag`).

**Where releases come from.** GitHub Releases on the public repo. Every release carries three assets:

    armada-update.json       the manifest: version, zip name, its size and SHA-256, the runtime tag
    armada-update.json.sig   an Ed25519 signature over the manifest's exact bytes (base64)
    armada-<version>.zip     the `armada/` folder

The manifest and signature are fetched from `…/releases/latest/download/<name>` (GitHub redirects
that to the newest release); the zip from that release's own tag, a URL the updater builds itself
rather than reads from anywhere.

**Why this is safe to do automatically (THREAT_MODEL T11).** Whoever can change what ARMADA runs can
act as the owner, with their files and accounts. So nothing downloaded is trusted until it checks
out against `PUBLIC_KEY`, compiled into the app: the manifest's signature must verify, the zip must
match the size and hash the signed manifest names, and the signed version must be newer than this
one (an old, validly signed release can't be replayed to roll someone back to a known bug). A
GitHub account compromise alone therefore can't push code to installed copies; that takes the
signing key too, which lives offline in MATCAP-private and never in the repository.

**When it's applied.** Downloading and checking happen in the background (a system job in the
scheduler, or Settings → Check for updates). The verified folder waits beside the live one as
`armada.staged\\`. It replaces the live folder only when exactly one ARMADA process would be
running the old code, so no process ever runs half old, half new:

- at start-up (`boot()`), before anything else is imported — the window when the scheduler isn't
  running, the scheduler when the window isn't open;
- by the scheduler between passes, when the window isn't open and nothing is mid-reply;
- when the owner clicks *Restart to update* (the scheduler, if running, is asked to do it at its
  next quiet moment and to restart the window after; otherwise the window does it itself).

The old folder is kept as `armada.previous\\` until the next update, so a bad release can be rolled
back by hand. The data folder and realms are never touched; the realm migration (2.8) runs on the
first start of the new code, as it does for any version.

**A development checkout never self-updates.** `installed()` is true only when the installer's marker
(`installed.json`) sits beside the package and there is no `.git` — so this repo keeps its git
Update & Restart and the updater does nothing at all in it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from . import __version__, ed25519, util
from .util import swallowed

log = logging.getLogger("armada.updater")

# The release signing key's public half. Its private half is MATCAP-private/update-signing.key.
# Changing this is a release that has to go out as a new installer (the old key can't vouch for it).
PUBLIC_KEY = bytes.fromhex("d48b6c9dd25bc7406a4b985a778b0ee8bf25a7dba0a98892582547e1425c72a0")

REPO = "smikees/armada"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
MANIFEST = "armada-update.json"
SIGNATURE = MANIFEST + ".sig"
AUTO_KEY = "auto_update"                        # appconfig; default on (ADR-005)
CHECK_EVERY = 12 * 3600                          # seconds between background checks
RESTART_RC = 75                                  # run_daemon's "restart me" return code

PKG = Path(__file__).resolve().parent            # <install>\armada
ROOT = PKG.parent                                # <install>
MARKER = ROOT / "installed.json"                 # written by the installer (5.2)
STAGED = ROOT / "armada.staged"
PREVIOUS = ROOT / "armada.previous"
_STAGED_INFO = ".staged.json"
_CARRY = ("support_key.txt",)                   # local files the release zip doesn't ship

_MAX_MANIFEST, _MAX_SIG, _MAX_ZIP = 64 * 1024, 1024, 60 * 1024 * 1024
_VER_RE = re.compile(r"^\d+(\.\d+){1,3}$")


# ---- facts about this copy ------------------------------------------------------------------------

def installed() -> bool:
    return MARKER.is_file() and not (ROOT / ".git").exists()


def runtime_tag(requirements_text: str, python: str | None = None) -> str:
    """What the runtime this code needs is: the Python minor version plus the pinned requirements.
    An update may only replace the package folder when the new code needs the same runtime as the
    installed one; otherwise it needs a new installer. Comments and blank lines don't count."""
    py = python or f"{sys.version_info[0]}.{sys.version_info[1]}"
    lines = sorted(l.split("#", 1)[0].strip().lower() for l in requirements_text.splitlines())
    body = "\n".join(l for l in lines if l)
    return f"py{py}-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def installed_runtime() -> str:
    try:
        return str(json.loads(MARKER.read_text(encoding="utf-8-sig")).get("runtime") or "")
    except Exception:  # noqa
        log.debug("installed_runtime: unreadable marker", exc_info=True)
        return ""


def auto_enabled() -> bool:
    from . import appconfig
    return appconfig.get(AUTO_KEY, True) is not False


def set_auto(on: bool) -> dict:
    from . import appconfig
    appconfig.save({AUTO_KEY: bool(on)})
    return {"ok": True, "auto": bool(on)}


def vtuple(v: str) -> tuple:
    return tuple(int(x) for x in str(v).split("."))


def newer(a: str, b: str) -> bool:
    """Is version a newer than version b?"""
    try:
        return vtuple(a) > vtuple(b)
    except ValueError:
        return False


# ---- state (on this machine, not in a realm) ------------------------------------------------------

def _state_path() -> Path:
    return util.data_dir() / "update.json"


def state() -> dict:
    try:
        d = json.loads(_state_path().read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except Exception:  # silent-ok: no state yet is the normal first case
        return {}


def _save(**kw) -> dict:
    st = state()
    st.update(kw)
    try:
        util.write_json_atomic(_state_path(), st)
    except Exception:  # noqa
        swallowed(log, "_save: could not write update.json; ignored")
    return st


def _request_path() -> Path:
    return util.data_dir() / "update-apply.request"


def _scheduler_pid_path() -> Path:
    return util.data_dir() / "scheduler.pid"


def note_scheduler(running: bool) -> None:
    """The scheduler says it's up (or going down), so start-up can tell whether it's running
    without reading every realm's lock."""
    p = _scheduler_pid_path()
    try:
        if running:
            util.write_text_atomic(p, str(os.getpid()))
        elif p.exists() and p.read_text().strip() == str(os.getpid()):
            p.unlink()
    except Exception:  # noqa
        log.debug("note_scheduler: failed; ignored", exc_info=True)


def scheduler_running() -> bool:
    try:
        pid = _scheduler_pid_path().read_text().strip()
    except OSError:
        return False
    return pid != str(os.getpid()) and util.pid_alive(pid)


def window_open(port: int = 8756) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


# ---- fetching and checking ------------------------------------------------------------------------

def _fetch(url: str, limit: int) -> bytes:
    """GET `url` over HTTPS, following GitHub's redirects, refusing anything larger than `limit`."""
    if not url.startswith("https://"):
        raise ValueError("updates are only fetched over HTTPS")
    req = urllib.request.Request(url, headers={"User-Agent": f"ARMADA/{__version__} (updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if not r.geturl().startswith("https://"):
            raise ValueError("redirected off HTTPS")
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("download larger than expected")
    return data


def _latest_url(name: str) -> str:
    return f"https://github.com/{REPO}/releases/latest/download/{name}"


def _asset_url(version: str, name: str) -> str:
    return f"https://github.com/{REPO}/releases/download/v{version}/{name}"


class UpdateError(Exception):
    """A release that failed a check. The message is what the owner is shown."""


def verified_manifest(raw: bytes, sig_b64: bytes) -> dict:
    """The manifest, if and only if it's signed by PUBLIC_KEY and well formed."""
    try:
        sig = base64.b64decode(sig_b64.strip(), validate=True)
    except Exception:  # noqa
        raise UpdateError("the release's signature is malformed") from None
    if not ed25519.verify(PUBLIC_KEY, raw, sig):
        raise UpdateError("the release isn't signed by ARMADA's release key — not installing it")
    try:
        m = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa
        raise UpdateError("the release's manifest is unreadable") from None
    ok = (isinstance(m, dict) and m.get("app") == "armada" and m.get("format") == 1
          and _VER_RE.match(str(m.get("version") or ""))
          and m.get("zip") == f"armada-{m.get('version')}.zip"
          and re.fullmatch(r"[0-9a-f]{64}", str(m.get("sha256") or ""))
          and isinstance(m.get("size"), int) and 0 < m["size"] <= _MAX_ZIP
          and isinstance(m.get("runtime"), str))
    if not ok:
        raise UpdateError("the release's manifest is incomplete")
    return m


def _safe_members(zf: zipfile.ZipFile) -> list:
    """Every entry must sit inside `armada/`, with no absolute paths or `..` — a signed zip is ours,
    but the extraction shouldn't depend on that."""
    out = []
    for info in zf.infolist():
        n = info.filename.replace("\\", "/")
        parts = n.split("/")
        if (not n.startswith("armada/") or n.startswith("/") or ":" in parts[0]
                or any(p in ("..",) for p in parts)):
            raise UpdateError("the release zip has an unexpected layout")
        if "__pycache__" in parts:
            continue
        out.append(info)
    return out


def _version_in(folder: Path) -> str:
    try:
        m = re.search(r'__version__\s*=\s*"([^"]+)"', (folder / "__init__.py").read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except OSError:
        return ""


def staged_version() -> str:
    """The version waiting in armada.staged, if a complete, checked one is there."""
    try:
        info = json.loads((STAGED / _STAGED_INFO).read_text(encoding="utf-8"))
    except Exception:  # silent-ok: no staged update is the usual case
        return ""
    v = str(info.get("version") or "")
    return v if v and _version_in(STAGED) == v and newer(v, __version__) else ""


def _stage(m: dict, blob: bytes) -> None:
    if len(blob) != m["size"] or hashlib.sha256(blob).hexdigest() != m["sha256"]:
        raise UpdateError("the download doesn't match the signed release (size or checksum)")
    tmp = ROOT / "armada.staging-tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(STAGED, ignore_errors=True)
    tmp.mkdir(parents=True)
    zpath = tmp / "release.zip"
    zpath.write_bytes(blob)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(tmp, members=_safe_members(zf))
    zpath.unlink()
    if _version_in(tmp / "armada") != m["version"]:
        shutil.rmtree(tmp, ignore_errors=True)
        raise UpdateError("the release's code doesn't carry the version it was signed as")
    (tmp / "armada" / _STAGED_INFO).write_text(json.dumps({"version": m["version"], "sha256": m["sha256"]}),
                                               encoding="utf-8")
    util._replace_retrying(tmp / "armada", STAGED)
    shutil.rmtree(tmp, ignore_errors=True)


def check(download: bool = True, fetch=None) -> dict:
    """Ask GitHub for the newest release; if it's newer and fits this runtime, download, verify and
    stage it. Returns what happened, for the Settings page and the Jobs list. Never raises."""
    fetch = fetch or _fetch
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    if not installed():
        return {"ok": True, "installed": False, "newer": False,
                "detail": "development copy — updates come from git"}
    try:
        raw = fetch(_latest_url(MANIFEST), _MAX_MANIFEST)
        sig = fetch(_latest_url(SIGNATURE), _MAX_SIG)
        m = verified_manifest(raw, sig)
        latest = m["version"]
        if not newer(latest, __version__):
            _save(checked=now, latest=latest, status="current", detail="")
            return {"ok": True, "installed": True, "newer": False, "latest": latest,
                    "detail": f"up to date (v{__version__})"}
        if m["runtime"] != installed_runtime():
            _save(checked=now, latest=latest, status="needs-installer", detail="")
            return {"ok": True, "installed": True, "newer": True, "latest": latest,
                    "needs_installer": True, "url": RELEASES_PAGE,
                    "detail": f"v{latest} needs the new installer"}
        if staged_version() == latest:
            _save(checked=now, latest=latest, status="staged", detail="")
            return {"ok": True, "installed": True, "newer": True, "latest": latest, "staged": latest,
                    "detail": f"v{latest} is ready to install"}
        if not download:
            _save(checked=now, latest=latest, status="available", detail="")
            return {"ok": True, "installed": True, "newer": True, "latest": latest,
                    "detail": f"v{latest} is available"}
        blob = fetch(_asset_url(latest, m["zip"]), _MAX_ZIP)
        _stage(m, blob)
        _save(checked=now, latest=latest, status="staged", detail="")
        log.info("update: v%s downloaded, verified and staged", latest)
        return {"ok": True, "installed": True, "newer": True, "latest": latest, "staged": latest,
                "detail": f"v{latest} downloaded and checked — installs on the next restart"}
    except UpdateError as e:
        log.warning("update: rejected — %s", e)
        _save(checked=now, status="rejected", detail=str(e))
        return {"ok": False, "installed": True, "newer": False, "error": str(e), "detail": str(e)}
    except Exception as e:  # noqa — offline, GitHub down, no release yet: try again later
        swallowed(log, "check: could not reach the release channel", level=logging.WARNING)
        msg = "no release published yet" if "404" in str(e) else f"couldn't reach GitHub ({type(e).__name__})"
        _save(checked=now, status="error", detail=msg)
        return {"ok": False, "installed": True, "newer": False, "error": msg, "detail": msg}


def check_due() -> bool:
    try:
        last = time.mktime(time.strptime(state().get("checked", ""), "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OverflowError):
        return True
    return time.time() - last >= CHECK_EVERY


# ---- applying -------------------------------------------------------------------------------------

def apply_staged() -> str:
    """Swap armada.staged in as the live package. Returns the version now installed, or "" when there
    was nothing to apply or the swap couldn't happen (tried again later; the live copy is untouched).

    Two renames. If the second fails, the first is undone, so the live folder is never missing."""
    v = staged_version()
    if not v or not installed():
        return ""
    old = __version__
    try:
        if PREVIOUS.exists():
            shutil.rmtree(PREVIOUS)
        for name in _CARRY:
            if (PKG / name).exists() and not (STAGED / name).exists():
                shutil.copy2(PKG / name, STAGED / name)
        util._replace_retrying(PKG, PREVIOUS)
        try:
            util._replace_retrying(STAGED, PKG)
        except Exception:
            util._replace_retrying(PREVIOUS, PKG)
            raise
    except Exception:  # noqa — a locked file (antivirus, an open editor): leave it for next time
        swallowed(log, "apply_staged: couldn't swap the package folder; will retry", level=logging.WARNING)
        return ""
    try:
        (PKG / _STAGED_INFO).unlink()
    except OSError:
        pass
    _save(status="applied", applied=v, previous=old,
          applied_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    try:
        _request_path().unlink()
    except OSError:
        pass
    log.info("update: v%s installed (was v%s); v%s kept in armada.previous", v, old, old)
    return v


def code_on_disk() -> str:
    """The version of the package folder as it is on disk now — which differs from __version__ once
    another process has applied an update under this one."""
    return _version_in(PKG) or __version__


def request_apply() -> dict:
    """*Restart to update*, from the window. Returns {"applied": v} when this process swapped the
    folder itself (then the caller restarts), or {"waiting": True} when the scheduler will."""
    v = staged_version()
    if not v:
        return {"ok": False, "error": "no update is waiting"}
    if scheduler_running():
        util.write_text_atomic(_request_path(), v)
        return {"ok": True, "waiting": True, "version": v}
    got = apply_staged()
    return {"ok": bool(got), "applied": got, "version": v,
            **({} if got else {"error": "Couldn't replace the program files just now. Try again in a minute."})}


def apply_requested() -> bool:
    return _request_path().exists()


def boot(mode: str) -> bool:
    """At process start, before the app is imported: apply a staged update if this is the only
    ARMADA process that could be running the old code. True when it applied (the caller re-execs).

    The window applies when the scheduler isn't running; the scheduler applies when the window isn't
    open. Either way the other one, started afterwards, loads the new code."""
    try:
        if not installed() or not staged_version():
            return False
        if mode == "app" and scheduler_running():
            return False
        if mode == "schedule" and window_open():
            return False
        return bool(apply_staged())
    except Exception:  # noqa — an updater problem must never stop ARMADA starting
        swallowed(log, "boot: failed; starting the current version")
        return False


def scheduler_pass(telegram_busy: bool = False) -> bool:
    """Called by the scheduler after each pass. True means "restart this process now": either it
    just applied an update, or someone else did and this process is running code that's gone."""
    if not installed():
        return False
    try:
        if newer(code_on_disk(), __version__):
            return True
        if telegram_busy or not staged_version():
            return False
        requested = apply_requested()
        if not requested and (not auto_enabled() or window_open()):
            return False
        if apply_staged():
            if requested:
                _restart_window()
            return True
    except Exception:  # noqa
        swallowed(log, "scheduler_pass: failed; ignored")
    return False


def _restart_window(port: int = 8756) -> None:
    """After applying an update the owner asked for, restart the window's server onto the new code."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/restart", data=b"", method="POST")
        urllib.request.urlopen(req, timeout=5).close()
    except Exception:  # noqa — the window may have been closed meanwhile; it'll start on the new code
        log.debug("_restart_window: failed; ignored", exc_info=True)


def reexec() -> None:
    """Start this command again on the (new) code on disk. On Windows os.execv starts a new process
    and ends this one, which is why the scheduler releases its locks before calling this."""
    argv = [sys.executable, "-m", "armada", *sys.argv[1:]]
    log.info("update: restarting %s", argv)
    os.chdir(ROOT)
    os.execv(sys.executable, argv)


def status() -> dict:
    """For the window: what the updater knows, without touching the network."""
    st = state()
    return {"installed": installed(), "version": __version__, "auto": auto_enabled(),
            "staged": staged_version(), "status": st.get("status", ""), "latest": st.get("latest", ""),
            "checked": st.get("checked", ""), "detail": st.get("detail", ""),
            "applied": st.get("applied", ""), "requested": apply_requested(),
            "releases": RELEASES_PAGE}
