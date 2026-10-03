"""Windows notification-area icon for a hidden Armada window.

Uses the WinForms runtime already shipped with pywebview; no second tray package or
background helper process is needed. The WinForms message loop lives on its own STA thread.
"""
from __future__ import annotations

import logging
import sys
import threading

from . import brand

log = logging.getLogger(__name__)


class Tray:
    def __init__(self, show, quit_app):
        self.show = show
        self.quit_app = quit_app
        self._context = None
        self._icon = None
        self._thread = None

    def start(self):
        if sys.platform != "win32":
            return False
        ready = threading.Event()
        result = {"ok": False}

        def run():
            try:
                import clr
                clr.AddReference("System.Windows.Forms")
                clr.AddReference("System.Drawing")
                from System.Drawing import Icon
                from System.Windows.Forms import Application, ApplicationContext, ContextMenuStrip, NotifyIcon

                menu = ContextMenuStrip()
                open_item = menu.Items.Add("Open Armada")
                exit_item = menu.Items.Add("Quit Armada")
                open_item.Click += lambda sender, args: self.show()
                exit_item.Click += lambda sender, args: self.quit_app()
                self._icon = NotifyIcon()
                native_icon = brand.native_icon(32)
                self._icon.Icon = native_icon
                self._icon.Text = "Armada — open in the tray"
                self._icon.ContextMenuStrip = menu
                self._icon.DoubleClick += lambda sender, args: self.show()
                self._context = ApplicationContext()
                self._icon.Visible = True
                result["ok"] = True
                ready.set()
                Application.Run(self._context)
            except Exception:
                log.exception("Could not start Armada's tray icon")
                ready.set()
            finally:
                if self._icon:
                    self._icon.Visible = False
                    self._icon.Dispose()
                if 'native_icon' in locals():
                    native_icon.Dispose()

        try:
            import clr
            clr.AddReference("System")
            from System.Threading import Thread, ThreadStart, ApartmentState
            self._thread = Thread(ThreadStart(run))
            self._thread.IsBackground = True
            self._thread.SetApartmentState(ApartmentState.STA)
            self._thread.Start()
        except Exception:
            log.exception("Could not initialize Armada's tray thread")
            return False
        ready.wait(5)
        return result["ok"]

    def stop(self):
        if self._context:
            try:
                self._context.ExitThread()
            except Exception:
                log.debug("Tray message loop already stopped", exc_info=True)
        if self._thread:
            try:
                self._thread.Join(3000)
            except Exception:
                log.debug("Tray thread already stopped", exc_info=True)
