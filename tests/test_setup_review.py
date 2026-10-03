"""Setup review must isolate Armada state while observing the real vendor sign-ins."""
from pathlib import Path

import pytest

from armada import util
from tools.review_setup import isolate_armada_state


def test_review_preserves_windows_and_vendor_homes(monkeypatch, tmp_path):
    homes = {key: str(tmp_path / key) for key in
             ('HOME', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR')}
    for key, value in homes.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('ARMADA_DATA_DIR', '')
    monkeypatch.setenv('ARMADA_MUTE_NOTIFICATIONS', '')
    home_before = Path.home()
    review = tmp_path / 'review'
    isolate_armada_state(review)
    import os
    assert {key: os.environ[key] for key in homes} == homes
    assert Path.home() == home_before
    assert util.data_dir() == review / '.armada'
    assert os.environ['ARMADA_MUTE_NOTIFICATIONS'] == '1'


def test_review_data_override_never_migrates_the_real_home(monkeypatch, tmp_path):
    real_home = tmp_path / 'windows-home'
    legacy = real_home / '.matcap'
    legacy.mkdir(parents=True)
    sentinel = legacy / 'config.json'
    sentinel.write_text('{"root":"live-realm"}')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: real_home))
    review = tmp_path / 'review' / '.armada'
    monkeypatch.setenv('ARMADA_DATA_DIR', str(review))
    assert util.data_dir() == review
    assert sentinel.read_text() == '{"root":"live-realm"}'
    assert not (real_home / '.armada').exists()


def test_relative_data_override_fails_without_falling_back(monkeypatch):
    monkeypatch.setenv('ARMADA_DATA_DIR', 'relative-profile')
    with pytest.raises(ValueError, match='absolute'):
        util.data_dir()
