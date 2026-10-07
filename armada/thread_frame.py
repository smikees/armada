"""Windows resize and soft shadow for the shaped, detached conversation window.

The shadow is a non-activating, click-through, per-pixel-alpha owned window.
Its centre is transparent, so it can follow the owner's z-order without tinting
the conversation. All native resources and event handlers belong to that window.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import logging
import sys

log = logging.getLogger(__name__)


def _api():
    user = ctypes.WinDLL("user32", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    signatures = (
        (user.CreateWindowExW, w.HWND, [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]),
        (user.DestroyWindow, w.BOOL, [w.HWND]),
        (user.ShowWindow, w.BOOL, [w.HWND, ctypes.c_int]),
        (user.SetWindowPos, w.BOOL, [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]),
        (user.SendMessageW, ctypes.c_ssize_t, [w.HWND, w.UINT, ctypes.c_size_t, ctypes.c_ssize_t]),
        (user.GetDC, w.HDC, [w.HWND]),
        (user.ReleaseDC, ctypes.c_int, [w.HWND, w.HDC]),
        (user.UpdateLayeredWindow, w.BOOL, [w.HWND, w.HDC, w.LPVOID, w.LPVOID, w.HDC, w.LPVOID,
                                           w.DWORD, w.LPVOID, w.DWORD]),
        (gdi.CreateCompatibleDC, w.HDC, [w.HDC]),
        (gdi.SelectObject, w.HANDLE, [w.HDC, w.HANDLE]),
        (gdi.DeleteObject, w.BOOL, [w.HANDLE]),
        (gdi.DeleteDC, w.BOOL, [w.HDC]),
    )
    for fn, result, args in signatures:
        fn.restype, fn.argtypes = result, args
    return user, gdi


def begin_resize(window):
    """Enter Windows' bottom-right sizing loop, including capture and minimum size."""
    if sys.platform != "win32":
        return False
    from System import Action
    native = window.native
    def start():
        if native.IsDisposed:
            return
        user, _ = _api()
        user.ReleaseCapture()
        # HTBOTTOMRIGHT. Windows owns the pointer until release, even outside the WebView.
        user.SendMessageW(int(native.Handle.ToInt64()), 0x00A1, 17, 0)
    native.BeginInvoke(Action(start))
    return True


def attach(window):
    """Install once, on the form's UI thread; a decorative failure never breaks chat."""
    if sys.platform != "win32":
        return
    from System import Action
    native = window.native
    def install():
        if native.IsDisposed or getattr(window, "_thread_shadow", None) is not None:
            return
        try:
            window._thread_shadow = _Shadow(native)
        except Exception:
            log.warning("Could not create detached thread shadow", exc_info=True)
    if native.InvokeRequired:
        native.Invoke(Action(install))
    else:
        install()


