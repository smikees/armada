"""Recover Windows presentation independently of execution and server ownership.

Native UI callbacks own the controller. No recovery action replays a POST or starts
an engine/scheduler. The same Form/HWND remains; failed WebView controls are disposed.
"""
from __future__ import annotations

from collections import deque
import json
import logging
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from .desktop_navigation import local_route
from .desktop_operations import ScriptCalls

log = logging.getLogger(__name__)
DISPLAY_PATHS = {"/", "/index.html", "/settings", "/alexander", "/approvals", "/docs", "/setup",
                 "/new/realm", "/new/agent", "/new/job", "/add-section", "/embed/thread", "/thread-window",
                 "/ministers", "/goals", "/jobs", "/memory", "/skills", "/artefacts", "/inbox"}
DISPLAY_PREFIXES = ("/agent/", "/job/", "/section/", "/edit-section/", "/docs/")
FAILURES = {"BrowserProcessExited", "RenderProcessExited", "RenderProcessUnresponsive"}
HEARTBEAT = """(()=>{if(!window.__armadaNativeDrafts){window.__armadaNativeDrafts=true;
window.dispatchEvent(new Event('armada-native-drafts-ready'));}
const style=getComputedStyle(document.body||document.documentElement);return {route:location.pathname+location.search,
realm:document.querySelector('meta[name="armada-realm"]')?.content||'',
background:style.backgroundColor,foreground:style.color,
ready:document.readyState==='complete'&&!!document.querySelector('link[href*="/static/brand.css"]')
&&typeof window.mcFontSize?.get==='function'};})()"""


def recovery_route(value, base):
    route = local_route(value, base)
    if route is None:
        return None
    path = urlsplit(route).path
    if path not in DISPLAY_PATHS and not path.startswith(DISPLAY_PREFIXES):
        return None
    return route.split('#', 1)[0]


def bound_route(route, realm):
    """Keep a recovered view bound to its last observed realm; never switch realms."""
    if not isinstance(realm, str) or not realm or len(realm) > 100:
        return route
    url = urlsplit(route)
    query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k != '_realm']
    return url.path + '?' + urlencode([*query, ('_realm', realm)])


def initial_route(value, base):
    """Retain the intended display route before the first page heartbeat.

    The local authentication bootstrap carries its destination in the fragment.
    Only its validated display destination is retained, never its session token.
    """
    route = recovery_route(value, base)
    if route:
        return route
    if local_route(value, base) is not None and urlsplit(value).path == '/auth':
        destination = dict(parse_qsl(urlsplit(value).fragment)).get('next', '/')
        return recovery_route(base.rstrip('/') + destination, base) or '/'
    return '/'


class RecoveryBudget:
    def __init__(self, *, limit=2, period=120):
        self.limit, self.period = limit, period
        self.attempts = deque()

    def allow(self, now):
        while self.attempts and now - self.attempts[0] >= self.period:
            self.attempts.popleft()
        if len(self.attempts) >= self.limit:
            return False
        self.attempts.append(now)
        return True


