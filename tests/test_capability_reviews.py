"""Durable review ownership, verified-version reuse, and fast capability actions."""
import json
import threading
import time
from unittest.mock import Mock

import pytest

from armada import capability_reviews as reviews, catalogue, capabilities, reader, util
from armada.routes.catalogue import CatalogueRoutes
from armada.routes.caps import CapabilityRoutes


@pytest.fixture
def realm(tmp_path, monkeypatch):
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path / 'data')
    root = tmp_path / 'realm'
    util.write_json_atomic(root / 'realm.json', {'name': 'Test', 'toolkit': {
        'skills': [{'id': 'notes', 'name': 'Notes'}],
        'connectors': [{'id': 'drive', 'name': 'Drive'}]}})
    util.write_json_atomic(root / 'agents' / 'reviewer' / 'agent.json', {'id': 'reviewer', 'display': 'Reviewer', 'model': 'gpt-6.1-sol'})
    monkeypatch.setattr(reviews, '_version', lambda url, key: ('abc123', url + '/pinned'))
    monkeypatch.setattr(catalogue, 'review_url', Mock(return_value={'ok': True, 'name': 'Notes', 'kind': 'skills', 'runs': 'reads'}))
    return root


def finish(root):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with reviews._lock:
            active = any(t[0] == str(reviews._directory(root)) for t in reviews._active)
        if not active:
            return reviews.recent(root)[0]
        time.sleep(.01)
    pytest.fail('Review worker did not finish')


