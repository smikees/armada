#!/usr/bin/env python3
"""Publish the current version to GitHub Releases (RELEASING §6b; Mihai, 2026-09-24: every release).

    python tools/publish_release.py

Run on Windows after the release commit is pushed. It builds the signed update files
(tools/build_release.py) and the installer (tools/build_installer.py) from that commit, writes the
release notes from this version's changelog entry, and creates the release `v<version>` on
github.com/smikees/armada with all four assets, as a normal (latest) release — the updater follows
`/releases/latest/download/`, which skips drafts and pre-releases. Installed copies pick it up
within 12 hours, or at once from Settings → Check for updates.

Refuses if the tree isn't clean, HEAD isn't on origin/main, or the version is already released.
"""
from __future__ import annotations

import re
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
GH = r"C:\Program Files\GitHub CLI\gh.exe"
REPO = "smikees/armada"


def _run(*cmd, **kw) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True, **kw).stdout.strip()


def notes(ver: str) -> str:
    from armada.webui import changelog
    lines = next((ls for v, ls in changelog._CHANGELOG if v == ver), None)
    if not lines:
        sys.exit(f"no changelog entry for {ver}")
    return (f"ARMADA {ver} (beta).\n\n"
            f"**New install:** download `ARMADA-Setup-{ver}.exe` and run it. It installs for you alone "
            "(no administrator rights) and brings its own Python. Windows publisher signatures cover "
            "the installer, its temporary executable and native components. "
            "ARMADA runs your agents through Claude Code (Anthropic), Codex CLI (OpenAI), or "
            "Antigravity CLI (Google/Gemini), using your connected accounts. The setup wizard "
            "checks installation and sign-in for all three engines.\n\n"
            "**Upgrading from 0.99.74 or earlier:** run the new installer once to add the recovery "
            "bootstrap and timezone data. Your realms and settings are preserved. Later compatible "
            "updates install through Settings and verify the update signature.\n\n"
            "What's new:\n\n" + "\n".join(f"- {l}" for l in lines) +
            "\n\nARMADA is source-available under the PolyForm Noncommercial License 1.0.0.\n")


def main() -> None:
    from armada import __version__ as ver
    if _run("git", "status", "--porcelain"):
        sys.exit("uncommitted changes — a release is a commit")
    from release_gate import run as run_gate
    run_gate()
    _run("git", "fetch", "--quiet", "origin")
    sha = _run("git", "rev-parse", "HEAD")
    if sha != _run("git", "rev-parse", "origin/main"):
        sys.exit("HEAD isn't origin/main — push first")
    runs = json.loads(_run(GH, 'api', '-X', 'GET',
        f'repos/{REPO}/actions/workflows/windows-ci.yml/runs', '-f', f'head_sha={sha}', '-f', 'per_page=20'))
    if not any(run.get('head_sha') == sha and run.get('event') == 'push'
               and run.get('status') == 'completed' and run.get('conclusion') == 'success'
               for run in runs.get('workflow_runs', [])):
        sys.exit('Windows CI has not passed for this exact release commit')
    if subprocess.run([GH, "release", "view", f"v{ver}", "--repo", REPO], cwd=ROOT,
                      capture_output=True).returncode == 0:
        sys.exit(f"v{ver} is already released")
    py = sys.executable
    subprocess.run([py, "tools/build_release.py"], cwd=ROOT, check=True)
    subprocess.run([py, "tools/build_installer.py"], cwd=ROOT, check=True)
    dist = ROOT / "dist"
    subprocess.run([py, "tools/sandbox_test.py", '--installer', str(dist/f'ARMADA-Setup-{ver}.exe')],
                   cwd=ROOT,check=True)
    if _run('git','rev-parse','HEAD') != sha or _run('git','status','--porcelain'):
        sys.exit('Source changed during validation; rerun the release gate')
    assets = [dist / f"ARMADA-Setup-{ver}.exe", *sorted((dist / f"v{ver}").iterdir())]
    nf = ROOT / "build" / f"notes-{ver}.md"
    nf.write_text(notes(ver), encoding="utf-8")
    out = _run(GH, "release", "create", f"v{ver}", "--repo", REPO, "--target", sha,
               "--title", f"ARMADA v{ver} (beta)", "--notes-file", str(nf), *map(str, assets))
    print(out)


if __name__ == "__main__":
    main()
