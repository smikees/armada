#!/usr/bin/env python3
"""Build the Windows installer: ARMADA-Setup-<version>.exe (launch plan 5.2, ADR-009).

    python tools/build_installer.py            # stage + smoke-test + compile
    python tools/build_installer.py --stage-only

Runs on Windows (the build machine), with `uv` and Inno Setup 7 installed. What it does:

1. Unpacks the python.org **embeddable** Python 3.12.10 (pinned by SHA-256) into
   `build/installer/ARMADA/python/`, and edits its `._pth` so the install folder (where `armada\\`
   lives) and `Lib\\site-packages` are on the path. Nothing else is: the `._pth` file puts Python in
   isolated mode, so no PYTHONPATH, user site-packages or other Python on the machine can leak in.
2. Installs the pinned `requirements.txt` into that `site-packages` for Windows/3.12
   (`uv pip install --target …`): prebuilt wheels for every package with compiled or .NET parts,
   so nothing is compiled at build time.
3. Copies the committed `armada/` package (git ls-files — no local caches or keys), plus the
   Report-an-issue send key (`armada/support_key.txt`, gitignored, send-only), `LICENSE`,
   `THIRD_PARTY_NOTICES.md`, the icon, and every bundled package's own licence files under
   `licenses/`. Refuses to build if the bundled package versions differ from the notices' table.
4. Writes `installed.json`, the marker that makes the updater (5.4) treat this as an installed copy,
   with the runtime tag a release must match to be applied in place.
5. Smoke-tests the staged runtime (imports the app, pywebview and pythonnet with the bundled Python,
   and serves the welcome page from a throwaway home folder), then compiles `installer/armada.iss`
   with Inno Setup into `dist/ARMADA-Setup-<version>.exe`.

The installer is unsigned for the beta (ADR-009 §5): SmartScreen says "unrecognised app" once.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PY_VERSION = "3.12.10"
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
# SHA-256 of that file, taken 2026-09-24 after checking its MD5 against python.org's release page
# (fe8ef205f2e9c3ba44d0cf9954e1abd3). A different file is refused.
PY_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
PTH_NAME = "python312._pth"

CACHE = ROOT / "build" / "cache"
STAGE_ROOT = ROOT / "build" / "installer"
STAGE = STAGE_ROOT / "ARMADA"
ISS = ROOT / "installer" / "armada.iss"
REDIST = STAGE_ROOT / "redist"
# Microsoft's Evergreen Bootstrapper for the WebView2 Runtime (~2 MB). Microsoft's distribution guide
# says to package it with the app and run it when the runtime is missing; it fetches the right
# runtime itself. It changes as Microsoft updates it, so it's pinned by signature, not by hash.
WEBVIEW2_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WEBVIEW2_EXE = "MicrosoftEdgeWebview2Setup.exe"
DIST = ROOT / "dist"
ISCC_CANDIDATES = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 7" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 7" / "ISCC.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 7" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
]


def say(msg: str) -> None:
    print(f"  · {msg}", flush=True)


def _version() -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "armada" / "__init__.py").read_text(encoding="utf-8"))
    if not m:
        sys.exit("no __version__ in armada/__init__.py")
    return m.group(1)


def _git(*args) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def _embeddable() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    z = CACHE / Path(PY_URL).name
    if not z.exists():
        say(f"downloading {PY_URL}")
        with urllib.request.urlopen(PY_URL, timeout=120) as r, open(z, "wb") as f:
            shutil.copyfileobj(r, f)
    got = hashlib.sha256(z.read_bytes()).hexdigest()
    if got != PY_SHA256:
        z.unlink()
        sys.exit(f"{z.name}: SHA-256 {got} is not the pinned {PY_SHA256} — refusing it")
    return z


def pth_text() -> str:
    """The embeddable Python's path file. Paths are relative to the python\\ folder: `..` is the
    install folder, where `armada\\` sits, so `pythonw -m armada` works from any working folder."""
    return ("python312.zip\n"
            ".\n"
            "..\n"
            "Lib\\site-packages\n"
            "# Import site so site-packages' .pth files (pythonnet, pywin32-style hooks) are honoured.\n"
            "import site\n")


def _requirements() -> dict:
    out = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            n, v = line.split("==", 1)
            out[_norm(n)] = v.strip()
    return out


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _notices_versions() -> dict:
    """The package table in THIRD_PARTY_NOTICES.md, as {name: version}."""
    out = {}
    for line in (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*([A-Za-z0-9_.\-]+)\s*\|\s*([0-9][0-9A-Za-z.\-]*)\s*\|", line)
        if m and m.group(1).lower() != "python":
            out[_norm(m.group(1))] = m.group(2)
    return out


def _bundled(site: Path) -> dict:
    out = {}
    for d in site.glob("*.dist-info"):
        m = re.match(r"(.+?)-([0-9][^-]*)\.dist-info$", d.name)
        if m:
            out[_norm(m.group(1))] = (m.group(2), d)
    return out


def stage(ver: str) -> Path:
    if _git("status", "--porcelain", "--untracked-files=no", "--", "armada").strip():
        sys.exit("armada/ has uncommitted changes — commit first; an installer is built from a commit")
    if STAGE_ROOT.exists():
        shutil.rmtree(STAGE_ROOT)
    py = STAGE / "python"
    py.mkdir(parents=True)

    say(f"Python {PY_VERSION} (embeddable)")
    with zipfile.ZipFile(_embeddable()) as zf:
        zf.extractall(py)
    (py / PTH_NAME).write_text(pth_text(), encoding="ascii")

    say("packages from requirements.txt (Windows wheels only)")
    site = py / "Lib" / "site-packages"
    site.mkdir(parents=True)
    # Prebuilt wheels for everything with compiled or .NET parts; the one pure-Python package with no
    # wheel on PyPI (proxy-tools 0.1.0, pywebview's) is packaged from its source, which is safe
    # across platforms because there's nothing in it to compile.
    binary_only = [a for n in ("cffi", "pythonnet", "clr-loader", "pywebview") for a in ("--only-binary", n)]
    subprocess.run(["uv", "pip", "install", "--target", str(site), "--python-version", "3.12",
                    "--python-platform", "x86_64-pc-windows-msvc", *binary_only,
                    "--no-cache", "-r", str(ROOT / "requirements.txt")], check=True)
    for junk in site.glob("bin"):
        shutil.rmtree(junk, ignore_errors=True)

    bundled = _bundled(site)
    want, notices = _requirements(), _notices_versions()
    have = {k: v for k, (v, _) in bundled.items()}
    if have != want:
        sys.exit(f"bundled packages {have} differ from requirements.txt {want}")
    if notices != want:
        sys.exit(f"THIRD_PARTY_NOTICES.md lists {notices}, but the installer bundles {want} — update the table")
    lic = STAGE / "licenses"
    for name, (v, dist) in sorted(bundled.items()):
        files = [p for p in dist.rglob("*") if p.is_file() and re.search(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", p.name, re.I)]
        base = dist
        if not files:                    # a package that ships none: the text kept in the repo
            base = ROOT / "installer" / "licenses" / f"{name}-{v}"
            files = [p for p in base.glob("*") if p.is_file()]
        if not files:
            sys.exit(f"{name} {v} ships no licence file — put its text in installer/licenses/{name}-{v}/")
        for f in files:
            dest = lic / f"{name}-{v}" / f.relative_to(base)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    if (py / "LICENSE.txt").exists():                    # the embeddable zip carries Python's own
        shutil.copy2(py / "LICENSE.txt", lic / f"python-{PY_VERSION}-LICENSE.txt")

    say("ARMADA (committed files only)")
    files = [f for f in _git("ls-files", "--", "armada").splitlines() if f]
    for f in files:
        dest = STAGE / f
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dest)
    key = ROOT / "armada" / "support_key.txt"
    if key.exists():
        shutil.copy2(key, STAGE / "armada" / "support_key.txt")
    else:
        say("WARNING: armada/support_key.txt missing — Report an issue will save reports locally instead of sending")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, STAGE / name)
    shutil.copy2(ROOT / "armada" / "webui" / "static" / "armada.ico", STAGE / "armada.ico")

    from armada import updater
    runtime = updater.runtime_tag((ROOT / "requirements.txt").read_text(encoding="utf-8"), "3.12")
    (STAGE / updater.MARKER.name).write_text(json.dumps(
        {"runtime": runtime, "version": ver, "python": PY_VERSION, "channel": "github"}, indent=2),
        encoding="utf-8")
    say(f"staged {STAGE}  (runtime {runtime})")
    return STAGE


def _webview2_bootstrapper() -> Path:
    """Download Microsoft's WebView2 bootstrapper and refuse it unless Windows says it carries a
    valid Authenticode signature from Microsoft Corporation."""
    CACHE.mkdir(parents=True, exist_ok=True)
    exe = CACHE / WEBVIEW2_EXE
    if not exe.exists():
        say("downloading Microsoft's WebView2 bootstrapper")
        with urllib.request.urlopen(WEBVIEW2_URL, timeout=120) as r, open(exe, "wb") as f:
            shutil.copyfileobj(r, f)
    ps = (f"$s = Get-AuthenticodeSignature -LiteralPath '{exe}'; "
          "Write-Output ([string]$s.Status + '|' + $s.SignerCertificate.Subject)")
    got = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
    status, _, subject = got.partition("|")
    if status != "Valid" or "O=Microsoft Corporation" not in subject:
        exe.unlink()
        sys.exit(f"{WEBVIEW2_EXE}: signature {status!r} from {subject!r} — refusing it")
    REDIST.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, REDIST / WEBVIEW2_EXE)
    say("WebView2 bootstrapper: valid signature from Microsoft Corporation")
    return REDIST


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def smoke(stage_dir: Path, ver: str) -> None:
    """Run the staged app with the staged Python, from a throwaway home folder and working folder."""
    py = stage_dir / "python" / "python.exe"
    with tempfile.TemporaryDirectory(prefix="armada-smoke-", ignore_cleanup_errors=True) as home:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "ARMADA_", "VIRTUAL_ENV"))}
        env.update(USERPROFILE=home, HOME=home)
        say("smoke: imports")
        r = subprocess.run([str(py), "-c",
                            "import sys, armada, webview, clr_loader, pythonnet, bottle; "
                            "from armada import updater, ed25519, app, serve; "
                            "print(armada.__version__, updater.installed(), sys.flags.isolated or sys.flags.no_user_site, sep='|')"],
                           cwd=home, env=env, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            sys.exit(f"smoke import failed:\n{r.stderr}")
        v, inst, _ = r.stdout.strip().split("|")
        if v != ver or inst != "True":
            sys.exit(f"smoke: got version {v}, installed={inst}")
        say("smoke: the server answers with the welcome page (no realm yet)")
        port = _free_port()
        p = subprocess.Popen([str(py), "-m", "armada", "serve", "--port", str(port)], cwd=home, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            body = ""
            for _ in range(60):
                time.sleep(0.5)
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as resp:
                        body = resp.read().decode("utf-8", "replace")
                    break
                except OSError:
                    if p.poll() is not None:
                        break
            if "ARMADA" not in body:
                p.kill()
                out, _ = p.communicate(timeout=15)
                sys.exit(f"smoke: the staged app didn't serve a page:\n{(out or '')[:2000]}")
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=15)       # let it let go of its log file before cleanup
    say("smoke: ok")


def _iscc() -> Path:
    for c in ISCC_CANDIDATES:
        if c.exists():
            return c
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return Path(found)
    sys.exit("Inno Setup's compiler (ISCC.exe) wasn't found — install Inno Setup 7 (winget install --id JRSoftware.InnoSetup.7 -e)")


def compile_installer(stage_dir: Path, ver: str) -> Path:
    DIST.mkdir(exist_ok=True)
    iscc = _iscc()
    say(f"compiling with {iscc}")
    redist = _webview2_bootstrapper()
    # Compiled in a private temp folder and copied into dist\ after: dist\ is where the sandbox test
    # maps from, and a mapped (or scanned) folder can hold the half-written .exe open, which Inno
    # Setup reports as "EndUpdateResource failed" / "output file appears to be in use".
    work = Path(tempfile.mkdtemp(prefix="armada-iscc-"))
    cmd = [str(iscc), "/Q", f"/DAppVersion={ver}", f"/DStage={stage_dir}", f"/DRedist={redist}", f"/O{work}", str(ISS)]
    for attempt in range(3):
        # "EndUpdateResource failed" is Inno Setup's known clash with an antivirus scanning the new
        # .exe as it's written (Defender does it here); it passes on a second go.
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            break
        err = (r.stdout + r.stderr).strip()
        if not re.search(r"EndUpdateResource|in use", err):
            sys.exit(f"Inno Setup:\n{err[-2000:]}")            # a real error in the script: no retry
        say(f"compile failed (attempt {attempt + 1}); retrying — a scanner had the new .exe open")
        time.sleep(5)
    else:
        sys.exit("Inno Setup couldn't compile the installer")
    out = DIST / f"ARMADA-Setup-{ver}.exe"
    shutil.copy2(work / out.name, out)
    shutil.rmtree(work, ignore_errors=True)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    say(f"built {out}  ({out.stat().st_size / 1e6:.1f} MB, SHA-256 {digest})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stage-only", action="store_true", help="stage and smoke-test, don't compile")
    ap.add_argument("--no-smoke", action="store_true")
    a = ap.parse_args()
    if os.name != "nt":
        sys.exit("the installer is built on Windows")
    ver = _version()
    print(f"ARMADA installer v{ver}")
    st = stage(ver)
    if not a.no_smoke:
        smoke(st, ver)
    if not a.stage_only:
        compile_installer(st, ver)


if __name__ == "__main__":
    main()
