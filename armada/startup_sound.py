"""Quiet desktop-ready cue. Runs off-thread; audio failures cannot affect startup."""
from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
import sys
import threading
import uuid

from . import appconfig

log = logging.getLogger(__name__)
SOUND = Path(__file__).parent / 'webui' / 'static' / 'sounds' / 'startup.mp3'
VOLUME = 120  # MCI uses 0..1000: 12% of this track's normal volume, no system-volume change.
_lock = threading.Lock()
_started = False


def _play_windows():
    alias = 'armada_startup_' + uuid.uuid4().hex
    opened = False
    try:
        send = ctypes.WinDLL('winmm').mciSendStringW
        send.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        send.restype = ctypes.c_uint
        def command(value):
            error = send(value, None, 0, None)
            if error:
                raise OSError(error, 'Startup sound playback unavailable')
        command(f'open "{SOUND.resolve()}" type mpegvideo alias {alias}')
        opened = True
        command(f'setaudio {alias} volume to {VOLUME}')
        command(f'play {alias} wait')
    except Exception:
        log.debug('Could not play the desktop-ready sound', exc_info=True)
    finally:
        if opened:
            try:
                send(f'close {alias}', None, 0, None)
            except Exception:
                log.debug('Could not close the startup sound device', exc_info=True)


def play():
    """Called only after the main desktop's authenticated page is ready, once per launch."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    try:
        if (sys.platform != 'win32' or os.environ.get('ARMADA_NO_EXTERNAL_NOTIFY') == '1'
                or not appconfig.get('startup_sound', True) or not SOUND.is_file()):
            return
        threading.Thread(target=_play_windows, name='armada-startup-sound', daemon=True).start()
    except Exception:
        log.debug('Could not start the desktop-ready sound', exc_info=True)
