"""Synthetic section confinement, including the content server and fallback."""
from pathlib import Path

import pytest

from armada import origins, serve, util
from test_content_origin import srv, _req


@pytest.mark.parametrize('relative', [
    '%2e%2e/site-private/marker.txt', '../site-private/marker.txt',
    '%2e%2e%5csite-private%5cmarker.txt', '/site-private/marker.txt',
    'C:/Windows/win.ini', 'C:relative.txt', '%5c%5cserver%5cshare%5cfile',
    'app.js:stream', 'app.js%00', 'app.js.', 'app.js%20', 'CON', './app.js',
])
@pytest.mark.parametrize('content', [True, False])
def test_assets_refuse_escape_and_windows_aliases(srv, monkeypatch, relative, content):
    sibling = Path(srv.realm) / 'shared/site-private'
    sibling.mkdir()
    (sibling / 'marker.txt').write_text('outside the asset root')
    if not content:
        monkeypatch.setattr(origins, '_content_port', None)
    port = origins.content_port() if content else srv.port
    status, _, body = _req(port, 'GET', '/section-asset/1/' + relative)
    assert status in (400, 404)
    assert 'outside the asset root' not in body


def test_assets_accept_nested_names_and_query_strings(srv):
    nested = Path(srv.realm) / 'shared/site/assets'
    nested.mkdir()
    (nested / 'safe file.js').write_text('console.log("nested");')
    status, _, body = _req(origins.content_port(), 'GET', '/section-asset/1/assets/safe%20file.js?v=1')
    assert status == 200 and body == 'console.log("nested");'


@pytest.mark.parametrize('field', ['entry', 'snapshot', 'path'])
def test_configured_section_paths_cannot_escape_their_root(srv, field):
    root = Path(srv.realm)
    base = root / 'shared/site' if field == 'entry' else root
    sibling = base.with_name(base.name + '-private')
    sibling.mkdir()
    marker = sibling / 'marker.html'
    marker.write_text('outside section root')
    cfg = util.read_json_state(root / 'realm.json')
    cfg['sections'][1] = {'name': 'Unsafe', field: str(marker)}
    if field == 'entry':
        cfg['sections'][1]['assets'] = str(base)
    util.write_json_atomic(root / 'realm.json', cfg)
    status, _, body = _req(origins.content_port(), 'GET', '/section-raw/1')
    assert status == 404 and 'outside section root' not in body


def test_snapshot_write_cannot_escape_or_report_external_file_as_success(tmp_path, monkeypatch):
    root = tmp_path / 'realm'
    root.mkdir()
    sibling = tmp_path / 'realm-private'
    sibling.mkdir()
    target = sibling / 'snapshot.html'
    target.write_text('original evidence')
    source = tmp_path / 'source.html'
    source.write_text('<html>synthetic snapshot</html>')
    section = {'snapshot': '../realm-private/snapshot.html', 'source': str(source)}
    handler = object.__new__(serve.Handler)
    handler.realm = str(root)
    handler._snapshot_refresh(section, force=True)
    assert target.read_text() == 'original evidence'
    from types import SimpleNamespace
    monkeypatch.setattr('armada.reader.read', lambda *a: SimpleNamespace(sections=[section]))
    result = handler._section_snapshot({'index': 0})
    assert result['ok'] is False


def test_local_snapshot_and_backslash_relative_path_still_work(tmp_path):
    root = tmp_path / 'realm'
    root.mkdir()
    source = tmp_path / 'source.html'
    source.write_text('<html>synthetic snapshot</html>')
    handler = object.__new__(serve.Handler)
    handler.realm = str(root)
    handler._snapshot_refresh({'snapshot': 'shared\\snapshot.html', 'source': str(source)}, force=True)
    assert (root / 'shared/snapshot.html').read_text() == source.read_text()


def test_section_refuses_link_even_when_it_points_inside_the_root(srv):
    base = Path(srv.realm) / 'shared/site'
    try:
        (base / 'linked.js').symlink_to(base / 'app.js')
    except OSError:
        pytest.skip('This Windows account cannot create symlinks')
    status, _, _ = _req(origins.content_port(), 'GET', '/section-asset/1/linked.js')
    assert status == 404


def test_section_rejects_reparse_root_without_resolving_it(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from armada.routes.dashboard import _section_path
    root = tmp_path / 'site'
    root.mkdir()
    original = Path.lstat
    monkeypatch.setattr(Path, 'lstat', lambda p: SimpleNamespace(st_file_attributes=0x400)
                        if p == root else original(p))
    # is_symlink() also uses lstat; the reparse attribute must be checked independently.
    monkeypatch.setattr(Path, 'is_symlink', lambda p: False)
    monkeypatch.setattr(Path, 'is_junction', lambda p: False, raising=False)
    with pytest.raises(ValueError, match='Linked'):
        _section_path(root, 'index.html')
