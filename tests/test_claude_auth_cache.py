"""A successful granted live probe repairs stale health metadata, never credentials."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada.engine import claude
from armada.engine.mcp import connected_names

IBKR_NAME = 'claude.ai Interactive Brokers (IBKR)'
IBKR_ID = 'claude_ai_Interactive_Brokers_IBKR'
RECOVER = claude._recover_auth_cache


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(claude, '_recover_auth_cache', RECOVER)
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    path = tmp_path / '.claude/mcp-needs-auth-cache.json'
    path.parent.mkdir()
    path.write_text(json.dumps({IBKR_NAME: {'timestamp': 1000, 'id': 'fixture'},
                               'claude.ai Gmail': {'timestamp': 1000, 'id': 'other'}}))
    credentials = path.parent / '.credentials.json'
    credentials.write_text('fixture credentials must remain byte-for-byte unchanged')
    return path


@pytest.mark.parametrize('granted', [True, False])
@pytest.mark.parametrize('health', ['√ Connected', '✓ Connected', 'Needs authentication', '✗ Failed to connect'])
def test_only_granted_live_connected_server_recovers(cache, monkeypatch, granted, health):
    engine = claude.ClaudeEngine()
    engine.allowed_mcp_ids = {IBKR_ID} if granted else set()
    monkeypatch.setattr(engine, '_launcher', lambda: ['claude'])
    monkeypatch.setattr(claude.time, 'time', lambda: 10)
    monkeypatch.setattr(claude.subprocess, 'run', lambda args, **kw: SimpleNamespace(
        returncode=0, stderr='', stdout='2.1.286' if args[-1] == '--version' else
        f'{IBKR_NAME}: https://broker.invalid - {health}\nclaude.ai Gmail: https://mail.invalid - √ Connected\n'))
    engine._mcp_args([])
    state = json.loads(cache.read_text())
    assert (IBKR_NAME not in state) is (granted and 'Connected' in health)
    assert state['claude.ai Gmail'] == {'timestamp': 1000, 'id': 'other'}
    assert (cache.parent/'.credentials.json').read_text() == 'fixture credentials must remain byte-for-byte unchanged'
    assert not list(cache.parent.glob('armada-mcp-health-*'))


def test_explicit_denial_preserves_auth_marker(cache, monkeypatch):
    engine = claude.ClaudeEngine()
    engine.allowed_mcp_ids = {IBKR_ID}
    monkeypatch.setattr(engine, '_launcher', lambda: ['claude'])
    monkeypatch.setattr(claude.subprocess, 'run', lambda args, **kw: SimpleNamespace(returncode=0,
        stderr='', stdout='2.1.286' if args[-1] == '--version' else f'{IBKR_NAME}: command - Connected\n'))
    engine._mcp_args([f'mcp__{IBKR_ID}'])
    assert IBKR_NAME in json.loads(cache.read_text())


def test_failure_written_after_probe_started_is_preserved(cache):
    state = json.loads(cache.read_text())
    state[IBKR_NAME]['timestamp'] = 11000
    cache.write_text(json.dumps(state))
    before = cache.read_bytes()
    assert not claude._recover_auth_cache({IBKR_NAME}, probe_started=10)
    assert cache.read_bytes() == before


@pytest.mark.parametrize('data', ['{', '[]', json.dumps({IBKR_NAME: {'timestamp': 1000, 'token': 'unexpected'}})])
def test_unknown_cache_formats_are_untouched(cache, data):
    cache.write_text(data)
    assert not claude._recover_auth_cache({IBKR_NAME}, probe_started=10)
    assert cache.read_text() == data


def test_concurrent_cache_update_is_preserved(cache, monkeypatch):
    original_read = Path.read_bytes
    newer = json.dumps({'new-server': {'timestamp': 15000}}).encode()
    reads = 0
    def read(path):
        nonlocal reads
        if path == cache:
            reads += 1
            if reads == 2:
                cache.write_bytes(newer)
        return original_read(path)
    monkeypatch.setattr(Path, 'read_bytes', read)
    assert not claude._recover_auth_cache({IBKR_NAME}, probe_started=10)
    assert original_read(cache) == newer
    assert not list(cache.parent.glob('armada-mcp-health-*'))


def test_custom_config_location_is_not_guessed(cache, monkeypatch):
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', 'some-other-config')
    before = cache.read_bytes()
    assert not claude._recover_auth_cache({IBKR_NAME}, probe_started=10)
    assert cache.read_bytes() == before


def test_health_parser_never_returns_urls_or_credentials():
    assert connected_names(f'{IBKR_NAME}: https://private.invalid/?secret=token - √ Connected\n'
                           'other: https://other.invalid - ✓ Failed to connect') == {IBKR_NAME}
