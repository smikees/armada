#!/usr/bin/env python3
"""Build and sign an update release for installed copies of ARMADA (launch plan 5.4, ADR-011).

    python tools/build_release.py [--key PATH] [--out DIR]

Makes, in dist/v<version>/:

    armada-<version>.zip      the committed armada/ folder (git ls-files — nothing untracked, so no
                              local keys or caches can ride along)
    armada-update.json        the manifest the updater reads
    armada-update.json.sig    Ed25519 signature over the manifest's exact bytes, base64

Refuses to build from uncommitted package files: a release is a commit. Signs with the private key
in MATCAP-private/update-signing.key (outside the repo), then checks the signature against the
public key compiled into armada/updater.py — a release signed with the wrong key would be refused by
every installed copy, so it's caught here instead.

Publishing is separate (RELEASING §6):

    gh release create v<version> dist/v<version>/* --title "ARMADA v<version>" --notes "…"

Release assets must be uploaded as a normal (not pre-release) release: the updater follows GitHub's
/releases/latest/download/ link, which skips drafts and pre-releases.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from armada import ed25519, updater  # noqa: E402

DEFAULT_KEY = ROOT.parent / "MATCAP-private" / "update-signing.key"


def _version() -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "armada" / "__init__.py").read_text(encoding="utf-8"))
    if not m:
        sys.exit("no __version__ in armada/__init__.py")
    return m.group(1)


def _git(*args) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def _load_key(path: Path) -> bytes:
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    seed = bytes.fromhex(lines[0])
    if len(seed) != 32:
        sys.exit("the signing key must be 32 bytes of hex")
    return seed


def build(key_path: Path, out_root: Path) -> Path:
    ver = _version()
    if _git("status", "--porcelain", "--untracked-files=no", "--", "armada").strip():   # only tracked files ship
        sys.exit("armada/ has uncommitted changes — commit first; a release is a commit")
    files = [f for f in _git("ls-files", "--", "armada").splitlines() if f]
    if not files:
        sys.exit("git lists no files under armada/")
    out = out_root / f"v{ver}"
    out.mkdir(parents=True, exist_ok=True)
    zname = f"armada-{ver}.zip"
    zpath = out / zname
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in sorted(files):
            zf.write(ROOT / f, f)
    blob = zpath.read_bytes()
    manifest = {
        "format": 1, "app": "armada", "version": ver, "zip": zname,
        "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
        "runtime": updater.runtime_tag((ROOT / "requirements.txt").read_text(encoding="utf-8"), "3.12"),
        "commit": _git("rev-parse", "HEAD").strip(),
        "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    raw = json.dumps(manifest, indent=2).encode("utf-8")
    seed = _load_key(key_path)
    sig = ed25519.sign(seed, raw)
    if not ed25519.verify(updater.PUBLIC_KEY, raw, sig):
        sys.exit("this key isn't the one armada/updater.py trusts — installed copies would refuse the release")
    (out / updater.MANIFEST).write_bytes(raw)
    (out / updater.SIGNATURE).write_bytes(base64.b64encode(sig) + b"\n")
    updater.verified_manifest(raw, base64.b64encode(sig))      # the updater's own checks, end to end
    print(f"built {out}  ({len(files)} files, {len(blob):,} bytes, runtime {manifest['runtime']})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY)
    ap.add_argument("--out", type=Path, default=ROOT / "dist")
    a = ap.parse_args()
    build(a.key, a.out)


if __name__ == "__main__":
    main()
