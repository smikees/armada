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
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
GH = r"C:\Program Files\GitHub CLI\gh.exe"
REPO = "smikees/armada"


def _run(*cmd, **kw) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True, **kw).stdout.strip()


def notes(ver: str, *, unsigned=False) -> str:
    from armada.webui import changelog
    from armada import runtime_spec
    lines = next((ls for v, ls in changelog._CHANGELOG if v == ver), None)
    if not lines:
        sys.exit(f"no changelog entry for {ver}")
    return (f"ARMADA {ver} (beta).\n\n"
            f"**New install:** download `ARMADA-Setup-{ver}.exe` and run it. It installs for you alone "
            "(no administrator rights) and brings its own Python. " +
            ("This maintenance beta installer is unsigned and may be blocked by Windows Application Control (error 4551). "
             if unsigned else "Windows publisher signatures cover the installer, its temporary executable and native components. ") +
            "ARMADA runs your agents through Claude Code (Anthropic), Codex CLI (OpenAI), or "
            "Antigravity CLI (Google/Gemini), using your connected accounts. The setup wizard "
            "checks installation and sign-in for all three engines.\n\n"
            f"**Upgrading from before {runtime_spec.INSTALLER_BASELINE_VERSION}:** run the full installer "
            "to update ARMADA's bundled runtime. Let current work finish and quit ARMADA before running it. "
            "Your realms and settings are preserved. Later compatible "
            "updates install through Settings and verify the update signature.\n\n"
            "What's new:\n\n" + "\n".join(f"- {l}" for l in lines) +
            "\n\nARMADA is source-available under the PolyForm Noncommercial License 1.0.0.\n")


def installer_command(python, *, maintenance_unsigned=False):
    return [python, 'tools/build_installer.py', *(['--allow-unsigned'] if maintenance_unsigned else [])]


def wait_for_ci(sha, timeout=900, *, run_id=None):
    """Allow CI to finish after the local gate; never substitute another source run."""
    deadline = time.monotonic() + timeout
    while True:
        if run_id is not None:
            run = json.loads(_run(GH, 'api', '-X', 'GET', f'repos/{REPO}/actions/runs/{run_id}'))
            if (run.get('head_sha') != sha or run.get('head_branch') != 'main'
                    or run.get('path') != '.github/workflows/windows-ci.yml'
                    or run.get('repository', {}).get('full_name') != REPO
                    or run.get('event') not in ('push', 'workflow_dispatch')):
                sys.exit('Windows CI run must validate this exact main commit with windows-ci.yml')
            if run.get('status') == 'completed':
                if run.get('conclusion') != 'success':
                    sys.exit('Windows CI failed for this exact release commit')
                from armada import runtime_spec
                jobs = json.loads(_run(GH, 'api', '-X', 'GET',
                    f'repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100')).get('jobs', [])
                required = {f'tests ({runtime_spec.PYTHON_VERSION})', 'tests (3.14)', 'relay'}
                passed = {j.get('name') for j in jobs
                          if j.get('status') == 'completed' and j.get('conclusion') == 'success'}
                if not required <= passed or any(j.get('conclusion') != 'success' for j in jobs):
                    sys.exit('Windows CI must pass both Python jobs and relay without skipped jobs')
                return {'run_id': run_id, 'event': run['event'], 'url': run.get('html_url')}
            if time.monotonic() >= deadline:
                sys.exit('Windows CI has not passed for this exact release commit within 15 minutes')
            time.sleep(min(10, max(0, deadline-time.monotonic())))
            continue
        result = json.loads(_run(GH, 'api', '-X', 'GET',
            f'repos/{REPO}/actions/workflows/windows-ci.yml/runs', '-f', f'head_sha={sha}', '-f', 'per_page=20'))
        runs = [r for r in result.get('workflow_runs', [])
                if r.get('head_sha') == sha and r.get('event') == 'push']
        for run in runs:
            if run.get('status') == 'completed' and run.get('conclusion') == 'success':
                return {'run_id': run.get('id'), 'event': run['event'], 'url': run.get('html_url')}
        if runs and all(r.get('status') == 'completed' for r in runs):
            sys.exit('Windows CI failed for this exact release commit')
        if time.monotonic() >= deadline:
            sys.exit('Windows CI has not passed for this exact release commit within 15 minutes')
        time.sleep(min(10, max(0, deadline-time.monotonic())))


