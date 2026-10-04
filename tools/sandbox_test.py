#!/usr/bin/env python3
"""Run the installer's clean-machine test in Windows Sandbox (launch plan 5.2 / 5.10).

    python tools/sandbox_test.py --installer dist/ARMADA-Setup-<version>.exe

Starts a fresh Windows Sandbox (a throwaway Windows that has never seen ARMADA, Python or Claude
Code) with `dist\\` mapped read-only and `build\\sandbox-results\\<run>\\` mapped writable, and runs
`installer\\sandbox\\clean-machine-test.ps1` at logon. Waits for it to finish and prints the report;
the screenshot of the first run lands beside it. The sandbox shuts down after recording the
result. Evidence records the SHA-256 of the exact installer that was tested.
"""
from __future__ import annotations

import shutil
import argparse
import hashlib
import json
import subprocess
import sys
import time
from xml.sax.saxutils import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "build" / "sandbox-runs"
SCRIPT_DIR = ROOT / "installer" / "sandbox"


def read_report(path):
    """The VM briefly holds an exclusive Windows write handle while appending a line."""
    try:
        return path.read_text(encoding='utf-8-sig', errors='replace')
    except (FileNotFoundError, PermissionError):
        return ''


def save_evidence(folder, installer, digest, report, text):
    passed = 'FAIL' not in text and 'DONE' in text and f'SHA256: {digest}' in text
    (folder/'evidence.json').write_text(json.dumps({'installer':installer.name,'sha256':digest,
        'passed':passed,'report':str(report)},indent=2),encoding='utf-8')
    return passed


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('--installer', required=True, type=Path)
    args = parser.parse_args()
    installer = args.installer.resolve()
    if not installer.is_file(): sys.exit('Installer not found')
    import re
    if not re.fullmatch(r'ARMADA-Setup-[0-9.]+\.exe', installer.name):
        sys.exit('Expected an ARMADA-Setup-<version>.exe installer')
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    sandbox = shutil.which("WindowsSandbox.exe") or r"C:\Windows\System32\WindowsSandbox.exe"
    if not Path(sandbox).exists():
        sys.exit("Windows Sandbox isn't enabled (Windows Features -> Windows Sandbox)")
    # A fresh folder per run: a sandbox that's just been closed can keep the last one's folder
    # mapped for a while, and then it can be neither deleted nor reused.
    RESULTS = RESULTS_ROOT / time.strftime("%Y%m%d-%H%M%S")
    RESULTS.mkdir(parents=True)
    wsb = RESULTS / "armada-clean-machine.wsb"
    wsb.write_text(f"""<Configuration>
  <Networking>Enable</Networking>
  <MappedFolders>
    <MappedFolder><HostFolder>{escape(str(installer.parent))}</HostFolder><SandboxFolder>C:\\armada-dist</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>{escape(str(SCRIPT_DIR))}</HostFolder><SandboxFolder>C:\\armada-test</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>{escape(str(ROOT / 'build/cache'))}</HostFolder><SandboxFolder>C:\\armada-redist</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>{escape(str(RESULTS))}</HostFolder><SandboxFolder>C:\\armada-results</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\armada-test\\clean-machine-test.ps1 -InstallerName {installer.name}</Command>
  </LogonCommand>
</Configuration>
""", encoding="utf-8")
    # Hide the host shell window; the sandbox runs its own visible-app checks internally.
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    process = subprocess.Popen([sandbox, str(wsb)], startupinfo=startup)
    report = RESULTS / "report.txt"
    print("Windows Sandbox starting; the test runs at its logon...", flush=True)
    text = ''
    for _ in range(600):                       # up to 20 minutes
        time.sleep(2)
        if process.poll() not in (None, 0):
            print(f'Windows Sandbox failed to start (exit {process.returncode})')
            break
        text = read_report(report) or text
        if "DONE" in text:
            break
    else:
        print("timed out waiting for the test to finish")
    text = read_report(report) or text or '(no report)'
    passed = save_evidence(RESULTS, installer, digest, report, text)
    print(text)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
