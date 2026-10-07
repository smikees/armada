"""Transient config access must not erase preferences during a later save."""
import json
from pathlib import Path

import pytest

from armada import appconfig, util


@pytest.mark.parametrize('raw', ['{broken', '[]', '{"theme":"dark","theme":"light"}'])
def test_damaged_config_renders_defaults_but_refuses_save(tmp_path, monkeypatch, raw):
    path = tmp_path/'config.json'
    path.write_text(raw, encoding='utf-8')
    monkeypatch.setattr(appconfig, '_path', lambda: path)
    assert appconfig.load() == {}
    with pytest.raises(util.StateError):
        appconfig.save({'theme': 'light'})
    assert path.read_text(encoding='utf-8') == raw


def test_transient_permission_error_retries_before_merging(tmp_path, monkeypatch):
    path = tmp_path/'config.json'
    path.write_text('{"theme":"dark","active_realm":"preserve"}', encoding='utf-8')
    monkeypatch.setattr(appconfig, '_path', lambda: path)
    real = Path.read_text
    attempts = []
    def flaky(p, *a, **k):
        if p == path:
            attempts.append(1)
            if len(attempts) < 3:
                raise PermissionError('temporarily busy')
        return real(p, *a, **k)
    monkeypatch.setattr(Path, 'read_text', flaky)
    monkeypatch.setattr(appconfig.time, 'sleep', lambda _: None)
    appconfig.save({'theme': 'light'})
    assert json.loads(real(path, encoding='utf-8')) == {'theme': 'light', 'active_realm': 'preserve'}
    assert len(attempts) == 3


def test_persistent_access_failure_never_overwrites_config(tmp_path, monkeypatch):
    path = tmp_path/'config.json'
    before = b'{"theme":"dark","active_realm":"preserve"}'
    path.write_bytes(before)
    monkeypatch.setattr(appconfig, '_path', lambda: path)
    real = Path.read_text
    def denied(p, *a, **k):
        if p == path:
            raise PermissionError('denied')
        return real(p, *a, **k)
    monkeypatch.setattr(Path, 'read_text', denied)
    monkeypatch.setattr(appconfig.time, 'sleep', lambda _: None)
    assert appconfig.load() == {}
    with pytest.raises(util.StateError, match='Cannot read config.json'):
        appconfig.save({'theme': 'light'})
    assert path.read_bytes() == before


def test_missing_config_can_be_created(tmp_path, monkeypatch):
    monkeypatch.setattr(appconfig, '_path', lambda: tmp_path/'config.json')
    appconfig.save({'theme': 'dark'})
    assert appconfig.load() == {'theme': 'dark'}