def main(argv=()) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--maintenance-unsigned', action='store_true',
                        help='Recorded maintainer-authorized unsigned beta distribution; all app/upgrade gates remain mandatory')
    parser.add_argument('--ci-run', type=int,
                        help='Exact-main Windows workflow run to verify, including a manual dispatch when push delivery is stuck')
    args = parser.parse_args(argv)
    if args.ci_run is not None and args.ci_run <= 0:
        parser.error('--ci-run must be a positive workflow run ID')
    from armada import __version__ as ver
    if _run("git", "status", "--porcelain"):
        sys.exit("uncommitted changes — a release is a commit")
    sha = _run("git", "rev-parse", "HEAD")
    from tools.release_gate import run as run_gate
    run_gate()
    if _run('git','rev-parse','HEAD') != sha or _run('git','status','--porcelain'):
        sys.exit('Source changed during the local gate; validate the new commit again')
    _run("git", "fetch", "--quiet", "origin")
    if sha != _run("git", "rev-parse", "origin/main"):
        sys.exit("HEAD isn't origin/main — push first")
    ci = wait_for_ci(sha, run_id=args.ci_run) if args.ci_run is not None else wait_for_ci(sha)
    if subprocess.run([GH, "release", "view", f"v{ver}", "--repo", REPO], cwd=ROOT,
                      capture_output=True).returncode == 0:
        sys.exit(f"v{ver} is already released")
    py = sys.executable
    subprocess.run([py, "tools/build_release.py"], cwd=ROOT, check=True)
    subprocess.run(installer_command(py, maintenance_unsigned=args.maintenance_unsigned), cwd=ROOT, check=True)
    dist = ROOT / "dist"
    if not args.maintenance_unsigned:
        subprocess.run([py, "tools/sandbox_test.py", '--installer', str(dist/f'ARMADA-Setup-{ver}.exe')],
                       cwd=ROOT,check=True)
    # The native upgrade gate is mandatory for both publication paths, with exact signed assets.
    previous = ROOT/'build/previous-release'
    previous.mkdir(parents=True,exist_ok=True)
    tag = json.loads(_run(GH,'release','view','--repo',REPO,'--json','tagName'))['tagName']
    _run(GH,'release','download',tag,'--repo',REPO,'--pattern','armada*','--dir',str(previous),'--clobber')
    report = ROOT/'build'/f'upgrade-{ver}.json'
    report.unlink(missing_ok=True)
    subprocess.run([py,'tools/upgrade_probe.py','--stage',str(ROOT/'build/installer/ARMADA'),
                    '--previous',str(previous),'--candidate',str(dist/f'v{ver}'),'--output',str(report)],
                   cwd=ROOT,check=True)
    evidence = json.loads(report.read_text(encoding='utf-8'))
    if evidence.get('commit') != sha or not evidence.get('ok'):
        sys.exit('Packaged upgrade evidence does not match this release commit')
    if _run('git','rev-parse','HEAD') != sha or _run('git','status','--porcelain'):
        sys.exit('Source changed during validation; rerun the release gate')
    assets = [dist / f"ARMADA-Setup-{ver}.exe", *sorted((dist / f"v{ver}").iterdir())]
    nf = ROOT / "build" / f"notes-{ver}.md"
    nf.write_text(notes(ver,unsigned=args.maintenance_unsigned), encoding="utf-8")
    installer = dist/f'ARMADA-Setup-{ver}.exe'
    (ROOT/'build'/f'release-evidence-{ver}.json').write_text(json.dumps({
        'commit':sha, 'version':ver, 'installer_sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),
        'upgrade':evidence, 'ci':ci, 'unsigned_maintenance':args.maintenance_unsigned,
        'sandbox': 'not_verified_unsigned_maintenance' if args.maintenance_unsigned else 'passed'},indent=2),encoding='utf-8')
    out = _run(GH, "release", "create", f"v{ver}", "--repo", REPO, "--target", sha,
               "--title", f"ARMADA v{ver} (beta)", "--notes-file", str(nf), *map(str, assets))
    print(out)


if __name__ == "__main__":
    main(sys.argv[1:])
