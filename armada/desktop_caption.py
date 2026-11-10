"""Theme the main Windows caption while keeping the system window controls."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import re
import sys

log = logging.getLogger(__name__)

# Windows draws the caption without the title and icon, but keeps the actual
# window title for task switching, accessibility and instance activation.
WTA_NONCLIENT = 1
WTNCA_HIDE_BRANDING = 0x01 | 0x02
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWA_COLOR_DEFAULT = 0xFFFFFFFF


def _colorref(css_color):
    if not isinstance(css_color, str):
        return None
    match = re.fullmatch(r'rgb\((\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})\)', css_color)
    if match is None:
        return None
    red, green, blue = map(int, match.groups())
    if max(red, green, blue) > 255:
        return None
    return red | green << 8 | blue << 16


class MainCaption:
    def __init__(self, window, loader):
        self.window = window
        self.loader = loader
        self.colors = None
        self.set_attribute = None
        if sys.platform == 'win32':
            window.events.before_show += self.mount

    def mount(self):
        try:
            form = self.window.native
            theme = ctypes.windll.uxtheme.SetWindowThemeAttribute
            theme.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
            options = (wintypes.DWORD * 2)(WTNCA_HIDE_BRANDING, WTNCA_HIDE_BRANDING)
            if theme(form.Handle.ToInt64(), WTA_NONCLIENT, options, ctypes.sizeof(options)) != 0:
                log.debug('Windows did not accept the caption visibility flags')
            form._armada_caption = self
            # Custom caption colors are available starting with Windows 11.
            if sys.getwindowsversion().build >= 22000:
                self.set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                self.set_attribute.argtypes = theme.argtypes
                if self.loader.panel is not None:
                    color = self.loader.panel.BackColor
                    background = f'rgb({color.R}, {color.G}, {color.B})'
                    foreground = 'rgb(228, 232, 238)' if color.GetBrightness() < .5 else 'rgb(24, 28, 34)'
                    self.update(background, foreground)
        except Exception:
            log.debug('Native caption styling unavailable', exc_info=True)

    def update(self, background, foreground):
        if self.set_attribute is None:
            return
        colors = (_colorref(background), _colorref(foreground))
        if None in colors:
            return
        try:
            from System import Action
            from System.Windows.Forms import SystemInformation
            form = self.window.native
            if form.IsDisposed:
                return
            if form.InvokeRequired:
                form.BeginInvoke(Action(lambda: self.update(background, foreground)))
                return
            if SystemInformation.HighContrast:
                colors = (DWMWA_COLOR_DEFAULT, DWMWA_COLOR_DEFAULT)
            if colors == self.colors:
                return
            for attribute, color in zip((DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR), colors):
                value = wintypes.DWORD(color)
                if self.set_attribute(form.Handle.ToInt64(), attribute, ctypes.byref(value), ctypes.sizeof(value)) != 0:
                    return
            self.colors = colors
        except Exception:
            log.debug('Could not update the native caption colors', exc_info=True)
