"""Loading artwork inside the main window, including while WebView2 starts."""
import logging
import sys
import time

log = logging.getLogger(__name__)


def _dark():
    from . import appconfig
    mode = appconfig.get('appearance', 'system')
    if mode != 'system':
        return mode == 'dark'
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0
    except OSError:
        return False


class LoadingPanel:
    """A child control, never a second top-level window or helper process."""

    def __init__(self, window):
        self.window = window
        self.panel = self.timer = self.image = self.track = self.bar = None
        self.finished = False
        window.events.before_show += self.mount

    def mount(self):
        # before_show runs synchronously on the native UI thread.
        if sys.platform != 'win32' or self.finished:
            return  # Other backends retain the in-window HTML loading screen.
        try:
            from System.Drawing import Color, Image, SolidBrush
            from System.Reflection import BindingFlags
            from System.Windows.Forms import DockStyle, Panel, Timer
            from . import brand
            dark = _dark()
            self.panel = Panel()
            self.panel.Dock = DockStyle.Fill
            self.panel.AccessibleName = 'Loading Armada'
            self.panel.BackColor = Color.FromArgb(30, 32, 36) if dark else Color.FromArgb(242, 242, 243)
            prop = self.panel.GetType().GetProperty('DoubleBuffered', BindingFlags.Instance | BindingFlags.NonPublic)
            prop.SetValue(self.panel, True, None)
            asset = brand.WORDMARK_DARK_ASSET if dark else brand.WORDMARK_ASSET
            self.image = Image.FromFile(str(brand._STATIC / asset))
            self.track = SolidBrush(Color.FromArgb(45, 90, 110, 125))
            self.bar = SolidBrush(Color.FromArgb(37, 154, 177))
            self.started = time.monotonic()
            self.panel.Paint += self.paint
            self.timer = Timer()
            self.timer.Interval = 30
            self.timer.Tick += self.tick
            self.window.native.Controls.Add(self.panel)
            self.window.native.FormClosed += self.closed
            self.panel.BringToFront()
            self.timer.Start()
            log.info('Startup loader attached to main window %s', self.window.native.Handle)
        except Exception:
            log.exception('Native loading panel unavailable; using the HTML loading screen')
            self.dispose()

    def paint(self, sender, event):
        scale = float(getattr(self.window.native, '_scale', 1)) or 1
        width = round(208 * scale)
        height = round(width * self.image.Height / self.image.Width)
        x = (self.panel.ClientSize.Width - width) // 2
        y = (self.panel.ClientSize.Height - height - round(31 * scale)) // 2
        event.Graphics.DrawImage(self.image, x, y, width, height)
        top, thickness = y + height + round(28 * scale), max(1, round(3 * scale))
        event.Graphics.FillRectangle(self.track, x, top, width, thickness)
        shift = round(((time.monotonic() - self.started) % 1.5) / 1.5 * (width + 80 * scale) - 80 * scale)
        left, right = max(0, shift), min(width, shift + round(80 * scale))
        if right > left:
            event.Graphics.FillRectangle(self.bar, x + left, top, right - left, thickness)

    def tick(self, sender, event):
        self.panel.Invalidate()

    def closed(self, sender, event):
        self.dispose()

    def ready(self):
        """Reveal the painted dashboard in the same window, on its UI thread."""
        self.finished = True
        if self.panel is None:
            return
        from System import Action
        native = self.window.native
        if native.IsDisposed:
            return
        log.info('Dashboard ready in main window %s', native.Handle)
        if native.InvokeRequired:
            native.Invoke(Action(self.dispose))
        else:
            self.dispose()

    def dispose(self):
        self.finished = True
        if self.timer is not None:
            self.timer.Stop()
            self.timer.Dispose()
            self.timer = None
        if self.panel is not None:
            self.panel.Dispose()
            self.panel = None
        for name in ('image', 'track', 'bar'):
            resource = getattr(self, name)
            if resource is not None:
                resource.Dispose()
                setattr(self, name, None)
