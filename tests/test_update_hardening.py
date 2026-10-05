"""Startup commit, crash-safe rollback, account scope and bounded resource use."""
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
import armada_bootstrap as b
from armada import app, instance, restart, updater, util
from test_updater import inst, _release
from test_update_recovery import installation
REAL_FETCH = updater._fetch


def test_profile_override_cannot_change_instance_identity(monkeypatch, tmp_path):
    original = instance._path()
    monkeypatch.setenv('ARMADA_DATA_DIR', str(tmp_path/'other-profile'))
    assert util.data_dir() != original.parent
    assert instance._path() == original


def test_library_entry_claims_instance_before_opening_window(monkeypatch):
    from contextlib import contextmanager
    @contextmanager
    def secondary(*args): yield False
    monkeypatch.setattr(instance, 'claim', secondary)
    owned = Mock()
    monkeypatch.setattr(app, '_run_owned', owned)
    assert app.run('Other realm', 8899) == 0
    owned.assert_not_called()


def test_browser_commit_checks_exact_package(installation):
    root = installation
    b.apply(root)
    assert (root/b.HEALTH).exists()
    with pytest.raises(OSError, match='acknowledgement'):
        b.confirm_health(root, '1.0.0')
    b.confirm_health(root, '1.1.0')
    assert not (root/b.HEALTH).exists()
    with b.install_lock(root): assert b.rollback_locked(root, 'late provider outage') == ''
    assert b.version(root/'armada') == '1.1.0'


@pytest.mark.parametrize('point', ['journal', 'failed_moved', 'previous_moved'])
def test_rollback_recovers_after_each_interruption(installation, monkeypatch, point):
    root = installation
    b.apply(root)
    record, replace = b.atomic_json, b.replace
    def write(path, data):
        record(path, data)
        if point == 'journal' and data.get('rollback'): raise KeyboardInterrupt()
    def move(source, target):
        replace(source, target)
        if ((point == 'failed_moved' and source.name == 'armada') or
                (point == 'previous_moved' and source.name == 'armada.previous')):
            raise KeyboardInterrupt()
    with monkeypatch.context() as patch:
        patch.setattr(b, 'atomic_json', write)
        patch.setattr(b, 'replace', move)
        with b.install_lock(root), pytest.raises(KeyboardInterrupt):
            b.rollback_locked(root, 'Browser could not authenticate')
    with b.install_lock(root): b.recover_locked(root)
    assert b.version(root/'armada') == '1.0.0'
    assert not (root/b.HEALTH).exists()
    assert json.loads((root/b.ERROR).read_text())['error'] == 'Browser could not authenticate'
    assert json.loads((root/b.QUARANTINE).read_text())['version'] == '1.1.0'


def test_damaged_previous_version_is_not_restored(installation):
    root = installation
    b.apply(root)
    (root/'armada.previous/__init__.py').write_text('corrupt')
    with b.install_lock(root), pytest.raises(OSError, match='cannot be verified'):
        b.rollback_locked(root, 'startup failed')
    assert b.version(root/'armada') == '1.1.0'


def test_low_disk_space_keeps_current_app_and_stage_intact(inst, monkeypatch):
    monkeypatch.setattr(updater.shutil, 'disk_usage', lambda root: type('Disk', (), {'free':1})())
    result = updater.check(fetch=_release())
    assert not result['ok'] and 'disk space' in result['error']
    assert b.version(updater.PKG) == '1.0.0'
    assert not updater.STAGED.exists()


def test_new_bootstrap_requirement_uses_installer_without_fetching_zip(inst):
    result = updater.check(fetch=_release(manifest_extra={'min_bootstrap':b.PROTOCOL+1}))
    assert result['needs_installer'] and not updater.STAGED.exists()


def test_quarantined_release_is_not_staged_again(inst):
    b.atomic_json(updater.ROOT/b.QUARANTINE, {'version':'1.1.0'})
    result = updater.check(fetch=_release())
    assert not result['ok'] and 'failed startup' in result['error']
    assert not updater.STAGED.exists()


def test_work_admission_stays_paused_until_browser_commit(inst):
    assert not updater.admission_paused()
    b.atomic_json(updater.ROOT/b.HEALTH, {'version':'1.1.0'})
    assert updater.admission_paused()


def test_transient_network_error_retries_but_invalid_transport_does_not(monkeypatch):
    import urllib.error
    attempts = []
    def failure(*args, **kw):
        attempts.append(1)
        raise urllib.error.HTTPError('https://example.test', 503, 'Busy', {}, None)
    monkeypatch.setattr(updater.urllib.request, 'urlopen', failure)
    monkeypatch.setattr(updater.time, 'sleep', lambda n: None)
    with pytest.raises(urllib.error.HTTPError): REAL_FETCH('https://example.test', 1024)
    assert len(attempts) == 3
    with pytest.raises(ValueError): REAL_FETCH('http://example.test', 1024)
    assert len(attempts) == 3


def test_restart_state_discards_malformed_bounds_and_auth_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(util, 'data_dir', lambda:tmp_path)
    (tmp_path/'desktop-state.json').write_text(json.dumps({'width':'bad','height':700,'route':'/settings'}))
    assert app.window_state() == {'height':700,'route':'/settings'}


def test_cleanup_retains_current_monitor_and_skips_linked_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(util, 'data_dir', lambda:tmp_path)
    for i in range(8):
        folder = tmp_path/'restart'/str(i)
        folder.mkdir(parents=True)
        os.utime(folder, (100+i,100+i))
    util.write_json_atomic(tmp_path/'restart-status.json', {'nonce':'0','monitor_pid':os.getpid()})
    restart.cleanup(keep=2, days=999999)
    assert {p.name for p in (tmp_path/'restart').iterdir()} == {'0','6','7'}
