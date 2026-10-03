"""The installer build (launch plan 5.2, ADR-009): the parts that can be checked on any machine.

Building the .exe needs Windows, uv and Inno Setup (tools/build_installer.py smoke-tests the staged
app and compiles), and the clean-machine run needs Windows Sandbox (tools/sandbox_test.py). What's
here guards the agreements between those pieces and the app, so a change to one can't quietly
break another: the path file that makes `pythonw -m armada` work, the notices table the build
checks against, the Start-menu identity the app declares, the files uninstall must never touch.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ISS = (ROOT / "installer" / "armada.iss").read_text(encoding="utf-8")


def _build():
    spec = importlib.util.spec_from_file_location("build_installer", ROOT / "tools" / "build_installer.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_path_file_puts_the_install_folder_and_site_packages_on_the_path():
    lines = _build().pth_text().splitlines()
    assert ".." in lines, "without the install folder on the path, `-m armada` can't find the package"
    assert "Lib\\site-packages" in lines and "import site" in lines
    assert lines[0] == "python312.zip"


def test_the_notices_table_matches_what_the_installer_bundles():
    b = _build()
    assert b._notices_versions() == b._requirements(), \
        "THIRD_PARTY_NOTICES.md and requirements.txt disagree; the build refuses to run until they match"


def test_a_package_without_its_own_licence_has_one_kept_in_the_repo():
    assert (ROOT / "installer" / "licenses" / "proxy-tools-0.1.0" / "LICENSE.txt").exists()


def test_the_python_download_is_pinned_by_hash():
    b = _build()
    assert re.fullmatch(r"[0-9a-f]{64}", b.PY_SHA256)
    assert b.PY_URL.startswith("https://www.python.org/ftp/python/3.12.")
    assert b.PTH_NAME == "python312._pth"


def test_the_shortcut_carries_the_same_app_id_as_the_window():
    from armada import app
    m = re.search(r'#define AppUserModelID "([^"]+)"', ISS)
    assert m and m.group(1) == app._APP_ID, "toasts and the taskbar need the shortcut and the window to agree"
    assert '#define AppExe "{app}\\python\\ARMADA.exe"' in ISS
    assert 'Filename: "{#AppExe}"; Parameters: "-m armada app"' in ISS
    assert (ROOT / "installer" / "ArmadaLauncher.cs").exists()


def test_installs_per_user_and_starts_the_scheduler_with_the_app():
    assert "PrivilegesRequired=lowest" in ISS
    assert re.search(r'ValueName: "ARMADA Scheduler"; Flags: deletevalue', ISS)
    assert "schedsvc.ensure_running(root)" in (ROOT / "armada" / "app.py").read_text(encoding="utf-8")


def test_uninstall_never_touches_the_users_data():
    removed = re.findall(r'^Type: \w+; Name: "([^"]+)"', ISS.split("[UninstallDelete]")[1].split("[")[0], re.M)
    assert removed and all(p.startswith("{app}") for p in removed)
    section = ISS.split("[UninstallDelete]")[1].split("[Code]")[0]
    assert not any(".armada" in l or "{%USERPROFILE}" in l or "{userdocs}" in l
                   for l in section.splitlines() if not l.startswith(";"))


def test_uninstall_and_upgrade_only_stop_processes_running_this_installs_python():
    stop = ISS[ISS.index("procedure StopArmada"):ISS.index("function PrepareToInstall")]
    assert "StartsWith(" in stop and "\\python\\" in stop
    assert "Get-Process python,pythonw,ARMADA" in stop
    assert "taskkill" not in ISS.lower()                       # would kill every Python on the machine


def test_webview2_is_installed_when_missing():
    assert "MicrosoftEdgeWebview2Setup.exe" in ISS and "procedure InstallWebView2" in ISS
    assert "F3017226-FE2A-4295-8BDF-00C3A9A7E4C5" in ISS
    wv = ISS[ISS.index("procedure InstallWebView2"):ISS.index("procedure CurStepChanged")]
    # quietly for this user first, then (asking first) for all users with Windows' admin prompt
    assert wv.index("Exec(Exe") < wv.index("ShellExec('runas'") and "WizardSilent()" in wv


@pytest.mark.parametrize("status,subject,accepted", [
    ("Valid", "CN=Microsoft Corporation, O=Microsoft Corporation", True),
    ("NotSigned", "", False),
    ("Valid", "CN=Other Publisher, O=Other Publisher", False),
])
def test_webview2_requires_a_valid_microsoft_signature(tmp_path, monkeypatch, status, subject, accepted):
    from subprocess import CompletedProcess
    b = _build()
    monkeypatch.setattr(b, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(b, "REDIST", tmp_path / "redist")
    b.CACHE.mkdir()
    exe = b.CACHE / b.WEBVIEW2_EXE
    exe.write_bytes(b"test bootstrapper")

    def verify(command, **kwargs):
        assert "Import-Module (Join-Path $PSHOME" in command[-1]
        assert "Microsoft.PowerShell.Security.psd1" in command[-1]
        return CompletedProcess(command, 0, f"{status}|{subject}\n", "")

    monkeypatch.setattr(b.subprocess, "run", verify)
    if accepted:
        assert (b._webview2_bootstrapper() / b.WEBVIEW2_EXE).read_bytes() == exe.read_bytes()
    else:
        with pytest.raises(SystemExit, match="refusing it"):
            b._webview2_bootstrapper()
        assert not exe.exists() and not b.REDIST.exists()


def test_webview2_verifier_failure_preserves_cache_and_reports_exact_error(tmp_path, monkeypatch):
    from subprocess import CompletedProcess
    b = _build()
    monkeypatch.setattr(b, "CACHE", tmp_path)
    monkeypatch.setattr(b, "REDIST", tmp_path / "redist")
    exe = tmp_path / b.WEBVIEW2_EXE
    exe.write_bytes(b"test bootstrapper")
    monkeypatch.setattr(b.subprocess, "run", lambda *a, **k: CompletedProcess(a, 1, "", "security module unavailable"))
    with pytest.raises(SystemExit, match="security module unavailable"):
        b._webview2_bootstrapper()
    assert exe.exists() and not b.REDIST.exists()


def test_gemini_install_is_optional_and_detected_alongside_other_engines():
    assert 'Name: "geminicli"' in ISS
    assert "InstallProviderCLI('gemini', 'Antigravity CLI for Gemini')" in ISS
    assert "not ClaudeFound() and not CodexFound() and not GeminiFound()" in ISS
    assert r"{localappdata}\agy\bin\agy.exe" in ISS


def test_the_window_refuses_to_open_without_webview2_before_starting_anything():
    from armada import app
    src = Path(app.__file__).read_text(encoding="utf-8")
    run = src[src.index("def run("):]
    assert run.index("webview2_version()") < run.index("threading.Thread"), \
        "check WebView2 before the server starts, or a refused window leaves a server behind"
    assert app.webview2_version() == "" or re.match(r"\d", app.webview2_version())


def test_the_sandbox_test_is_there_for_5_10():
    assert (ROOT / "installer" / "sandbox" / "clean-machine-test.ps1").exists()
    assert (ROOT / "tools" / "sandbox_test.py").exists()


def test_the_installer_is_branded_and_its_artwork_exists():
    """Mihai, 2026-09-25: the installer carries ARMADA's branding. Every image the script names
    must be in the repo (a missing one fails the compile on the build machine, not here)."""
    import re as _re
    assert "WizardStyle=modern dynamic" in ISS and "DisableWelcomePage=no" in ISS
    names = set()
    for key in ("WizardImageFile", "WizardImageFileDynamicDark", "WizardSmallImageFile",
                "WizardSmallImageFileDynamicDark"):
        m = _re.search(rf"^{key}=(.+)$", ISS, _re.M)
        assert m, key
        names |= {n.strip() for n in m.group(1).split(",")}
    for n in names:
        assert (ROOT / "installer" / n.replace("\\", "/")).exists(), n


def test_the_help_pages_ship_inside_the_package():
    """The installer and the updater ship armada/ only. Help read docs/user/ at the repo root until
    v0.99.72, so every installed copy had an empty Help page (found on Mihai's install)."""
    from armada.webui import pages
    pkg = ROOT / "armada"
    assert pages._DOCS_USER.resolve().is_relative_to(pkg.resolve())
    assert (pages._DOCS_USER / "index.md").exists() and len(pages._doc_toc()) >= 10