def test_survives_navigation_deduplicates_and_restores_from_disk(realm, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def review(url):
        entered.set()
        assert release.wait(3)
        return {'ok': True, 'name': 'Notes'}
    mock = Mock(side_effect=review)
    monkeypatch.setattr(catalogue, 'review_url', mock)
    rid = reviews.start(realm, 'https://github.com/example/notes')
    try:
        assert entered.wait(2)
        assert reviews.start(realm, 'https://github.com/example/notes') == rid
        assert reviews.recent(realm)[0]['state'] == 'running'
        assert reviews.recent(realm.parent / 'other') == []
    finally:
        release.set()
    row = finish(realm)
    assert row['state'] == 'done'
    assert mock.call_count == 1
    assert json.loads((reviews._directory(realm) / (rid + '.json')).read_text())['result']['name'] == 'Notes'
    assert reviews.recent(realm)[0] == row


def test_only_same_verified_version_reuses_review(realm, monkeypatch):
    url = 'https://github.com/example/notes'
    reviews.start(realm, url); finish(realm)
    reviews.start(realm, url)
    assert finish(realm)['cached']
    assert catalogue.review_url.call_count == 1
    monkeypatch.setattr(reviews, '_version', lambda url, key: ('changed', url))
    reviews.start(realm, url)
    assert not finish(realm)['cached']
    assert catalogue.review_url.call_count == 2
    monkeypatch.setattr(reviews, '_version', lambda url, key: ('', url))
    reviews.start(realm, url); finish(realm)
    reviews.start(realm, url); finish(realm)
    assert catalogue.review_url.call_count == 4


def test_policy_change_invalidates_cache(realm, monkeypatch):
    reviews.start(realm, 'https://example.com/skill'); finish(realm)
    monkeypatch.setattr(reviews.sysskills, 'get_system_skill', lambda name: {'body': 'Changed protocol'})
    reviews.start(realm, 'https://example.com/skill'); finish(realm)
    assert catalogue.review_url.call_count == 2


def test_failed_reviews_can_retry_and_restart_does_not_rerun(realm):
    catalogue.review_url.return_value = {'ok': False, 'error': 'Provider unavailable'}
    rid = reviews.start(realm, 'https://example.com/skill')
    assert finish(realm)['state'] == 'error'
    catalogue.review_url.return_value = {'ok': True, 'name': 'Notes'}
    reviews.start(realm, 'https://example.com/skill')
    row = finish(realm)
    assert row['state'] == 'done'
    row['state'] = 'running'
    util.write_json_atomic(reviews._directory(realm) / (rid + '.json'), row)
    assert reviews.recent(realm)[0]['stage'] == 'Review interrupted'
    assert catalogue.review_url.call_count == 2


def test_local_fingerprint_changes_for_script_edits(tmp_path, monkeypatch):
    folder = tmp_path / 'skill';folder.mkdir()
    (folder / 'SKILL.md').write_text('Instructions')
    script = folder / 'script.py';script.write_text('print(1)')
    monkeypatch.setattr(catalogue, 'find', lambda key: {'install': {'path': str(folder)}})
    first = reviews._version('', 'local')[0]
    script.write_text('print(2)')
    assert reviews._version('', 'local')[0] != first


def test_github_revision_is_pinned_and_host_is_not_spoofable(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps({'sha': 'a' * 40}).encode()
    mock = Mock(return_value=Response())
    monkeypatch.setattr(reviews, 'urlopen', mock)
    revision, target = reviews._version('https://github.com/example/notes', '')
    assert revision == 'a' * 40 and target.endswith('/tree/' + revision)
    assert mock.call_args.args[0].full_url == 'https://api.github.com/repos/example/notes/commits/HEAD'
    for url in ('https://github.com.evil/x/y', 'https://evil@github.com/x/y', 'https://github.com/x', 'please find https://github.com/a/b'):
        assert not reviews.github_repo(url)


def test_github_search_routes_to_review_without_searching(realm, monkeypatch):
    handler = CatalogueRoutes();handler.realm = realm
    monkeypatch.setattr(reviews, 'start', Mock(return_value='review-id'))
    from armada import smart_search
    monkeypatch.setattr(smart_search, 'start', Mock(side_effect=AssertionError('Must not search')))
    assert handler._smart_search({'q': 'https://github.com/example/notes', 'sources': []}) == {'ok': True, 'review_id': 'review-id'}


def test_inline_grant_and_revoke_do_not_probe_providers(realm, monkeypatch):
    from armada import connector_runtime
    from armada.webui import capabilities as ui
    monkeypatch.setattr(ui, '_portrait', lambda *args: '<img src="/avatar/reviewer">')
    monkeypatch.setattr(connector_runtime, 'codex_inventory', Mock(side_effect=AssertionError('No CLI on grant')))
    handler = CapabilityRoutes();handler.realm = realm
    body = {'agent': 'reviewer', 'capability': 'drive', 'inline': True}
    result = handler._cap_grant(body)
    assert result['ok'] and 'reviewer' in result['agents'] and 'Reviewer' in result['grants']
    assert '_realm=' in result['grants'], 'new portrait URLs must stay bound to their realm'
    assert capabilities.may_use(realm, 'reviewer', 'drive')
    result = handler._cap_revoke(body)
    assert result['ok'] and 'reviewer' not in result['agents']


def test_page_shell_does_not_render_inventory(realm, monkeypatch):
    from armada.routes.realm import RealmRoutes
    from armada.webui import capabilities as ui
    monkeypatch.setattr(ui, '_realm_skills', Mock(side_effect=AssertionError('Must load asynchronously')))
    handler = RealmRoutes();handler.realm = realm;handler._dark = lambda: False
    handler._send = Mock()
    handler._get_realm_page('skills')
    html = handler._send.call_args.args[1]
    assert 'Loading capabilities' in html and 'capload.js' in html


def test_render_cache_is_request_local(realm, monkeypatch):
    from armada.webui.capabilities import _realm_skills
    original = capabilities.usable
    mock = Mock(wraps=original);monkeypatch.setattr(capabilities, 'usable', mock)
    snapshot = reader.read(realm)
    mock.reset_mock()
    _realm_skills(snapshot, realm)
    assert mock.call_count == 2  # once for the roster, once shared by every capability card
    capabilities.grant(realm, 'reviewer', 'notes')
    snapshot = reader.read(realm)
    mock.reset_mock()
    html = _realm_skills(snapshot, realm)
    assert mock.call_count == 2
    assert 'data-cap="notes" data-agents="reviewer"' in html


def test_same_source_reuses_report_across_search_and_link_entry_points(realm):
    url = 'https://github.com/example/notes'
    reviews.start(realm, url, 'catalogue/notes'); finish(realm)
    reviews.start(realm, url)
    assert finish(realm)['cached']
    assert catalogue.review_url.call_count == 1


def test_app_version_and_install_path_do_not_invalidate_unchanged_protocol(realm, monkeypatch):
    monkeypatch.setattr(reviews.sysskills, 'get_system_skill', lambda name: {'body': 'Same protocol', 'version': '1', 'path': 'old'})
    reviews.start(realm, 'https://example.com/skill'); finish(realm)
    monkeypatch.setattr(reviews.sysskills, 'get_system_skill', lambda name: {'body': 'Same protocol', 'version': '2', 'path': 'new'})
    reviews.start(realm, 'https://example.com/skill')
    assert finish(realm)['cached']
    assert catalogue.review_url.call_count == 1
