"""Native desktop window for ARMADA (SPEC §13 — the app wrapper).

Wraps the existing local web cockpit (serve.py) in a real OS window via pywebview, so ARMADA
feels like an app rather than a browser tab. The server runs in a background thread on
127.0.0.1; the window points at it. Everything else — Update & Restart, streaming chat,
the dashboard — is unchanged, because it's the same server underneath.

`webview` is imported lazily inside run(), so the stdlib `armada serve` path stays
dependency-free; only `armada app` needs pywebview installed.
"""
from __future__ import annotations
import logging
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import urllib.parse
from . import brand
from .util import swallowed
log = logging.getLogger(__name__)
_main_window = None
_alex_window = None
_window_lock = threading.RLock()
_quitting = False
_app_url = ""


def _webview_options():
    """All app windows share an owner-only browser profile.

    pywebview's default private mode deletes the profile's cookies whenever a
    new WebView2 window initializes, invalidating the already-open cockpit.
    Session tokens still rotate with each server and each window bootstraps them.
    """
    from .local_auth import desktop_storage
    return dict(private_mode=False, storage_path=str(desktop_storage()))


def _deliver_alexander(window, payload):
    """Deliver once the companion page is ready, across its auth redirect too."""
    if not payload or not payload.get('message'):
        return
    lock = threading.Lock()
    delivered = False

    def ready():
        nonlocal delivered
        with lock:
            if delivered:
                return
            try:
                sent = window.evaluate_js(
                    "typeof window.mcAlexReceive === 'function' && "
                    "(window.mcAlexReceive(" + json.dumps(payload, ensure_ascii=False) + "), true)")
            except Exception:
                log.debug('Alexander receiver is not ready yet', exc_info=True)
                return  # The browser/bridge may still be initializing.
            if sent is True:
                delivered = True
                window.events.loaded -= ready

    window.events.loaded += ready
    if window.events.loaded.is_set():
        ready()


def _alexander_bounds(main, area, width=520, height=720, gap=10):
    """Place a companion beside the main window, within this monitor's working area."""
    mx, my, mw, mh = main
    ax, ay, aw, ah = area
    width, height = min(width, aw), min(height, ah)
    right, left = mx + mw + gap, mx - gap - width
    x = right if right + width <= ax + aw else left
    x = max(ax, min(x, ax + aw - width))
    y = max(ay, min(my, ay + ah - height))
    return dict(x=int(x), y=int(y), width=int(width), height=int(height))


def _alexander_position():
    """pywebview uses logical pixels; WinForms working areas use physical pixels."""
    try:
        native = _main_window.native
        from System.Windows.Forms import Screen
        area = Screen.FromControl(native).WorkingArea
        scale = float(native._scale) or 1
        return _alexander_bounds(
            (_main_window.x, _main_window.y, _main_window.width, _main_window.height),
            (area.X / scale, area.Y / scale, area.Width / scale, area.Height / scale))
    except Exception:
        log.debug("Could not determine Alexander's adjacent position", exc_info=True)
        return dict(width=520, height=720)


class _AlexanderCompanionAPI:
    """The companion's close control can destroy only its own native window."""

    def __init__(self):
        self._window = None

    def close_window(self):
        """Close Alexander without closing the cockpit or losing saved conversation history."""
        if self._window is not None:
            self._window.destroy()


