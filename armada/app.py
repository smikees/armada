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
import sys
import threading
import time
import urllib.request
from . import brand
from .util import swallowed
log = logging.getLogger(__name__)

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


def _wait_until_up(url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except Exception:  # noqa — server still booting
            log.debug('_wait_until_up: failed; retrying', exc_info=True)
            time.sleep(0.1)
    return False


def _set_app_user_model_id() -> None:
    """Windows: declare our own AppUserModelID so the taskbar stops using pythonw.exe's identity."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except Exception:  # noqa — cosmetic only
        log.debug('_set_app_user_model_id: failed; ignored', exc_info=True)


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
    IMAGE_ICON, LR_LOADFROMFILE = 1, 0x00000010
    WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
    hicon_big = user32.LoadImageW(None, ico, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | 0x40)  # default big size
    hicon_sm = user32.LoadImageW(None, ico, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    if not hicon_big and not hicon_sm:
        return

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    matches: list[int] = []

    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
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
                if hicon_sm:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_sm)
                if hicon_big:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            return
        time.sleep(0.1)


def run(realm: str, port: int = 8756, title: str = "") -> int:
    """Open ARMADA in a native window. Blocks until the window is closed."""
    title = title or brand.window_title()
    _set_app_user_model_id()   # must be before any window is created
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

    from . import serve
    url = f"http://127.0.0.1:{port}/"

    # If a server is already serving this port (e.g. the always-on `armada serve`), attach the
    # window to it instead of starting a second one (which would fail to bind). Otherwise start
    # our own on a daemon thread — ThreadingHTTPServer.serve_forever(), no signal handlers, so
    # it's safe off the main thread; the GUI must own the main thread.
    if not _wait_until_up(url, timeout=0.6):
        err = {}

        def _serve():
            try:
                serve.serve(realm, port)
            except Exception as e:  # noqa — carry the reason back to the main thread
                swallowed(log, '_serve: failed; using a default')
                err["e"] = e
        threading.Thread(target=_serve, daemon=True).start()
        if not _wait_until_up(url):
            # Distinguish "someone else owns this port" from "our server failed to start" — the
            # first is a stale/duplicate ARMADA and needs different advice from a real failure.
            if serve.port_owner(port):
                _fatal(f"{brand.NAME} looks like it's already running on port {port}.\n\n"
                       "Close the other window (or end the leftover 'pythonw' process) and try "
                       "again — only one copy can own the port.")
            else:
                why = f"\n\n{type(err['e']).__name__}: {err['e']}" if err.get("e") else ""
                _fatal(f"{brand.NAME}: the server did not come up on {url}.{why}")
            return 1

    # Scheduled jobs are fired by a separate background process (so they run with this window
    # closed). Start it now if it isn't running — otherwise the first sign of trouble after a
    # reboot is a job that silently didn't run (5.5). Off a thread: nothing here should delay the
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
    threading.Thread(target=_autostart_scheduler, daemon=True).start()

    # Window title stays "ARMADA" (realm-agnostic — it doesn't change when you switch realms).
    # text_select=True: pywebview disables document text selection by default (app-like), which
    # stopped you selecting/copying text out of thread messages. Enable it so the cockpit behaves
    # like a normal page. (A CSS fallback in brand.css also re-enables selection inside threads for
    # an already-open window, before it's relaunched with this flag.)
    # min width 1400: the cockpit's widest pages (Capabilities' list + sticky legend, the dashboard
    # widget grid) need it — below that the right-hand column wraps and the layout breaks up.
    webview.create_window(title, url, width=1440, height=860, min_size=(1400, 700), text_select=True)
    # Window/taskbar icon = the ARMADA mark (best-effort at runtime; the packaged .exe sets it
    # definitively via PyInstaller --icon). Not all pywebview backends honour start(icon=...).
    # The icon file is defined in brand.py so a re-skin is one edit.
    # _apply_window_icon runs after the GUI loop starts and forces our icon onto the taskbar button
    # (WM_SETICON) — the reliable path; webview.start(icon=) is passed too as a best-effort backstop.
    ico = brand.icon_path()
    try:
        webview.start(_apply_window_icon, icon=str(ico))
    except TypeError:
        webview.start(_apply_window_icon)
    return 0
