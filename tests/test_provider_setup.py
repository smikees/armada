"""Fresh install, browser login ownership, and explicit provider failure states."""
import io
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest

from armada import auth, provider_install, provider_login
from armada.engine.codex import CodexEngine


@pytest.mark.parametrize('text,code,ok,logged', [
    ('Logged in using ChatGPT', 0, True, True),
    ('Not logged in', 1, True, False),
    ('Not logged in', 0, True, False),
    ('Error loading configuration: CODEX_HOME does not exist', 1, False, False),
    ('Unexpected output', 0, False, False),
])
def test_codex_probe_distinguishes_signout_from_cli_failure(monkeypatch, text, code, ok, logged):
    eng = CodexEngine()
    monkeypatch.setattr(eng, '_probe', lambda *a: SimpleNamespace(stdout='', stderr=text, returncode=code))
    result = eng.auth_status()
    assert result['ok'] is ok and result['logged_in'] is logged


@pytest.mark.parametrize('value', ['false', 'true', 1, None])
def test_claude_does_not_treat_malformed_auth_as_signed_in(monkeypatch, value):
    import json
    monkeypatch.setattr(auth, '_launcher', lambda: ['claude'])
    monkeypatch.setattr(auth.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout=json.dumps({'loggedIn': value})))
    assert not auth.status(force=True)['logged_in']


@pytest.mark.parametrize('url', ['https://evil.example/oauth/authorize',
    'https://auth.openai.com.evil.example/oauth/authorize', 'https://user@auth.openai.com/oauth/authorize',
    'https://auth.openai.com:444/oauth/authorize', 'https://auth.openai.com/logout'])
def test_login_page_only_accepts_official_authorization_endpoints(url):
    assert provider_login.authorization_url('codex', url) == ''


def until(check):
    deadline = time.monotonic() + 3
    while not check() and time.monotonic() < deadline:
        time.sleep(.01)
    assert check()


@pytest.fixture
def login(monkeypatch):
    from armada.engine import windows_job
    done = threading.Event()
    calls = []
    proc = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO(b'Open https://auth.openai.com/oauth/authorize?state=fixture'),
        poll=lambda: 1 if done.is_set() else None, kill=done.set)
    def wait(timeout):
        if not done.wait(min(timeout, 3)):
            raise subprocess.TimeoutExpired('fixture', timeout)
        return 1
    proc.wait = wait
    monkeypatch.setattr(provider_login, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(provider_login, '_attempts', {})
    monkeypatch.setattr(provider_login.subprocess, 'Popen', lambda cmd, **kw: calls.append((cmd, kw)) or proc)
    monkeypatch.setattr(windows_job, 'WindowsJob', lambda: SimpleNamespace(attach_and_resume=lambda p: None, close=done.set))
    yield calls, proc, done
    provider_login._close()
    done.set()
    until(lambda: not provider_login.state('codex')['pending'])


def test_official_login_is_deduplicated_and_can_reopen_browser(login, monkeypatch):
    calls, proc, done = login
    assert provider_login.begin('codex', ['codex'])['pending']
    assert provider_login.begin('codex', ['codex'])['pending']
    until(lambda: provider_login.state('codex')['can_open_login'])
    assert len(calls) == 1 and calls[0][0] == ['codex', 'login']
    assert 'shell' not in calls[0][1] and calls[0][1]['stdin'] == subprocess.PIPE
    opened = []
    monkeypatch.setattr(provider_login.webbrowser, 'open', lambda url, **kw: opened.append(url) or True)
    assert provider_login.open_page('codex')['ok'] and opened
    assert provider_login.state('codex')['login_url'] == opened[0]
    provider_login.cancel('codex')
    assert done.is_set() and not provider_login.open_page('codex')['ok']
    assert provider_login.state('codex')['login_url'] == ''


def test_failed_login_keeps_an_actionable_error(login):
    _, _, done = login
    provider_login.begin('codex', ['codex'])
    done.set()
    until(lambda: not provider_login.state('codex')['pending'])
    assert 'try again' in provider_login.state('codex')['login_error']


def test_login_timeout_closes_owned_tree_and_allows_retry(login):
    _, proc, done = login
    def wait(timeout):
        if timeout == 600:
            raise subprocess.TimeoutExpired('fixture', timeout)
        return 1
    proc.wait = wait
    provider_login.begin('codex', ['codex'])
    until(lambda: not provider_login.state('codex')['pending'])
    assert done.is_set()
    assert 'timed out' in provider_login.state('codex')['login_error']
    assert not provider_login.state('codex')['can_open_login']


def test_install_timeout_uses_owned_process_and_reports_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(provider_install, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(provider_install, 'supervise', lambda *a, **kw:
        calls.append(kw) or SimpleNamespace(returncode=None, error='Timed out'))
    assert not provider_install.install('codex')['ok']
    assert calls[0]['timeout'] == 600 and calls[0]['prompt'] == ''


@pytest.mark.parametrize('provider,url', [('claude', 'https://claude.ai/install.ps1'), ('codex', 'https://chatgpt.com/codex/install.ps1'), ('gemini', 'https://antigravity.google/cli/install.ps1')])
def test_installer_uses_fixed_vendor_source(provider, url):
    cmd = provider_install.command(provider)
    assert cmd[0] == 'powershell.exe' and url in cmd[-1]
    assert 'login' not in cmd[-1]
    assert "Join-Path $PSHOME" in cmd[-1] and 'Microsoft.PowerShell.Utility.psd1' in cmd[-1]
    with pytest.raises(ValueError):
        provider_install.command('codex; arbitrary command')


def test_folder_picker_passes_an_existing_start_directory(monkeypatch, tmp_path):
    from armada.routes.realm import RealmRoutes
    from pathlib import Path
    import sys
    seen = []
    window = SimpleNamespace(create_file_dialog=lambda kind, **kw: seen.append(kw['directory']) or None)
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(windows=[window], FileDialog=SimpleNamespace(FOLDER=1)))
    assert not RealmRoutes._pick_folder(object())['ok']
    assert Path(seen[0]).is_dir()
