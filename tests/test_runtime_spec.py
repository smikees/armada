"""Keep the signed package requirement aligned with the installer's security baseline."""
import hashlib
import io
import json
from types import SimpleNamespace

import pytest

from armada import ed25519, runtime_spec, updater
from tools import build_installer, build_release
from tools import upgrade_probe


def test_patch_baseline_does_not_depend_on_the_build_hosts_python(monkeypatch):
    first = updater.runtime_tag('a==1')
    assert first.startswith('py' + runtime_spec.PYTHON_VERSION + '-')
    monkeypatch.setattr(runtime_spec, 'PYTHON_VERSION', '3.14.11')
    assert updater.runtime_tag('a==1').startswith('py3.14.11-')
    assert updater.runtime_tag('a==1') != first


def test_native_launcher_change_requires_a_full_installer(monkeypatch):
    first = updater.runtime_tag('a==1')
    monkeypatch.setattr(runtime_spec, 'LAUNCHER_PROTOCOL', runtime_spec.LAUNCHER_PROTOCOL + 1)
    assert updater.runtime_tag('a==1') != first


def test_signed_manifest_and_installer_share_the_full_patch_baseline(tmp_path, monkeypatch):
    (tmp_path/'armada').mkdir()
    (tmp_path/'armada/__init__.py').write_text('__version__ = "1.1.0"\n')
    (tmp_path/'requirements.txt').write_text('example==1\n')
    seed = bytes(range(32))
    key = tmp_path/'synthetic-key.txt'
    key.write_text(seed.hex())
    monkeypatch.setattr(updater, 'PUBLIC_KEY', ed25519.public_key(seed))
    monkeypatch.setattr(build_release, 'ROOT', tmp_path)
    def git(*args):
        if args[0] == 'ls-files': return 'armada/__init__.py\n'
        if args[0] == 'rev-parse': return 'a'*40
        return ''
    monkeypatch.setattr(build_release, '_git', git)
    folder = build_release.build(key, tmp_path/'dist')
    manifest = updater.verified_manifest((folder/updater.MANIFEST).read_bytes(),
                                        (folder/updater.SIGNATURE).read_bytes())
    assert build_installer.PY_VERSION == runtime_spec.PYTHON_VERSION
    assert manifest['runtime'] == updater.runtime_tag('example==1', build_installer.PY_VERSION)
    assert manifest['runtime'] != updater.runtime_tag('example==1', runtime_spec.PYTHON_MINOR)


def test_corrupt_cached_runtime_is_refused_without_replacing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(build_installer, 'CACHE', tmp_path)
    bad = tmp_path/'runtime.zip'
    bad.write_bytes(b'corrupt archive')
    monkeypatch.setattr(build_installer.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('unexpected network'))
    with pytest.raises(SystemExit, match='refusing'):
        build_installer._pinned_download('https://example.invalid/runtime.zip', '0'*64)
    assert bad.read_bytes() == b'corrupt archive'


def test_unverified_download_never_becomes_a_cached_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(build_installer, 'CACHE', tmp_path)
    monkeypatch.setattr(build_installer.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(b'wrong bytes'))
    with pytest.raises(SystemExit, match='refusing'):
        build_installer._pinned_download('https://example.invalid/runtime.zip', hashlib.sha256(b'correct bytes').hexdigest())
    assert list(tmp_path.iterdir()) == []


def test_runtime_boundary_probe_restores_installed_marker_after_failure(tmp_path, monkeypatch):
    root = tmp_path/'install'
    (root/'armada').mkdir(parents=True)
    (root/'armada/__init__.py').write_text('__version__ = "1.0.0"')
    marker = root/'installed.json'
    original = b'{"runtime":"new-runtime","python":"3.14.10"}'
    marker.write_bytes(original)
    def failed(command, **kwargs):
        assert json.loads(marker.read_text())['runtime'] == 'old-runtime'
        assert kwargs['env']['HOME'] == str(tmp_path/'boundary-home')
        return SimpleNamespace(returncode=1, stderr='Synthetic boundary failure')
    monkeypatch.setattr(upgrade_probe.subprocess, 'run', failed)
    with pytest.raises(RuntimeError, match='Synthetic boundary failure'):
        upgrade_probe.verify_runtime_boundary(root, {'runtime':'old-runtime'},
                                               {'runtime':'new-runtime'}, tmp_path/'assets')
    assert marker.read_bytes() == original
