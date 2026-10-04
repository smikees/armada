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
`armada.staged\\`. Applying it requires a restart through the stable bootstrap outside this
package. The bootstrap owns a durable journal and an installation lock, recovers any interrupted
swap before importing ARMADA, and waits for existing process leases to close. The scheduler asks
the window to restart only at a quiet point; new work is refused once a restart is requested.
No running HTTP worker replaces the package it has imported.

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
import tempfile

import armada_bootstrap as bootstrap
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
_CARRY = ()                                    # no client credentials are carried into updates

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
    body = "\n".join(l for l in lines if l) + f"\nbootstrap:{bootstrap.PROTOCOL}"
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
    return ROOT / bootstrap.REQUEST


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
                or any(p in ("..",) or ":" in p or p.rstrip(' .') != p for p in parts)
                or any(p.lower() == 'support_key.txt' for p in parts)):
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
    if (ROOT / bootstrap.ERROR).exists(): return ""
    try:
        info = json.loads((STAGED / _STAGED_INFO).read_text(encoding="utf-8"))
    except Exception:  # silent-ok: no staged update is the usual case
        return ""
    v = str(info.get("version") or "")
    return v if v and _version_in(STAGED) == v and newer(v, __version__) else ""


def _stage(m: dict, blob: bytes) -> None:
    if len(blob) != m["size"] or hashlib.sha256(blob).hexdigest() != m["sha256"]:
        raise UpdateError("the download doesn't match the signed release (size or checksum)")
    with bootstrap.install_lock(ROOT):
        # A slower download must not replace a newer verified stage from another checker.
        existing = staged_version()
        if existing and not newer(m["version"], existing):
            return
        if not newer(m["version"], code_on_disk()):
            return
        tmp = Path(tempfile.mkdtemp(prefix=".armada-staging-", dir=ROOT))
        old_stage = ROOT / (tmp.name + "-previous")
        try:
            zpath = tmp / "release.zip"
            zpath.write_bytes(blob)
            with zipfile.ZipFile(zpath) as zf:
                zf.extractall(tmp, members=_safe_members(zf))
            zpath.unlink()
            package = tmp / "armada"
            if _version_in(package) != m["version"]:
                raise UpdateError("the release's code doesn't carry the version it was signed as")
            bootstrap.atomic_json(package / _STAGED_INFO,
                {"version":m["version"], "sha256":m["sha256"], "files":bootstrap.inventory(package)})
            if STAGED.exists(): bootstrap.replace(STAGED, old_stage)
            try:
                bootstrap.replace(package, STAGED)
                (ROOT / bootstrap.ERROR).unlink(missing_ok=True)
            except BaseException:
                if old_stage.exists(): bootstrap.replace(old_stage, STAGED)
                raise
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            if old_stage.exists(): shutil.rmtree(old_stage)


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
        if getattr(e, "code", None) == 404:
            # No release has been published: nothing newer than this copy exists, which is an
            # answer, not a fault (it logged a full traceback every 12 hours until v0.99.66).
            log.info("update: no release published yet")
            _save(checked=now, latest="", status="current", detail="no release published yet")
            return {"ok": True, "installed": True, "newer": False, "latest": "",
                    "detail": "no release published yet"}
        swallowed(log, "check: could not reach the release channel", level=logging.WARNING)
        msg = f"couldn't reach GitHub ({type(e).__name__})"
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
    """Apply under the stable bootstrap's lock and journal; ordinary callers restart first."""
    v = staged_version()
    if not v or not installed(): return ""
    try:
        applied = bootstrap.apply(ROOT)
    except (OSError, ValueError):
        swallowed(log, "apply_staged: package replacement deferred", level=logging.WARNING)
        return ""
    if applied:
        _save(status="applied", applied=applied, previous=__version__,
              applied_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        _request_path().unlink(missing_ok=True)
    return applied


def code_on_disk() -> str:
    """The version of the package folder as it is on disk now — which differs from __version__ once
    another process has applied an update under this one."""
    return _version_in(PKG) or __version__


def request_apply() -> dict:
    """Quiesce admission, then restart through the bootstrap; never swap under the HTTP worker."""
    from . import execution
    with execution.RUNS_LOCK:
        v = staged_version()
        if not v: return {"ok": False, "error": "no update is waiting"}
        if execution.ACTIVE_RUNS:
            return {"ok": False, "error": "Finish or stop current tasks before restarting to update."}
        util.write_text_atomic(_request_path(), v)
        return {"ok": True, "waiting": scheduler_running(), "restart": True, "version": v}


def apply_requested() -> bool:
    return _request_path().exists()


def boot(mode: str) -> bool:
    """Compatibility hook for legacy callers; normal installed launches use armada_bootstrap.py."""
    if not installed() or not staged_version(): return False
    if mode == "app" and scheduler_running(): return False
    if mode == "schedule" and window_open(): return False
    return bool(apply_staged())


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
        from . import execution
        with execution.RUNS_LOCK:
            if execution.ACTIVE_RUNS: return False
            if requested and window_open() and not _restart_window(): return False
            # The new bootstrap waits for old process leases to close before replacing files.
            return True
    except Exception:  # noqa
        swallowed(log, "scheduler_pass: failed; ignored")
    return False


def _restart_window(port: int = 8756) -> bool:
    """After applying an update the owner asked for, restart the window's server onto the new code."""
    try:
        from . import local_auth
        req = urllib.request.Request(f"http://127.0.0.1:{port}/restart", data=b"", method="POST",
                                     headers=local_auth.headers(port))
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception:  # noqa — the window may have been closed meanwhile; it'll start on the new code
        log.debug("_restart_window: failed; ignored", exc_info=True)
        return False


def launch_arguments(*args):
    entry = ROOT / "armada_bootstrap.py"
    return [str(entry), *args] if installed() else ["-m", "armada", *args]


def reexec() -> None:
    """Start this command again on the (new) code on disk. On Windows os.execv starts a new process
    and ends this one, which is why the scheduler releases its locks before calling this."""
    if len(sys.argv) > 1 and sys.argv[1] == 'app' and os.name == 'nt':
        from .desktop_launch import spawn
        host = Path(sys.executable).with_name('ARMADA.exe')
        spawn([str(host if host.is_file() else sys.executable), *launch_arguments(*sys.argv[1:])], ROOT)
        raise SystemExit(0)
    argv = [sys.executable, *launch_arguments(*sys.argv[1:])]
    log.info("update: restarting %s", argv)
    os.chdir(ROOT)
    os.execv(sys.executable, argv)


def status() -> dict:
    """For the window: what the updater knows, without touching the network."""
    st = state()
    try:
        error = json.loads((ROOT / bootstrap.ERROR).read_text(encoding="utf-8"))['error']
        st = {**st, 'status': 'error', 'detail': 'Update was not applied: ' + str(error)}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {"installed": installed(), "version": __version__, "auto": auto_enabled(),
            "staged": staged_version(), "status": st.get("status", ""), "latest": st.get("latest", ""),
            "checked": st.get("checked", ""), "detail": st.get("detail", ""),
            "applied": st.get("applied", ""), "requested": apply_requested(),
            "releases": RELEASES_PAGE}
