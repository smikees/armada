#!/usr/bin/env python3
"""Run the installer's clean-machine test in Windows Sandbox (launch plan 5.2 / 5.10).

    python tools/sandbox_test.py

Starts a fresh Windows Sandbox (a throwaway Windows that has never seen ARMADA, Python or Claude
Code) with `dist\\` mapped read-only and `build\\sandbox-results\\<run>\\` mapped writable, and runs
`installer\\sandbox\\clean-machine-test.ps1` at logon. Waits for it to finish and prints the report;
the screenshot of the first run lands beside it. The sandbox stays open afterwards with ARMADA
installed, for a person to try; closing it throws everything away.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "build" / "sandbox-runs"
SCRIPT_DIR = ROOT / "installer" / "sandbox"


def main() -> int:
    if not list((ROOT / "dist").glob("ARMADA-Setup-*.exe")):
        sys.exit("no installer in dist\\ â€” run tools/build_installer.py first")
    sandbox = shutil.which("WindowsSandbox.exe") or r"C:\Windows\System32\WindowsSandbox.exe"
    if not Path(sandbox).exists():
        sys.exit("Windows Sandbox isn't enabled (Windows Features â†’ Windows Sandbox)")
    # A fresh folder per run: a sandbox that's just been closed can keep the last one's folder
    # mapped for a while, and then it can be neither deleted nor reused.
    RESULTS = RESULTS_ROOT / time.strftime("%Y%m%d-%H%M%S")
    RESULTS.mkdir(parents=True)
    wsb = RESULTS / "armada-clean-machine.wsb"
    wsb.write_text(f"""<Configuration>
  <Networking>Enable</Networking>
  <MappedFolders>
    <MappedFolder><HostFolder>{ROOT / 'dist'}</HostFolder><SandboxFolder>C:\\armada-dist</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>{SCRIPT_DIR}</HostFolder><SandboxFolder>C:\\armada-test</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>{RESULTS}</HostFolder><SandboxFolder>C:\\armada-results</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\armada-test\\clean-machine-test.ps1</Command>
  </LogonCommand>
</Configuration>
""", encoding="utf-8")
    subprocess.Popen([sandbox, str(wsb)])
    report = RESULTS / "report.txt"
    print("Windows Sandbox starting; the test runs at its logonâ€¦", flush=True)
    for _ in range(600):                       # up to 20 minutes
        time.sleep(2)
        if report.exists() and "DONE" in report.read_text(encoding="utf-8", errors="replace"):
            break
    else:
        print("timed out waiting for the test to finish")
    text = report.read_text(encoding="utf-8", errors="replace") if report.exists() else "(no report)"
    print(text)
    return 0 if "FAIL" not in text and "DONE" in text else 1


if __name__ == "__main__":
    sys.exit(main())