class _Shadow:
    PAD = 24

    def __init__(self, native):
        self.native = native
        self.user, self.gdi = _api()
        self.handle = None
        self.size = None
        self.bitmap = None
        self.handlers = []
        self.closed_handler = False
        # WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW.
        self.handle = self.user.CreateWindowExW(
            0x080800A0, "Static", "", 0x80000000, 0, 0, 1, 1,
            int(native.Handle.ToInt64()), None, None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.refresh()
            for event in ("LocationChanged", "SizeChanged", "VisibleChanged", "DpiChanged"):
                handler = lambda *_: self.refresh()
                getattr(native, event).__iadd__(handler)
                self.handlers.append((event, handler))
            native.FormClosed += self.close
            self.closed_handler = True
        except Exception:
            self.close()
            raise

    def _path(self, width, height, scale, spread=0, offset=0):
        from System.Drawing.Drawing2D import GraphicsPath, FillMode
        path = GraphicsPath(FillMode.Winding)
        pad = self.PAD
        def arc(x, y, diameter, angle):
            path.AddArc(float((pad+x-spread)*scale), float((pad+y-spread+offset)*scale),
                        float((diameter+2*spread)*scale), float((diameter+2*spread)*scale), float(angle), 90.)
        path.AddEllipse(float((pad+8-spread)*scale), float((pad+8-spread+offset)*scale),
                        float((96+2*spread)*scale), float((96+2*spread)*scale))
        path.StartFigure()
        left, top, right, bottom, diameter = 48, 40, width-8, height-8, 28
        for x,y,angle in ((left,top,180),(right-diameter,top,270),
                          (right-diameter,bottom-diameter,0),(left,bottom-diameter,90)):
            arc(x,y,diameter,angle)
        path.CloseFigure()
        return path

    def _draw(self, width, height, scale):
        from System.Drawing import Bitmap, Color, Graphics, SolidBrush
        from System.Drawing.Drawing2D import SmoothingMode, CompositingMode
        from System.Drawing.Imaging import PixelFormat
        bitmap = Bitmap(round((width+2*self.PAD)*scale), round((height+2*self.PAD)*scale),
                        PixelFormat.Format32bppPArgb)
        graphics = Graphics.FromImage(bitmap)
        try:
            graphics.Clear(Color.Transparent)
            graphics.SmoothingMode = SmoothingMode.AntiAlias
            # Overlapping translucent silhouettes create a soft edge with an 8px drop.
            for spread in range(18, -1, -1):
                path = self._path(width, height, scale, spread, 8)
                brush = SolidBrush(Color.FromArgb(3 if spread > 8 else 5, 0, 0, 0))
                try:
                    graphics.FillPath(brush, path)
                finally:
                    brush.Dispose()
                    path.Dispose()
            # No shadow pixels over the owner, including its portrait and crescent.
            graphics.CompositingMode = CompositingMode.SourceCopy
            graphics.SmoothingMode = getattr(SmoothingMode, "None")
            path = self._path(width, height, scale, 1)
            brush = SolidBrush(Color.Transparent)
            try:
                graphics.FillPath(brush, path)
            finally:
                brush.Dispose()
                path.Dispose()
        except Exception:
            bitmap.Dispose()
            raise
        finally:
            graphics.Dispose()
        return bitmap

    def refresh(self):
        if not self.handle or self.native.IsDisposed:
            return
        try:
            native = self.native
            scale = float(native._scale) or 1
            size = (native.ClientSize.Width, native.ClientSize.Height, scale)
            pad = round(self.PAD*scale)
            if size != self.size:
                bitmap = self._draw(size[0]/scale, size[1]/scale, scale)
                try:
                    self._upload(bitmap, native.Left-pad, native.Top-pad)
                except Exception:
                    bitmap.Dispose()
                    raise
                if self.bitmap is not None:
                    self.bitmap.Dispose()
                self.bitmap, self.size = bitmap, size
            else:
                self.user.SetWindowPos(self.handle, None, native.Left-pad, native.Top-pad, 0, 0,
                                       0x0001 | 0x0004 | 0x0010)  # NOSIZE | NOZORDER | NOACTIVATE
            self.user.ShowWindow(self.handle, 4 if native.Visible and str(native.WindowState) != "Minimized" else 0)
        except Exception:
            # Avoid retrying at every mouse movement if Windows refuses the decoration.
            log.warning("Could not update detached thread shadow", exc_info=True)
            self.close()

    def _upload(self, bitmap, left, top):
        from System.Drawing import Color
        class Blend(ctypes.Structure):
            _fields_ = [("op", w.BYTE), ("flags", w.BYTE), ("alpha", w.BYTE), ("format", w.BYTE)]
        point, size, source = w.POINT(left, top), w.SIZE(bitmap.Width, bitmap.Height), w.POINT(0, 0)
        blend = Blend(0, 0, 255, 1)  # AC_SRC_OVER, AC_SRC_ALPHA
        screen = self.user.GetDC(None)
        memory = self.gdi.CreateCompatibleDC(screen)
        handle = int(bitmap.GetHbitmap(Color.FromArgb(0)).ToInt64())
        old = self.gdi.SelectObject(memory, handle)
        try:
            if not self.user.UpdateLayeredWindow(self.handle, screen, ctypes.byref(point), ctypes.byref(size),
                                                 memory, ctypes.byref(source), 0, ctypes.byref(blend), 2):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.gdi.SelectObject(memory, old)
            self.gdi.DeleteObject(handle)
            self.gdi.DeleteDC(memory)
            self.user.ReleaseDC(None, screen)

    def close(self, *_):
        if self.closed_handler:
            self.native.FormClosed -= self.close
            self.closed_handler = False
        for event, handler in self.handlers:
            getattr(self.native, event).__isub__(handler)
        self.handlers.clear()
        if self.handle:
            self.user.DestroyWindow(self.handle)
            self.handle = None
        if self.bitmap is not None:
            self.bitmap.Dispose()
            self.bitmap = None