def _shape_alexander(window):
    """Clip the Windows form to the portrait and panel; transparent margins stay click-through.

    WebView2's transparent background alone still exposes the underlying WinForms rectangle.
    Keep this native region in step with the logical geometry in brand.css, at the form's DPI.
    """
    if sys.platform != "win32":
        return
    try:
        from System import Action
        from System.Drawing import Region
        from System.Drawing.Drawing2D import GraphicsPath, FillMode

        native = window.native

        def apply():
            scale = float(native._scale) or 1
            width, height = native.ClientSize.Width / scale, native.ClientSize.Height / scale
            path = GraphicsPath(FillMode.Winding)  # union, not a hole where portrait overlaps panel
            path.AddEllipse(8 * scale, 8 * scale, 96 * scale, 96 * scale)
            left, top, right, bottom, diameter = 48, 40, width - 8, height - 8, 28
            for x, y, angle in ((left, top, 180), (right - diameter, top, 270),
                                (right - diameter, bottom - diameter, 0),
                                (left, bottom - diameter, 90)):
                path.AddArc(x * scale, y * scale, diameter * scale, diameter * scale, angle, 90)
            path.CloseFigure()
            old = native.Region
            native.Region = Region(path)
            path.Dispose()
            if old is not None:
                old.Dispose()

        if native.InvokeRequired:
            native.Invoke(Action(apply))
        else:
            apply()
    except Exception:
        log.warning("Could not shape Alexander's companion window", exc_info=True)


def open_alexander(request: dict | None = None) -> bool:
    """Show Alexander in his own native window, reusing one that is already open."""
    global _alex_window
    if not _main_window or not _app_url:
        return False
    import webview
    import json
    payload = {"message": str(request.get("message") or "")[:6000],
               "item": request.get("item") if isinstance(request.get("item"), dict) else None,
               "page": str(request.get("page") or "")[:300]} if isinstance(request, dict) else None
    with _window_lock:
        if _alex_window is not None:
            try:
                _alex_window.show()
                _alex_window.restore()
                bounds = _alexander_position()
                if "x" in bounds:
                    _alex_window.resize(bounds["width"], bounds["height"])
                    _alex_window.move(bounds["x"], bounds["y"])
                _deliver_alexander(_alex_window, payload)
                return True
            except Exception:
                logging.getLogger(__name__).exception('Reopening Alexander failed')
                _alex_window = None
        try:
            api = _AlexanderCompanionAPI()
            from .local_auth import browser_url
            w = webview.create_window("Alexander — ARMADA", browser_url(_app_url, '/alexander'),
                                      **_alexander_position(), min_size=(400, 500), text_select=True,
                                      frameless=True, transparent=True, easy_drag=False, js_api=api)
            api._window = w
            _alex_window = w
            w.events.loaded += lambda: _shape_alexander(w)
            w.events.resized += lambda *args: _shape_alexander(w)
            w.events.closed += lambda: _clear_alexander(w)
            _deliver_alexander(w, payload)
            threading.Thread(target=_apply_window_icon, daemon=True).start()
            return True
        except Exception:
            log.exception("Could not open Alexander's window")
            return False


def _clear_alexander(window):
    global _alex_window
    with _window_lock:
        if _alex_window is window:
            _alex_window = None


def show_main(*, href: str = "", report: str = "") -> bool:
    """Apply Alexander's navigation/report cards in the main cockpit window."""
    if _main_window is None:
        return False
    import json
    if href and (not href.startswith("/") or href.startswith("//") or "\\" in href):
        return False
    _main_window.show()
    _main_window.restore()
    if href:
        from .local_auth import browser_url
        _main_window.load_url(browser_url(_app_url, href))
    elif report:
        _main_window.evaluate_js("window.mcSupportOpen({message:" + json.dumps(report[:6000]) + "})")
    return True

# A stable AppUserModelID so Windows treats the window as its own app (not "pythonw.exe") — this is
# what lets the taskbar button use OUR icon instead of the Python interpreter's, and keeps ARMADA
# from grouping under other Python windows.
_APP_ID = "Stamih.ARMADA.App"


def _fatal(msg: str) -> None:
    """Report a startup failure by every channel that might actually be seen.

    `armada app` is normally launched by ARMADA.vbs via pythonw.exe, which has no console — so
    stdout/stderr go nowhere. Log it (the log file survives), and on Windows put it on screen in a
    message box, so a failed launch explains itself instead of dying silently.
    """
    try:
        logging.getLogger("armada.app").error(msg.replace("\n", " "))
    except Exception:  # silent-ok: logging itself is what failed
        pass
    print(msg)
    if sys.platform == "win32":
        try:
            import ctypes
            MB_ICONERROR, MB_SETFOREGROUND = 0x10, 0x10000
            ctypes.windll.user32.MessageBoxW(None, msg, f"{brand.NAME} — cannot start",
                                             MB_ICONERROR | MB_SETFOREGROUND)
        except Exception:  # noqa — never let the error reporter raise
            log.debug('_fatal: failed; ignored', exc_info=True)


