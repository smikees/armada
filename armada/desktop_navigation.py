"""Keep private desktop navigation inside its authenticated WebView2 profile.

The default pywebview popup handler opens *every* URL in the system browser.
That browser does not share the desktop's local-session cookie. Never pass a
bootstrap credential to it, or promote a popup from an untrusted content frame.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

log = logging.getLogger(__name__)


def local_route(value, base):
    """Return a route only for the exact app origin, without URL credentials."""
    try:
        url, origin = urlsplit(str(value)), urlsplit(str(base))
        if (url.scheme != 'http' or origin.scheme != 'http'
                or origin.hostname != '127.0.0.1'
                or (url.hostname, url.port) != (origin.hostname, origin.port)
                or url.username is not None or url.password is not None
                or '\\' in str(value) or any(ord(c) < 32 for c in str(value))):
            return None
        path = url.path or '/'
        if path.startswith('//'):
            return None
        return path + ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')
    except (ValueError, TypeError):
        return None


def trusted_page(route):
    """Exclude same-origin fallback documents that are deliberately sandboxed."""
    if route is None:
        return False
    path = urlsplit(route).path
    if path in ('/user-avatar', '/realm-icon'):
        return False
    return not path.startswith(('/api/', '/static/', '/r/', '/section-raw/',
                               '/section-asset/', '/thread-file', '/avatar/'))


def handle_popup(backend, args, base):
    """Return True when a local popup was handled (including refused frames)."""
    target = str(args.Uri)
    route = local_route(target, base)
    if route is None:
        return False  # Provider sign-in and ordinary external links keep their behavior.
    args.Handled = True
    try:
        source = local_route(str(args.OriginalSourceFrameInfo.Source), base)
    except Exception:
        log.debug('WebView2 did not identify the popup source frame', exc_info=True)
        source = None  # Older runtimes cannot prove a frame's origin: fail closed.
    top = local_route(str(backend.webview.Source), base)
    if not trusted_page(source) or not trusted_page(top):
        log.warning('Blocked local popup from an untrusted or unidentified frame')
        return True
    # Already inside the owner's browser profile; ordinary navigation preserves
    # its cookie, realm query and history. No credential crosses to Chrome.
    log.info('Kept desktop popup inside ARMADA (path=%s; user_gesture=%s)',
             urlsplit(route).path, bool(getattr(args, 'IsUserInitiated', False)))
    backend.load_url(target)
    return True


def recover_document(backend, args, base):
    """Repair a lost desktop cookie on a document GET, never replay an API action."""
    if args.HttpStatusCode != 401:
        return False
    route = local_route(str(backend.webview.Source), base)
    if not trusted_page(route) or urlsplit(route).path == '/auth':
        return False
    now = time.monotonic()
    previous = getattr(backend, '_armada_auth_retry', None)
    if previous is not None and now - previous < 30:
        return False  # A broken bootstrap must not make a reload loop.
    backend._armada_auth_retry = now
    from .local_auth import browser_url
    try:
        destination = browser_url(base, route)
        log.info('Restoring desktop session for path=%s', urlsplit(route).path)
        backend.load_url(destination)
        return True
    except Exception:
        log.warning('Could not restore desktop session; leaving recovery page visible')
        return False


def install(base_url):
    """Install before creating any window; base_url follows the bound server port."""
    from webview.platforms import edgechromium
    cls = edgechromium.EdgeChrome
    cls._armada_base_url = staticmethod(base_url)
    if getattr(cls, '_armada_navigation_installed', False):
        return
    popup = cls.on_new_window_request
    completed = cls.on_navigation_completed

    def on_popup(self, sender, args):
        if not handle_popup(self, args, self._armada_base_url()):
            popup(self, sender, args)

    def on_completed(self, sender, args):
        completed(self, sender, args)
        try:
            recover_document(self, args, self._armada_base_url())
        except Exception:
            log.warning('Desktop session recovery check failed', exc_info=True)

    cls.on_new_window_request = on_popup
    cls.on_navigation_completed = on_completed
    cls._armada_navigation_installed = True
