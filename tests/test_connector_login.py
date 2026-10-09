"""OAuth outcomes are observed, bounded and never inferred from process launch."""
import threading
import time

import pytest
from armada import connector_login as login
from armada.engine.process import ProcessResult


@pytest.fixture(autouse=True)
def attempts(monkeypatch):
    monkeypatch.setattr(login, '_attempts', {})
    monkeypatch.setattr(login, '_closing', False)


def test_actual_codex_registration_refusal_is_visible(monkeypatch):
    reason = 'Error: Registration failed: Dynamic registration failed: Registration failed: Dynamic client registration not supported'
    monkeypatch.setattr(login, 'supervise', lambda *a, **kw: ProcessResult(returncode=1, stderr=reason))
    result = login.begin(('realm', 'codex', 'drive'), ['codex', 'mcp', 'login', 'drive'])
    assert not result['ok'] and result['state'] == 'failed'
    assert result['error'] == reason
    assert result['login_url'] == ''


def test_url_is_available_only_during_owned_attempt_and_deduplicates(monkeypatch):
    finish = threading.Event(); done = threading.Event(); calls = []
    url = 'https://accounts.example.invalid/authorize?response_type=code&client_id=test&state=secret'
    def supervise(args, **kwargs):
        calls.append(kwargs)
        kwargs['on_line']('Open: ' + url)
        assert finish.wait(3)
        return ProcessResult(returncode=0)
    monkeypatch.setattr(login, 'supervise', supervise)
    key = ('realm', 'codex', 'drive')
    try:
        result = login.begin(key, ['codex'], on_finish=done.set)
        assert result['state'] == 'sign_in' and result['login_url'] == url
        assert login.begin(key, ['codex'])['state'] == 'sign_in'
        assert len(calls) == 1 and calls[0]['timeout'] == 300
    finally:
        finish.set()
    assert done.wait(3)
    assert login.state(key)['state'] == 'configured'
    assert login.state(key)['login_url'] == ''


@pytest.mark.parametrize('url', [
    'http://accounts.example/authorize?response_type=code&client_id=x',
    'https://user:secret@accounts.example/authorize?response_type=code&client_id=x',
    'https://accounts.example:444/authorize?response_type=code&client_id=x',
    'https://accounts.example/?client_id=x',
    'https://accounts.example/?response_type=token&client_id=x',
    'javascript:alert(1)',
])
def test_non_authorization_urls_are_not_exposed(url):
    assert login._url(url) == ''


def test_failure_redacts_oauth_values_and_clears_authorization_url(monkeypatch):
    monkeypatch.setattr(login, 'supervise', lambda *a, **kw: ProcessResult(returncode=1,
        stderr='invalid_grant https://a.invalid/?state=hidden access_token=secret client_secret:private code=hidden'))
    result = login.begin(('realm', 'claude', 'drive'), ['claude'])
    assert not result['ok']
    assert 'invalid_grant' in result['error']
    for value in ('secret', 'private', 'hidden', 'https://'):
        assert value not in result['error'].replace('client_secret', '')
    assert not result['login_url']


def test_failure_redacts_bearer_and_quoted_credentials():
    result = login._error('Authorization: Bearer secret-token {"client_secret": "private", "access_token": "access"}')
    assert 'secret-token' not in result and 'private' not in result and '"access"' not in result


def test_timeout_keeps_deadline_reason_even_with_other_stderr(monkeypatch):
    monkeypatch.setattr(login, 'supervise', lambda *a, **kw: ProcessResult(returncode=1,
        error='CLI timed out after 300s', stderr='Waiting for sign-in', timed_out=True))
    assert login.begin('timeout', ['codex'])['error'] == 'CLI timed out after 300s'


def test_owned_process_is_cancelled_on_shutdown_even_when_started_late(monkeypatch):
    calls = []
    login._close()
    result = login.begin(('realm', 'codex', 'drive'), ['codex'])
    assert not result['ok']
    monkeypatch.setattr(login, '_closing', False)
    def supervise(args, **kw):
        login._close()
        kw['on_proc'](type('Handle', (), {'kill': lambda self: calls.append('cancel')})())
        return ProcessResult(returncode=1, error='Run stopped by the owner.')
    monkeypatch.setattr(login, 'supervise', supervise)
    assert not login.begin(('realm', 'codex', 'drive'), ['codex'])['ok']
    assert calls == ['cancel']


def test_terminal_states_expire_without_retaining_login_urls(monkeypatch):
    login._attempts['expired'] = {'state': 'failed', 'reason': 'old', 'login_url': '',
        'finished': time.monotonic()-901}
    assert login.state('expired') == {}
    assert not login._attempts