class Presentation:
    """One bounded recovery owner per native Form, including detached windows."""
    heartbeat_timeout = 12
    recovery_timeout = 25

    def __init__(self, backend, base_url, quitting):
        from System.Windows.Forms import Timer
        self.window, self.form = backend.pywebview_window, backend.form
        self.base_url, self.quitting = base_url, quitting
        self.backend = backend
        self.route = initial_route(str(self.window.real_url or ''), base_url())
        self.state = 'healthy'
        self.generation = 0
        self.recoveries = 0
        self.budget = RecoveryBudget()
        self.panel = self.label = self.heading = self.retry = None
        self.fonts = []
        self.heartbeat = self.auth = None
        self.bindings = None
        self.drafts = {}
        self.restoring_drafts = False
        self.next_heartbeat = 0
        self.last_tick = time.monotonic()
        self.deadline = 0
        self.calls = ScriptCalls(self.post, self.start_script)
        self.timer = Timer()
        self.timer.Interval = 100
        self.timer.Tick += self.tick
        self.form.FormClosed += self.closed
        self.form._armada_presentation = self
        self.timer.Start()

    def post(self, callback):
        from System import Action
        self.form.BeginInvoke(Action(callback))

    def start_script(self, script):
        return self.backend.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
            'Runtime.evaluate', json.dumps({'expression': script, 'awaitPromise': True, 'returnByValue': True}))

    def bind(self, backend, args):
        if self.state == 'closed' or self.quitting():
            return
        self.backend = backend
        if not args.IsSuccess:
            self.failed('The browser view could not initialize.')
            return
        self.unbind()
        core = backend.webview.CoreWebView2
        environment, pid = core.Environment, int(core.BrowserProcessId)
        def process_failed(sender, event):
            if backend is self.backend:
                self.process_failed(str(event.ProcessFailedKind))
        def browser_exited(sender, event):
            if backend is self.backend and int(event.BrowserProcessId) == pid:
                self.process_failed('BrowserProcessExited')
        def draft_received(sender, event):
            if backend is self.backend and self.state == 'healthy':
                try:
                    if recovery_route(str(event.Source), self.base_url()):
                        self.remember_draft(json.loads(str(event.WebMessageAsJson)))
                except Exception:
                    log.debug('Native draft message unavailable', exc_info=True)
        def navigating(sender, event):
            if backend is self.backend and local_route(str(event.Uri), self.base_url()):
                if urlsplit(str(event.Uri)).path == '/auth':
                    self.route = initial_route(str(event.Uri), self.base_url())
        core.ProcessFailed += process_failed
        environment.BrowserProcessExited += browser_exited
        core.WebMessageReceived += draft_received
        core.NavigationStarting += navigating
        self.bindings = (core, process_failed, environment, browser_exited, draft_received, navigating)
        if self.panel is not None:
            self.panel.BringToFront()

    def unbind(self):
        if self.bindings is None:
            return
        core, failed, environment, exited, draft, navigating = self.bindings
        self.bindings = None
        try:
            core.ProcessFailed -= failed
            core.WebMessageReceived -= draft
            core.NavigationStarting -= navigating
        except Exception:
            log.debug('Failed browser no longer exposes its event subscription', exc_info=True)
        try:
            environment.BrowserProcessExited -= exited
        except Exception:
            log.debug('Browser environment event was already disconnected', exc_info=True)

    def remember_draft(self, message):
        """Two bounded unsent composer values, in memory only; never arbitrary fields."""
        if not isinstance(message, dict) or message.get('type') != 'armada-unsent-draft':
            return
        kind, key, value = message.get('kind'), message.get('key'), message.get('value')
        prefixes = {'chat': 'armada-draft:', 'alexander': 'armada-alex-draft:'}
        if (not isinstance(kind, str) or kind not in prefixes or not isinstance(key, str) or len(key) > 2048
                or not key.startswith(prefixes[kind]) or not isinstance(value, str)):
            return
        self.drafts[kind] = {'key': key, 'value': value[:65536 if kind == 'chat' else 6000]}

    def draft_script(self):
        return "(()=>{const drafts=" + json.dumps(self.drafts) + ";" + """
for(const [kind,draft] of Object.entries(drafts)) {
  const restore=kind==='chat'?window.mcRestoreChatDraft:window.mcRestoreAlexanderDraft;
  if(typeof restore==='function')restore(draft.key,draft.value);
}return true;})()"""

    def process_failed(self, kind):
        if self.state == 'closed' or self.quitting():
            return
        if kind in FAILURES:
            self.recover(kind)
        else:
            log.warning('WebView2 reported a subordinate process failure: %s', kind)

    def show_panel(self, message, *, retry=False):
        from System.Drawing import Color, Font, FontStyle, Size
        from System.Windows.Forms import Button, DockStyle, FlowLayoutPanel, Label, Padding, Panel
        if self.panel is None:
            from .startup_splash import _dark
            dark = _dark()
            panel = self.panel = Panel()
            panel.Dock = DockStyle.Fill
            # Companion Forms have a clipped portrait/header region. Keep the
            # recovery controls inside their opaque panel, including at 400px.
            panel.Padding = Padding(64, 112, 24, 24) if self.window.frameless else Padding(40)
            panel.Font = Font('Segoe UI', 11)
            self.fonts.append(panel.Font)
            panel.BackColor = Color.FromArgb(30, 32, 36) if dark else Color.White
            panel.ForeColor = Color.White if dark else Color.FromArgb(30, 32, 36)
            panel.AccessibleName = 'ARMADA view recovery'
            heading = self.heading = Label()
            heading.Dock = DockStyle.Top
            heading.Height = 52
            heading.Font = Font('Segoe UI', 18, FontStyle.Bold)
            self.fonts.append(heading.Font)
            label = self.label = Label()
            label.Dock = DockStyle.Top
            label.Height = 165 if self.window.frameless else 110
            buttons = FlowLayoutPanel()
            buttons.Dock = DockStyle.Top
            buttons.Height = 65
            self.retry = Button()
            self.retry.Text = 'Restore view'
            self.retry.AutoSize = True
            self.retry.MinimumSize = Size(120, 36)
            self.retry.Click += lambda *_: self.recover('owner retry', manual=True)
            close = Button()
            close.Text = 'Close window'
            close.AutoSize = True
            close.MinimumSize = Size(120, 36)
            close.Click += lambda *_: self.form.Close()
            buttons.Controls.Add(self.retry)
            buttons.Controls.Add(close)
            panel.Controls.Add(buttons)
            panel.Controls.Add(label)
            panel.Controls.Add(heading)
            self.form.Controls.Add(panel)
        self.heading.Text = 'View unavailable' if retry else 'Restoring your view'
        self.label.Text = message + '\n\nRunning work stays on the server. Requests will not be sent again.'
        self.retry.Enabled = retry
        self.panel.BringToFront()

    def hide_panel(self):
        if self.panel is not None:
            self.panel.Dispose()
            self.panel = self.label = self.heading = self.retry = None
        for font in self.fonts:
            font.Dispose()
        self.fonts.clear()

    def failed(self, message):
        if self.state == 'closed' or self.quitting():
            return
        self.state = 'failed'
        self.auth = self.heartbeat = None
        self.show_panel(message + ' You can try restoring the view again or close this window.', retry=True)
        log.warning('Desktop presentation recovery stopped: %s', message)

    def recover(self, reason, *, manual=False):
        if self.state in ('closed', 'recovering') or self.quitting():
            return
        if self.state == 'failed' and not manual:
            return
        self.state = 'recovering'
        self.generation += 1
        self.window._armada_presentation_generation = self.generation
        self.heartbeat = self.auth = None
        self.restoring_drafts = False
        self.deadline = time.monotonic() + self.recovery_timeout
        self.show_panel('Restoring this view…')
        if not manual and not self.budget.allow(time.monotonic()):
            self.failed('This view has failed repeatedly. Automatic recovery has stopped.')
            return
        log.warning('Desktop presentation recovery requested: %s (generation %s)', reason, self.generation)
        generation = self.generation
        def replace():
            if self.state != 'recovering' or generation != self.generation or self.quitting():
                return
            try:
                from webview.platforms.edgechromium import EdgeChrome
                from .local_auth import browser_url
                old = self.backend
                self.unbind()
                self.form.Controls.Remove(old.webview)
                old.webview.Dispose()
                self.calls.reset()
                self.window.events.loaded.clear()
                self.window.events._pywebviewready.clear()
                self.window.real_url = browser_url(self.base_url(), self.route)
                self.window.html = None
                self.backend = EdgeChrome(self.form, self.window, old.user_data_folder)
                self.form.browser = self.backend
                self.form.webview = self.backend.webview
                self.panel.BringToFront()
                self.recoveries += 1
            except Exception:
                log.exception('Could not replace the failed browser control')
                self.failed('The browser view could not be restored.')
        try:
            self.post(replace)
        except Exception:
            log.debug('Native recovery dispatch unavailable', exc_info=True)
            self.failed('The native window could not restore its view.')

    def tick(self, *_):
        if self.state == 'closed':
            return
        now = time.monotonic()
        if self.form.IsDisposed:
            self.closed()
            return
        try:
            self.calls.poll()
            if self.quitting():
                # Quit still needs its bounded final snapshot. Stop recovery,
                # not native call completion, until the Form actually closes.
                return
            # Sleep/resume must not consume the recovery deadline or trigger a
            # false heartbeat failure while the Windows message loop was suspended.
            gap, self.last_tick = now - self.last_tick, now
            if gap > 5:
                self.deadline += gap
                if self.heartbeat:
                    self.heartbeat_started += gap
            if self.state == 'failed':
                return
            if self.state == 'recovering' and now > self.deadline:
                self.failed('The browser did not become ready in time.')
                return
            if self.auth is not None:
                if self.auth.IsCompleted:
                    result = json.loads(str(self.auth.Result)).get('result', {}).get('value', {})
                    self.auth = None
                    from . import instance, __version__
                    if self.restoring_drafts and result is True:
                        self.restoring_drafts = False
                        self.state = 'healthy'
                        self.hide_panel()
                        log.info('Desktop presentation restored and authenticated (generation %s)', self.generation)
                    elif (isinstance(result, dict) and bool(instance.current().get('nonce'))
                            and result.get('nonce') == instance.current().get('nonce')
                            and result.get('version') == __version__):
                        self.restoring_drafts = True
                        self.auth = self.start_script(self.draft_script())
                return
            if self.heartbeat is not None:
                if self.heartbeat.IsCompleted:
                    value = json.loads(str(self.heartbeat.Result))
                    self.heartbeat = None
                    if isinstance(value, dict):
                        route = recovery_route(self.base_url().rstrip('/') + str(value.get('route', '')), self.base_url())
                        if route and value.get('ready'):
                            self.route = bound_route(route, value.get('realm'))
                            caption = getattr(self.form, '_armada_caption', None)
                            if caption is not None:
                                caption.update(value.get('background'), value.get('foreground'))
                    if isinstance(value, dict) and self.state == 'recovering' and value.get('ready'):
                        self.auth = self.start_script("fetch('/api/instance',{credentials:'same-origin'}).then(r=>r.ok?r.json():{})")
                elif now - self.heartbeat_started > self.heartbeat_timeout:
                    self.recover('renderer heartbeat timed out')
                return
            if now >= self.next_heartbeat and self.backend.webview.CoreWebView2 is not None:
                # First-party documents only. External sign-in, file frames and
                # bootstrap pages are not treated as ARMADA readiness evidence.
                if recovery_route(str(self.backend.webview.Source), self.base_url()):
                    self.heartbeat = self.backend.webview.CoreWebView2.ExecuteScriptAsync(HEARTBEAT)
                    self.heartbeat_started = now
                self.next_heartbeat = now + 2
        except Exception:
            log.debug('Desktop presentation health check failed', exc_info=True)
            if self.state == 'recovering':
                self.failed('The browser failed while restoring this view.')
            else:
                self.recover('browser operation failed')

    def closed(self, *_):
        if self.state == 'closed':
            return
        self.state = 'closed'
        self.generation += 1
        self.calls.reset(close=True)
        self.unbind()
        self.timer.Stop()
        self.timer.Dispose()
        self.heartbeat = self.auth = None
        self.drafts.clear()
        self.hide_panel()


