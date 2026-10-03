import threading
import time
from unittest.mock import Mock

import pytest

from armada import provider_limits as limits


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(limits, '_entries', {})
    monkeypatch.setattr(limits.providers, 'allowed', lambda provider: True)
    monkeypatch.setattr(limits.providers, 'connected', lambda: ['claude', 'codex', 'gemini'])


def finish(provider, realm=None):
    key = (provider, str(getattr(realm, 'root', realm)) if provider == 'claude' else '')
    limits._entries[key].worker.join(1)
    return limits.read(provider, realm)


def test_independent_checks_cache_zero_and_missing_period(monkeypatch):
    release = threading.Event()
    calls = []
    def probe(provider, realm):
        calls.append(provider)
        if provider == 'claude':
            release.wait(2)
        return {'available': True, 'weekly': {'pct': 0}}
    monkeypatch.setattr(limits, '_probe', probe)
    try:
        assert limits.read('claude')['pending']
        limits.read('gemini')
        data = finish('gemini')
        assert data['weekly']['pct'] == 0 and 'session' not in data
        assert not data.get('pending')
        for _ in range(5):
            limits.read('gemini')
        assert calls.count('gemini') == 1
        assert limits.read('claude')['pending']
    finally:
        release.set()
        finish('claude')


@pytest.mark.parametrize('result', [None, {}, {'available': 'yes'}, RuntimeError('exact CLI failure')])
def test_invalid_or_failed_probe_is_terminal(monkeypatch, result):
    def probe(*args):
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(limits, '_probe', probe)
    limits.read('gemini')
    data = finish('gemini')
    assert data['available'] is False and not data.get('pending')
    assert data['connected'] is True  # Quota failure does not mean signed out.
    assert data['reason'] == 'error'
    assert 'failure' in data['message'] if isinstance(result, Exception) else 'malformed' in data['message']


def test_timeout_is_terminal_and_late_result_cannot_overwrite_it(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(limits, 'DEADLINE', .01)
    def probe(*args):
        release.wait(2)
        return {'available': True, 'weekly': {'pct': 42}}
    monkeypatch.setattr(limits, '_probe', probe)
    try:
        limits.read('gemini')
        time.sleep(.025)
        data = limits.read('gemini')
        assert data['reason'] == 'timeout' and not data.get('pending')
        worker = limits._entries[('gemini', '')].worker
        limits.read('gemini', force=True)
        assert limits._entries[('gemini', '')].worker is worker  # No duplicate stuck workers.
    finally:
        release.set()
        worker.join(1)
    assert limits.read('gemini')['reason'] == 'timeout'


def test_failed_refresh_retains_last_good_and_disconnect_wins(monkeypatch):
    probe = Mock(return_value={'available': True, 'weekly': {'pct': 21}})
    monkeypatch.setattr(limits, '_probe', probe)
    limits.read('codex')
    assert finish('codex')['weekly']['pct'] == 21
    probe.side_effect = RuntimeError('network unavailable')
    limits.read('codex', force=True)
    data = finish('codex')
    assert data['stale'] and data['weekly']['pct'] == 21
    assert data['message'] == 'network unavailable'
    monkeypatch.setattr(limits.providers, 'allowed', lambda p: False)
    data = limits.read('codex')
    assert data['reason'] == 'disconnected' and not data['connected'] and not data['available']
