"""Keep native windows reachable after display topology changes, in physical pixels."""
import logging
import sys

log = logging.getLogger(__name__)


def ensure(window):
    if sys.platform != 'win32':
        return
    try:
        from System import Action
        native=window.native
        if not native.IsDisposed:
            native.BeginInvoke(Action(lambda:recover_native(native)))
    except Exception:
        log.debug('Could not queue window recovery',exc_info=True)


def reachable(bounds, areas):
    x,y,width,height = bounds
    # Enough of the title/drag area must remain on one usable display.
    return any(min(x+width,ax+aw)-max(x,ax) >= min(160,width)
               and min(y+40,ay+ah)-max(y,ay) >= 24 for ax,ay,aw,ah in areas)


def fit(bounds, area, offset=0):
    x,y,width,height = bounds
    ax,ay,aw,ah = area
    width,height = min(width,aw),min(height,ah)
    return (max(ax,min(x+offset,ax+aw-width)),max(ay,min(y+offset,ay+ah-height)),width,height)


def recover_native(native, *, here=False, offset=0):
    from System.Drawing import Rectangle, Size
    from System.Windows.Forms import Screen, Cursor, FormWindowState
    if native.IsDisposed or not native.Visible and not here:
        return
    if native.WindowState == FormWindowState.Minimized and not here:
        return
    areas=[(s.WorkingArea.X,s.WorkingArea.Y,s.WorkingArea.Width,s.WorkingArea.Height) for s in Screen.AllScreens]
    if not areas or not any(aw>0 and ah>0 for _,_,aw,ah in areas):
        return
    rect=native.RestoreBounds if native.WindowState == FormWindowState.Minimized else native.Bounds
    bounds=(rect.X,rect.Y,rect.Width,rect.Height)
    if not here and reachable(bounds,areas):
        return
    screen=Screen.FromPoint(Cursor.Position) if here else Screen.FromRectangle(rect)
    area=screen.WorkingArea
    if area.Width<=0 or area.Height<=0:
        return
    if here:
        bounds=(area.X+40,area.Y+40,bounds[2],bounds[3])
    x,y,width,height=fit(bounds,(area.X,area.Y,area.Width,area.Height),offset)
    native.WindowState=FormWindowState.Normal
    native.MinimumSize=Size(min(native.MinimumSize.Width,area.Width),min(native.MinimumSize.Height,area.Height))
    native.Bounds=Rectangle(x,y,width,height)
    if here:
        native.Show()


class MonitorRecovery:
    def __init__(self, windows):
        self.windows=windows
        self.stopped=False
        self.timer=None
        self.display_handler=None

    def start(self, main):
        self.main=main
        if sys.platform != 'win32':
            return
        from System import Action
        from System.Windows.Forms import Timer
        def install():
            if self.stopped or main.native.IsDisposed or self.timer is not None:
                return
            self.timer=Timer()
            self.timer.Interval=2000
            self.timer.Tick += self.tick
            def display_changed(*_):
                try:
                    if not self.stopped and not main.native.IsDisposed:
                        main.native.BeginInvoke(Action(self.tick))
                except Exception:
                    log.debug('Display-change recovery was superseded by close',exc_info=True)
            self.display_handler=display_changed
            try:
                from Microsoft.Win32 import SystemEvents
                SystemEvents.DisplaySettingsChanged += display_changed
            except Exception:
                self.display_handler=None
                log.debug('Display notifications unavailable; using periodic recovery',exc_info=True)
            self.timer.Start()
            self.tick()
        try:
            main.native.BeginInvoke(Action(install))
        except Exception:
            log.debug('Monitor recovery startup was superseded by close',exc_info=True)

    def tick(self, *_):
        if self.stopped:
            return
        for window in self.windows():
            try:
                recover_native(window.native)
            except Exception:
                log.debug('Could not recover window after display change',exc_info=True)

    def bring_here(self):
        from System import Action
        for index,window in enumerate(self.windows()):
            def move(window=window,index=index):
                try:
                    recover_native(window.native,here=True,offset=20*index)
                except Exception:
                    log.exception('Could not bring window to this display')
            window.native.BeginInvoke(Action(move))

    def stop(self):
        if self.stopped:
            return
        self.stopped=True
        if self.timer is not None:
            from System import Action
            def dispose():
                if self.display_handler is not None:
                    from Microsoft.Win32 import SystemEvents
                    SystemEvents.DisplaySettingsChanged -= self.display_handler
                    self.display_handler=None
                self.timer.Stop()
                self.timer.Tick -= self.tick
                self.timer.Dispose()
            if not self.main.native.IsDisposed:
                if self.main.native.InvokeRequired:
                    self.main.native.BeginInvoke(Action(dispose))
                else:
                    dispose()