def _server_matches(url: str, realm: str) -> bool:
    """Recognize the same realm without asking the dashboard to render."""
    from .request_context import RealmContext
    try:
        from . import local_auth
        request = urllib.request.Request(url + "api/instance", headers=local_auth.headers(urllib.parse.urlsplit(url).port or 8756))
        with urllib.request.urlopen(request, timeout=0.5) as response:
            info = json.load(response)
        return (isinstance(info, dict) and info.get("app") == "ARMADA"
                and info.get("realm_id") == RealmContext.capture(realm).realm_id)
    except (OSError, ValueError, TypeError):
        return False


def _wait_until_up(url: str, realm: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_matches(url, realm):
            return True
        time.sleep(0.1)
    return False


def _free_port_pair(after: int) -> int:
    """Find separate app/content ports when the default belongs to another server."""
    for port in range(after, min(after + 200, 65534), 2):
        sockets = []
        try:
            for candidate in (port, port + 1):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sockets.append(sock)
                sock.bind(("127.0.0.1", candidate))
            return port
        except OSError:
            continue
        finally:
            for sock in sockets:
                sock.close()
    raise OSError("No free local port pair is available for ARMADA.")


def _set_app_user_model_id() -> None:
    """Windows: declare our own AppUserModelID so the taskbar stops using pythonw.exe's identity."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except Exception:  # noqa — cosmetic only
        log.debug('_set_app_user_model_id: failed; ignored', exc_info=True)


def _retire_scheduler_run_key() -> None:
    """Remove the sign-in scheduler entry made by older Armada installers."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.DeleteValue(handle, "ARMADA Scheduler")
    except FileNotFoundError:
        pass
    except OSError:
        log.warning("Could not remove the old scheduler sign-in entry", exc_info=True)


_window_icons = {}  # Keep managed icons alive while HWNDs reference their handles.


def _apply_window_icon() -> None:
    """Windows: force the ARMADA icon onto our top-level window(s) via WM_SETICON, once they exist.

    pywebview's start(icon=) doesn't reliably reach the taskbar on the EdgeChromium backend, so we
    load the .ico ourselves and set both the small (titlebar/alt-tab) and big (taskbar) icons on the
    window whose title is ARMADA. Runs on a helper thread after the GUI loop starts; best-effort.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:  # noqa
        log.debug('_apply_window_icon: failed; returning a fallback', exc_info=True)
        return
    ico = str(brand.icon_path())
    if not brand.icon_path().exists():
        return
    user32 = ctypes.windll.user32
    WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    if hasattr(user32, 'GetDpiForWindow'):
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT
    if hasattr(user32, 'GetSystemMetricsForDpi'):
        user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    matches: list[int] = []

    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != os.getpid():
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if brand.NAME.lower() in buf.value.lower():
                matches.append(hwnd)
        return True

    for _ in range(60):  # window may not exist for a moment after start()
        matches.clear()
        user32.EnumWindows(WNDENUMPROC(_enum), 0)
        if matches:
            for hwnd in matches:
                dpi = user32.GetDpiForWindow(hwnd) if hasattr(user32, 'GetDpiForWindow') else 96
                for kind, metric, default in ((ICON_SMALL, 49, 16), (ICON_BIG, 11, 32)):
                    size = user32.GetSystemMetricsForDpi(metric, dpi or 96) if hasattr(user32, 'GetSystemMetricsForDpi') else default
                    size = size or default
                    if size not in _window_icons:
                        _window_icons[size] = brand.native_icon(size)
                    user32.SendMessageW(hwnd, WM_SETICON, kind, _window_icons[size].Handle.ToInt64())
            return
        time.sleep(0.1)


_WEBVIEW2 = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def webview2_version() -> str:
    """The installed WebView2 Runtime's version, or "" if there's none — Microsoft's documented
    check: a `pv` value above 0.0.0.0 under EdgeUpdate\\Clients, machine-wide or per user."""
    try:
        import winreg
    except ImportError:                      # not Windows
        return ""
    places = [(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + _WEBVIEW2),
              (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + _WEBVIEW2),
              (winreg.HKEY_CURRENT_USER, "Software\\" + _WEBVIEW2)]
    for root, key in places:
        try:
            with winreg.OpenKey(root, key) as k:
                v = str(winreg.QueryValueEx(k, "pv")[0] or "")
        except OSError:
            continue
        if v and v != "0.0.0.0":
            return v
    return ""


def _startup_html() -> str:
    """Self-contained loading view, available before the local server is ready."""
    import base64
    from . import appconfig
    mode = appconfig.get("appearance", "system")
    def image(asset):
        return "data:image/png;base64," + base64.b64encode((brand._STATIC / asset).read_bytes()).decode("ascii")
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>{brand.NAME}</title>
<style>html,body{{height:100%;margin:0}}body{{display:grid;place-items:center;background:#f2f2f3;color:#333}}
.loading{{width:208px;text-align:center}}img{{width:208px;height:auto;object-fit:contain;display:block}}.dark{{display:none}}
.track{{margin-top:28px;height:3px;border-radius:4px;overflow:hidden;background:rgba(90,110,125,.16)}}
.bar{{width:40%;height:100%;background:#259ab1;border-radius:4px;animation:loading 1.5s ease-in-out infinite}}
@keyframes loading{{from{{transform:translateX(-110%)}}to{{transform:translateX(360%)}}}}
@media(prefers-reduced-motion:reduce){{.bar{{animation:none;margin:auto}}}}
{'body{background:#1e2024;color:#ddd}.light{display:none}.dark{display:block}' if mode == 'dark' else ''}
{'@media(prefers-color-scheme:dark){body{background:#1e2024;color:#ddd}.light{display:none}.dark{display:block}}' if mode == 'system' else ''}
</style><body><div class="loading"><img class="light" src="{image(brand.WORDMARK_ASSET)}" alt="{brand.NAME}">
<img class="dark" src="{image(brand.WORDMARK_DARK_ASSET)}" alt="{brand.NAME}">
<div class="track" role="progressbar" aria-label="Loading Armada"><div class="bar"></div></div></div></body></html>'''


def run(realm: str, port: int = 8756, title: str = "") -> int:
    """Open ARMADA in a native window. Blocks until the window is closed."""
    global _main_window, _app_url, _quitting
    from .util import init_logging
    init_logging('armada.log')
    _quitting = False
    title = title or brand.window_title()
    _set_app_user_model_id()   # must be before any window is created
    _retire_scheduler_run_key()
    try:
        import webview  # pywebview — only needed for the windowed app
    except ImportError:
        # Under pythonw (how the .vbs launcher starts us) there is no console, so a bare print()
        # here is invisible: the process would start, fail, and vanish with no window and no error —
        # which reads as "the app is broken" rather than "a dependency is missing". Say it out loud.
        _fatal("ARMADA needs pywebview to open its window.\n\n"
               "Install it in this environment:\n"
               "    uv pip install pywebview\n"
               "(or:  python -m pip install pywebview)\n\n"
               "Until then, 'armada serve' still works in a browser at 127.0.0.1:8756.")
        return 1
    if sys.platform == "win32" and not webview2_version():
        # Without WebView2, pywebview quietly falls back to Internet Explorer's engine, which can't
        # draw the app: an unstyled page that looks broken (seen on a clean Windows Sandbox, 5.2).
        # The installer normally puts WebView2 in place; this is for a machine where that failed.
        _fatal("ARMADA's window needs Microsoft Edge WebView2, which isn't on this computer.\n\n"
               "It's free from Microsoft:\n"
               "    https://developer.microsoft.com/microsoft-edge/webview2/\n"
               "(choose the Evergreen Bootstrapper). Install it, then open ARMADA again.")
        return 1

    # pywebview's EdgeChromium backend disables WebView2's native context menu unless debug=True
    # (it sets AreDefaultContextMenusEnabled = debug). We want the native right-click menu — so the
    # composer's spelling-correction suggestions work — WITHOUT enabling devtools/status bar. Patch
    # just that one setting, applied right after pywebview writes its own during webview init.
    try:
        from webview.platforms import edgechromium as _ec
        _orig_ready = _ec.EdgeChrome.on_webview_ready
        _ctx_handlers = []   # keep .NET event handlers alive (don't let Python GC them)

        def _strip_more_tools(_sender, e):
            # Drop WebView2's 'More tools' submenu (inspect / web capture / read aloud / share) — it's
            # never useful in this app; leave the spelling suggestions, cut/copy/paste, etc.
            try:
                items = e.MenuItems
                for i in range(items.Count - 1, -1, -1):
                    it = items[i]
                    nm = (getattr(it, "Name", "") or "").lower()
                    lbl = (getattr(it, "Label", "") or "").lower().replace("&", "")
                    if nm == "other" or lbl.startswith("more tool"):
                        items.RemoveAt(i)
            except Exception:  # noqa
                log.debug('_strip_more_tools: failed; ignored', exc_info=True)

        def _ready_with_ctxmenu(self, sender, args):
            _orig_ready(self, sender, args)
            try:
                cw = sender.CoreWebView2
                cw.Settings.AreDefaultContextMenusEnabled = True
                cw.ContextMenuRequested += _strip_more_tools
                _ctx_handlers.append(_strip_more_tools)
            except Exception:  # noqa — settings/event unavailable on this init path; ignore
                log.debug('_ready_with_ctxmenu: failed; ignored', exc_info=True)
        _ec.EdgeChrome.on_webview_ready = _ready_with_ctxmenu
    except Exception:  # noqa — non-EdgeChromium backend or API drift: skip, app still runs
        log.debug('run: failed; ignored', exc_info=True)

    url = f"http://127.0.0.1:{port}/"
    _app_url = url
    err = {}

    def _prepare_server():
        # Import and probe only after the main window is showing its loader.
        nonlocal port, url
        global _app_url
        from . import serve
        if serve.port_owner(port) and not _server_matches(url, realm):
            old_port = port
            port = _free_port_pair(port + 2)
            url = f"http://127.0.0.1:{port}/"
            _app_url = url
            log.warning("port %s belongs to another or unhealthy server; opening on %s", old_port, port)
        from . import instance
        instance.publish_port(port)
        if not _server_matches(url, realm):
            def _serve():
                try:
                    serve.serve(realm, port)
                except Exception as e:
                    swallowed(log, '_serve: failed; using a default')
                    err["e"] = e
            threading.Thread(target=_serve, daemon=True).start()

    # Scheduled jobs are fired by a separate process bound to this app's lifetime, including
    # while the window is hidden in the tray. Start it now if it isn't running. Off a thread: nothing here should delay the
    # window, and ensure_running never raises.
    def _autostart_scheduler():
        try:
            from . import activerealm, schedsvc
            root = activerealm.resolve(realm)
            if root:
                r = schedsvc.ensure_running(root)
                log.info("scheduler on launch: %s", r)
        except Exception:  # noqa — the window matters more than the scheduler check
            swallowed(log, "run: scheduler autostart failed; the in-app bar will offer it")

    # Window title stays "ARMADA" (realm-agnostic — it doesn't change when you switch realms).
    # text_select=True: pywebview disables document text selection by default (app-like), which
    # stopped you selecting/copying text out of thread messages. Enable it so the cockpit behaves
    # like a normal page. (A CSS fallback in brand.css also re-enables selection inside threads for
    # an already-open window, before it's relaunched with this flag.)
    # min width 1400: the cockpit's widest pages (Capabilities' list + sticky legend, the dashboard
    # widget grid) need it — below that the right-hand column wraps and the layout breaks up.
    main = webview.create_window(title, html=_startup_html(), width=1440, height=860,
                                 min_size=(1400, 700), text_select=True)
    from .startup_splash import LoadingPanel
    loader = LoadingPanel(main)
    painted = threading.Event()
    navigating = threading.Event()
    def _page_loaded():
        if not painted.is_set() or (navigating.is_set() and not loader.finished):
            try:
                main.evaluate_js('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))')
            except Exception:
                log.debug('Could not confirm a painted startup frame', exc_info=True)
            if navigating.is_set():
                if not main.evaluate_js("!!document.querySelector('link[href*=\"/static/brand.css\"]')"):
                    return  # Auth/bootstrap and refusal pages are not a ready desktop.
                loader.ready()
                from . import instance
                instance.desktop_ready()
            else:
                painted.set()
    main.events.loaded += _page_loaded
    _main_window = main
    from . import instance
    activation_stop = instance.watch_activation(lambda: (main.show(), main.restore()))
    from . import appconfig
    from .tray import Tray
    tray = Tray(lambda: (main.show(), main.restore()), lambda: _quit_windows(main))
    tray_ready = tray.start()

    def _on_main_closing():
        if not _quitting and tray_ready and appconfig.get("keep_in_tray", True) is not False:
            threading.Thread(target=main.hide, daemon=True).start()
            return False  # cancel close; the process, scheduler, and Telegram remain alive
        _quit_windows(main, close_main=False)
        return True

    def _on_main_minimized():
        if tray_ready and appconfig.get("keep_in_tray", True) is not False:
            main.hide()

    main.events.closing += _on_main_closing
    main.events.minimized += _on_main_minimized
    # Window/taskbar icon = the ARMADA mark (best-effort at runtime; the packaged .exe sets it
    # definitively via PyInstaller --icon). Not all pywebview backends honour start(icon=...).
    # The icon file is defined in brand.py so a re-skin is one edit.
    # _apply_window_icon runs after the GUI loop starts and forces our icon onto the taskbar button
    # (WM_SETICON) — the reliable path; webview.start(icon=) is passed too as a best-effort backstop.
    ico = brand.icon_path()
    def _start_main():
        _apply_window_icon()
        try:
            _prepare_server()
        except Exception as exc:
            logging.getLogger(__name__).exception('Desktop server startup failed')
            err['startup_failed'] = True
            _fatal(f'ARMADA could not start its server: {exc}')
            _quit_windows(main)
            return
        if _wait_until_up(url, realm):
            if not painted.wait(30):
                err['startup_failed'] = True
                _fatal('ARMADA could not render its startup screen. Please restart the app.')
                _quit_windows(main)
                return
            if not _quitting:
                navigating.set()
                from .local_auth import browser_url
                main.load_url(browser_url(url))
                threading.Thread(target=_autostart_scheduler, daemon=True).start()
        elif not _quitting:
            err["startup_failed"] = True
            why = f"\n\n{type(err['e']).__name__}: {err['e']}" if err.get("e") else ""
            _fatal(f"{brand.NAME}: the server did not come up on {url}.{why}")
            _quit_windows(main)
    try:
        try:
            webview.start(_start_main, icon=str(ico), **_webview_options())
        except TypeError:
            webview.start(_start_main, **_webview_options())
    finally:
        activation_stop.set()
        _quitting = True
        try:
            from . import schedsvc
            schedsvc.stop_for_app_exit()
        except Exception:
            log.exception("Could not stop scheduled jobs during Armada exit")
        tray.stop()
        _main_window = None
    return 1 if err.get("startup_failed") else 0


def _quit_windows(main, *, close_main=True):
    """Exit the GUI. An owner-bound scheduler stops when this process exits."""
    global _quitting
    _quitting = True
    with _window_lock:
        alex = _alex_window
    if alex is not None:
        try:
            alex.destroy()
        except Exception:
            log.debug("Alexander window already closed", exc_info=True)
    if close_main:
        main.destroy()
