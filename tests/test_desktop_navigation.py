"""A private app page must not become an unauthenticated system-browser tab."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from armada import desktop_navigation as nav, local_auth

BASE = 'http://127.0.0.1:8756/'


def backend(source=BASE):
    return NS(webview=NS(Source=source), load_url=Mock())


def popup(target, source=BASE):
    return NS(Uri=target, OriginalSourceFrameInfo=NS(Source=source), Handled=False)


def test_internal_popup_preserves_realm_and_stays_in_profile():
    view = backend()
    event = popup(BASE + 'ministers?_realm=original#agent')
    assert nav.handle_popup(view, event, BASE)
    assert event.Handled
    view.load_url.assert_called_once_with(event.Uri)


@pytest.mark.parametrize('url', [
    'https://example.com/login', 'http://127.0.0.1:8757/section-raw/page',
    'http://127.0.0.1:87560/', 'http://127.0.0.1.example.com:8756/',
    'http://127.0.0.1:8756@example.com/', 'https://127.0.0.1:8756/',
    'http://user@127.0.0.1:8756/', 'http://127.0.0.1:bad/',
    'file:///private/file', '//127.0.0.1:8756/', 'http://127.0.0.1:8756/\\evil',
])
def test_other_origins_never_receive_desktop_auth(url):
    assert nav.local_route(url, BASE) is None


@pytest.mark.parametrize('source', [
    'https://example.com/', 'http://127.0.0.1:8757/section-raw/p',
    BASE + 'section-raw/p', BASE + 'thread-file?name=evil.html',
    BASE + 'r/realm/section-raw/p', BASE + 'static/evil.html', 'about:blank',
    BASE + 'user-avatar', BASE + 'realm-icon',
])
def test_untrusted_frame_cannot_promote_a_popup_into_private_app(source):
    view, event = backend(), popup(BASE + 'switch?path=untrusted', source)
    assert nav.handle_popup(view, event, BASE) and event.Handled
    view.load_url.assert_not_called()


def test_unknown_source_is_blocked_not_sent_to_chrome():
    view = backend()
    event = NS(Uri=BASE + 'ministers', Handled=False)
    assert nav.handle_popup(view, event, BASE) and event.Handled
    view.load_url.assert_not_called()


def test_external_popup_retains_existing_provider_login_behavior():
    view, event = backend(), popup('https://example.com/oauth')
    assert not nav.handle_popup(view, event, BASE)
    assert not event.Handled
    view.load_url.assert_not_called()


def test_recover_lost_cookie_preserves_route_and_has_loop_limit(monkeypatch):
    ticks = [100]
    monkeypatch.setattr(nav.time, 'monotonic', lambda: ticks[0])
    launch = Mock(return_value=BASE + 'auth#private-fragment')
    monkeypatch.setattr(local_auth, 'browser_url', launch)
    view = backend(BASE + 'ministers?_realm=original#agent')
    assert nav.recover_document(view, NS(HttpStatusCode=401), BASE)
    launch.assert_called_once_with(BASE, '/ministers?_realm=original#agent')
    view.load_url.assert_called_once_with(launch.return_value)
    assert not nav.recover_document(view, NS(HttpStatusCode=401), BASE)
    ticks[0] += 31
    assert nav.recover_document(view, NS(HttpStatusCode=401), BASE)


@pytest.mark.parametrize('url,status', [
    (BASE, 200), (BASE, 500), (BASE, 409),
    (BASE + 'auth', 401), (BASE + 'api/run', 401),
    (BASE + 'thread-file?name=evil.html', 401),
    ('https://example.com/', 401), ('http://127.0.0.1:8757/', 401),
])
def test_recovery_never_authenticates_other_origins_or_retries_actions(url, status, monkeypatch):
    launch = Mock()
    monkeypatch.setattr(local_auth, 'browser_url', launch)
    view = backend(url)
    assert not nav.recover_document(view, NS(HttpStatusCode=status), BASE)
    launch.assert_not_called()
    view.load_url.assert_not_called()


def test_missing_private_session_leaves_recovery_page_without_loop(monkeypatch):
    monkeypatch.setattr(local_auth, 'browser_url', Mock(side_effect=OSError('unavailable')))
    view = backend()
    assert not nav.recover_document(view, NS(HttpStatusCode=401), BASE)
    assert not nav.recover_document(view, NS(HttpStatusCode=401), BASE)
    assert local_auth.browser_url.call_count == 1
    view.load_url.assert_not_called()
