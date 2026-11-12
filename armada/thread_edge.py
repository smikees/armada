"""Antialiased WebView perimeter on a click-through, per-pixel-alpha window.

Only a three-pixel logical band is cached. The interactive WebView stays live;
preview bytes never leave memory. A failed/stale capture keeps the original clip.
"""
import logging
import threading

log = logging.getLogger(__name__)


def perimeter(preview, scale):
    from System.Drawing import Bitmap, Graphics, Region
    from System.Drawing.Imaging import PixelFormat
    from System.Drawing.Drawing2D import CombineMode
    from .thread_frame import _frame_path
    bitmap = Bitmap(preview.Width, preview.Height, PixelFormat.Format32bppPArgb)
    painter = Graphics.FromImage(bitmap)
    outer = _frame_path(preview.Width/scale, preview.Height/scale, scale, spread=1)
    inner = _frame_path(preview.Width/scale, preview.Height/scale, scale, spread=-3)
    region = Region(outer)
    try:
        region.Exclude(inner)
        painter.SetClip(region, CombineMode.Replace)
        # CapturePreview preserves Chromium's fractional alpha, including the
        # actual portrait/accent colours. Do not threshold or resample it.
        painter.DrawImageUnscaled(preview, 0, 0)
    except Exception:
        bitmap.Dispose()
        raise
    finally:
        region.Dispose(); inner.Dispose(); outer.Dispose(); painter.Dispose()
    return bitmap


class Edge:
    def __init__(self, native):
        from System.Windows.Forms import Timer
        from .thread_frame import _api
        self.native = native
        self.user, self.gdi = _api()
        self.bitmap = None
        self.size = None
        self.busy = False
        self.dirty = False
        self.closed = False
        self.error = ''
        self.stream = self.task = None
        self.handlers = []
        self.handle = self.user.CreateWindowExW(0x080800A0, 'Static', '', 0x80000000,
            0, 0, 1, 1, int(native.Handle.ToInt64()), None, None, None)
        if not self.handle:
            raise OSError('Could not create the frame edge')
        self.timer = Timer()
        self.timer.Interval = 120
        self.timer.Tick += self._capture
        for name in ('LocationChanged', 'VisibleChanged'):
            handler = lambda *_: self.position()
            getattr(native, name).__iadd__(handler)
            self.handlers.append((name, handler))
        for name in ('SizeChanged', 'DpiChanged'):
            handler = lambda *_: self.request()
            getattr(native, name).__iadd__(handler)
            self.handlers.append((name, handler))
        native.FormClosed += self.close
        self.request()

    def dimensions(self):
        return (self.native.ClientSize.Width, self.native.ClientSize.Height, float(self.native._scale) or 1)

    def current(self):
        return self.bitmap is not None and self.size == self.dimensions()

    def request(self):
        if self.closed or self.native.IsDisposed:
            return
        self.dirty = True
        self.position()
        if not self.busy and not self.timer.Enabled:
            self.timer.Start()

    def position(self):
        if self.closed:
            return
        native = self.native
        visible = self.current() and native.Visible and str(native.WindowState) != 'Minimized'
        if self.current():
            self.user.SetWindowPos(self.handle, None, native.Left, native.Top, 0, 0, 0x0015)
        self.user.ShowWindow(self.handle, 4 if visible else 0)

    def _clip(self, spread):
        from System.Drawing import Region
        from .thread_frame import _frame_path
        width, height, scale = self.dimensions()
        path = _frame_path(width/scale, height/scale, scale, spread=spread)
        try:
            old = self.native.Region
            self.native.Region = Region(path)
            if old is not None:
                old.Dispose()
        finally:
            path.Dispose()

    def _capture(self, *_):
        self.timer.Stop()
        if self.closed or self.busy or not self.dirty:
            return
        from System import Action
        from System.IO import MemoryStream
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        self.dirty = False
        size = self.dimensions()
        stream = MemoryStream()
        try:
            task = self.native.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
        except Exception as exc:
            self.error = str(exc)
            stream.Dispose()
            log.debug('Frame preview could not start', exc_info=True)
            return
        self.busy = True
        self.stream, self.task = stream, task
        def finish():
            try:
                task.GetAwaiter().GetResult()
                def apply():
                    try:
                        self._apply(stream, size)
                    except Exception as exc:
                        self.error = str(exc)
                        log.debug('Frame edge unavailable', exc_info=True)
                    finally:
                        stream.Dispose()
                        self.stream = self.task = None
                        self.busy = False
                        if self.dirty:
                            self.request()
                if self.closed or self.native.IsDisposed:
                    stream.Dispose()
                    self.busy = False
                else:
                    self.native.BeginInvoke(Action(apply))
            except Exception as exc:
                self.error = str(exc)
                stream.Dispose()
                self.busy = False
                log.debug('Frame preview unavailable', exc_info=True)
        threading.Thread(target=finish, name='thread-edge-preview', daemon=True).start()

    def _apply(self, stream, size):
        if self.closed:
            return
        if size != self.dimensions():
            self.dirty = True
            return
        from System.Drawing import Bitmap
        from .thread_frame import _Shadow
        stream.Position = 0
        preview = Bitmap(stream)
        try:
            if (preview.Width, preview.Height) != size[:2]:
                self.error = f'Preview dimensions {preview.Width}x{preview.Height}, native {size}'
                return
            bitmap = perimeter(preview, size[2])
        finally:
            preview.Dispose()
        try:
            _Shadow._upload(self, bitmap, self.native.Left, self.native.Top)
        except Exception as exc:
            self.error = str(exc)
            bitmap.Dispose()
            log.debug('Frame edge upload unavailable', exc_info=True)
            return
        old = self.bitmap
        self.error = ''
        self.bitmap, self.size = bitmap, size
        self._clip(-2)
        self.position()
        if old is not None:
            old.Dispose()

    def close(self, *_):
        if self.closed:
            return
        self.closed = True
        # A completed capture may already have queued a UI callback when the
        # form closes. A still-writing capture is disposed by its waiting thread.
        if self.task is not None and self.task.IsCompleted:
            self.stream.Dispose()
        self.timer.Stop()
        self.timer.Tick -= self._capture
        self.timer.Dispose()
        self.native.FormClosed -= self.close
        for name, handler in self.handlers:
            getattr(self.native, name).__isub__(handler)
        self.handlers.clear()
        self.user.DestroyWindow(self.handle)
        self.handle = None
        if self.bitmap is not None:
            self.bitmap.Dispose()
            self.bitmap = None
