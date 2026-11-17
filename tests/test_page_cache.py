"""Presentation reuse must expire, stay realm-bound and yield to writes/reloads."""
from unittest.mock import Mock

import pytest

from armada import page_cache


@pytest.fixture(autouse=True)
def empty_cache():
    page_cache.invalidate()
    yield
    page_cache.invalidate()


def test_revisit_reuses_only_the_matching_realm_and_page(tmp_path):
    build = Mock(return_value='<p>Saved inventory</p>')
    assert page_cache.render(tmp_path, 'skills', build) == build.return_value
    assert page_cache.render(tmp_path, 'skills', build) == build.return_value
    assert build.call_count == 1
    assert page_cache.get(tmp_path/'other', 'skills') is None
    assert page_cache.get(tmp_path, 'artefacts') is None


def test_expiry_is_not_extended_by_reads(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(page_cache.time, 'monotonic', lambda: now[0])
    page_cache.render(tmp_path, 'skills', lambda: 'old')
    now[0] += 29
    assert page_cache.get(tmp_path, 'skills') == 'old'
    now[0] += 2
    assert page_cache.get(tmp_path, 'skills') is None
    assert page_cache.render(tmp_path, 'skills', lambda: 'new') == 'new'


def test_mutation_fences_inflight_render(tmp_path):
    def racing_render():
        page_cache.invalidate()
        return 'earlier snapshot'
    page_cache.render(tmp_path, 'skills', racing_render)
    assert page_cache.get(tmp_path, 'skills') is None


def test_bounds_and_failed_render(tmp_path, monkeypatch):
    monkeypatch.setattr(page_cache, 'MAX_ENTRIES', 2)
    monkeypatch.setattr(page_cache, 'MAX_CHARS', 12)
    for key in ('a', 'b', 'c'):
        page_cache.render(tmp_path, key, lambda: '12345')
    assert page_cache.get(tmp_path, 'a') is None
    assert page_cache.get(tmp_path, 'b') == '12345'
    page_cache.render(tmp_path, 'large', lambda: 'x'*13)
    assert page_cache.get(tmp_path, 'large') is None
    with pytest.raises(ValueError):
        page_cache.render(tmp_path, 'bad', lambda: int('bad'))
    assert page_cache.get(tmp_path, 'bad') is None


@pytest.mark.parametrize('page', ['skills', 'artefacts'])
def test_cold_page_is_fast_frame_warm_page_includes_content_and_reload_bypasses(tmp_path, monkeypatch, page):
    from armada.routes.realm import RealmRoutes
    from armada.webui import capabilities, agentcommon
    from tests.golden_support import build_fixture
    realm = build_fixture(tmp_path/'realm')
    build = Mock(return_value='<p id="synthetic-list">Content</p>')
    monkeypatch.setattr(capabilities, 'content', build)
    monkeypatch.setattr(agentcommon, '_realm_artefacts', build)
    handler = RealmRoutes();handler.realm = realm;handler._dark = lambda: False
    handler.headers = {};handler._send = Mock()
    handler._get_realm_page(page)
    cold = handler._send.call_args.args[1]
    assert 'page_content.js' in cold and 'synthetic-list' not in cold
    assert build.call_count == 0
    handler._get_list_content(page)
    assert build.call_count == 1
    handler._get_realm_page(page)
    warm = handler._send.call_args.args[1]
    assert 'synthetic-list' in warm and 'page_content.js' not in warm
    assert build.call_count == 1
    # The title, subtitle, actions and (Capabilities) tabs are not in the payload.
    assert cold.count('class="mc-list-heading"') == warm.count('class="mc-list-heading"') == 1
    handler.headers = {'Cache-Control': 'max-age=0'}
    handler._get_realm_page(page)
    assert 'page_content.js' in handler._send.call_args.args[1]
    handler._get_list_content(page)
    assert build.call_count == 2


def test_http_auth_and_writes_do_not_reuse_cached_presentations(tmp_path, monkeypatch):
    import http.client
    import json
    import threading
    from armada import local_auth, serve
    from tests.golden_support import build_fixture
    root = build_fixture(tmp_path/'realm')
    class Fixture(serve.Handler):
        realm = root
        def _save_user(self, body):
            return {'ok': True}
    monkeypatch.setattr(local_auth.util, 'data_dir', lambda: tmp_path/'private')
    server = serve._Server(('127.0.0.1', 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    def request(path, method='GET', auth=True):
        from armada.request_context import RealmContext
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
        headers = {'Authorization': 'Bearer '+server.auth.token} if auth else {}
        headers['Content-Type'] = 'application/json'
        headers['X-Armada-Realm'] = RealmContext.capture(root).realm_id
        conn.request(method, path, '{}' if method == 'POST' else None, headers)
        response = conn.getresponse();body = response.read();conn.close()
        return response.status, body
    try:
        page_cache.render(root, 'artefacts', lambda: '<p>Earlier contents</p>')
        assert request('/api/artefacts-content', auth=False)[0] == 401
        assert request('/api/artefacts-content')[1] == b'<p>Earlier contents</p>'
        assert json.loads(request('/api/save-user', 'POST')[1])['ok']
        assert page_cache.get(root, 'artefacts') is None
    finally:
        server.shutdown();server.server_close()