def install(base_url, quitting):
    """Install once, before any EdgeChrome control is constructed."""
    from webview.platforms.edgechromium import EdgeChrome
    EdgeChrome._armada_recovery_base = staticmethod(base_url)
    EdgeChrome._armada_recovery_quitting = staticmethod(quitting)
    if getattr(EdgeChrome, '_armada_recovery_installed', False):
        return
    original = EdgeChrome.on_webview_ready
    original_message = EdgeChrome.on_script_notify
    def message(backend, sender, args):
        # pywebview's bridge expects a three-item array. Our native draft channel
        # uses a typed object and is handled by its separate Core subscription.
        try:
            value = json.loads(str(args.WebMessageAsJson))
            if isinstance(value, dict) and value.get('type') == 'armada-unsent-draft':
                return
        except (ValueError, TypeError):
            pass
        original_message(backend, sender, args)
    def ready(backend, sender, args):
        original(backend, sender, args)
        try:
            controller = getattr(backend.form, '_armada_presentation', None)
            if controller is None:
                controller = Presentation(backend, backend._armada_recovery_base, backend._armada_recovery_quitting)
            controller.bind(backend, args)
        except Exception:
            log.exception('Could not attach desktop presentation recovery')
    EdgeChrome.on_webview_ready = ready
    EdgeChrome.on_script_notify = message
    EdgeChrome._armada_recovery_installed = True
