"""Opt-in CLI installation through the vendors' official Windows installers.

Shared by Inno Setup and App Settings. No sign-in or credentials are handled here.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading

from .engine.process import supervise

URLS = {"claude": "https://claude.ai/install.ps1",
        "codex": "https://chatgpt.com/codex/install.ps1", "gemini": "https://antigravity.google/cli/install.ps1"}
_lock = threading.Lock()
_states = {}


def command(provider):
    if provider not in URLS:
        raise ValueError("Unknown provider")
    # Values are fixed vendor URLs, never supplied by a request.
    script = ("$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
              "Import-Module (Join-Path $PSHOME 'Modules\\Microsoft.PowerShell.Utility\\Microsoft.PowerShell.Utility.psd1'); "
              "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding; "
              "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; ")
    if provider == "codex":
        script += "$env:CODEX_NON_INTERACTIVE='1'; "
    script += f"& ([scriptblock]::Create((Invoke-RestMethod -Uri '{URLS[provider]}'))); if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}"
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]


def install(provider):
    args = command(provider)
    if os.name != "nt":
        return {"ok": False, "error": "Automatic CLI installation is available on Windows."}
    try:
        result = supervise(args, prompt="", on_line=lambda _: None, timeout=600)
        if result.error or result.returncode != 0:
            import logging
            logging.getLogger(__name__).warning("%s installer failed: %s", provider, (result.error or result.stderr)[-2000:])
            return {"ok": False, "error": "Installation failed. Check your internet connection and retry, or use the installation guide."}
        from .engine import get_engine
        launcher = get_engine(provider)._launcher()
        if not launcher:
            return {"ok": False, "error": "Installation finished but the CLI was not found. Restart Armada and check again."}
        if provider == 'gemini':
            from . import providers
            providers._save(provider, executable_path=launcher[0])
        return {"ok": True}
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "error": "Installation could not finish. Check your internet connection and retry."}


def state(provider):
    with _lock:
        return dict(_states.get(provider, {}))


def start(provider):
    command(provider)  # validate before creating work
    with _lock:
        if _states.get(provider, {}).get("pending"):
            return {"ok": True, "pending": True}
        _states[provider] = {"pending": True}
    def work():
        result = install(provider)
        with _lock:
            _states[provider] = {**result, "pending": False}
    threading.Thread(target=work, daemon=True, name=f"install-{provider}").start()
    return {"ok": True, "pending": True}


if __name__ == "__main__":
    result = install(sys.argv[1] if len(sys.argv) == 2 else "")
    if result.get("error"):
        print(result["error"])
    raise SystemExit(0 if result["ok"] else 1)
