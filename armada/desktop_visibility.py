"""Nonblocking close-to-tray/restore transitions, with the newest request winning.

WinForms close callbacks run on its UI thread. Tray callbacks run on a different
STA thread. Neither may wait for the other's message loop or a WebView2 result.
"""
from __future__ import annotations

import logging
import sys
import threading
import time

log = logging.getLogger(__name__)


class DesktopVisibility:
    def __init__(self, window, save_state, *, post=None, apply=None, save_timeout=.4):
        self.window = window
        self.save_state = save_state
        self._post = post or self._native_post
        self._apply = apply or self._native_apply
        self._save_timeout = save_timeout
        self._lock = threading.Lock()
        self._snapshot_lock = threading.Lock()
        self._generation = 0
        self._wanted = None
        self._stopped = False

    def show(self):
        self._request(True, False)

    def hide(self, *, save=True):
        self._request(False, save)

    def hide_if_minimized(self):
        # pywebview delivers resize events on worker threads. A delayed minimize
        # notification must not undo a more recent native restore.
        def check():
            from System.Windows.Forms import FormWindowState
            if not self.window.native.IsDisposed and self.window.native.WindowState == FormWindowState.Minimized:
                self.hide(save=False)
        try:
            self._post(check)
        except Exception:
            log.exception('Could not queue desktop minimize check')

    def stop(self):
        with self._lock:
            self._stopped = True
            self._generation += 1

    def _request(self, visible, save):
        with self._lock:
            if self._stopped or (not visible and self._wanted is False):
                return
            self._generation += 1
            generation = self._generation
            self._wanted = visible
        log.info('Desktop visibility requested: %s (%s)', 'show' if visible else 'tray', generation)
        if save:
            # Save before hiding so WebView2 does not throttle an in-flight snapshot.
            # One stuck renderer can leave at most one snapshot worker behind.
            threading.Thread(target=self._save_then_hide, args=(generation,), daemon=True).start()
        else:
            self._queue(visible, generation)

    def _save_then_hide(self, generation):
        if self._snapshot_lock.acquire(blocking=False):
            done = threading.Event()

            def capture():
                try:
                    self.save_state()
                except Exception:
                    log.exception('Desktop tray snapshot failed')
                finally:
                    self._snapshot_lock.release()
                    done.set()

            threading.Thread(target=capture, daemon=True).start()
            if not done.wait(self._save_timeout):
                log.warning('Desktop snapshot timed out; continuing to tray')
        self._queue(False, generation)

    def _queue(self, visible, generation):
        started = time.monotonic()

        def apply():
            with self._lock:
                if self._stopped or generation != self._generation:
                    return  # A restore/quit superseded this delayed hide.
            try:
                self._apply(visible)
                log.info('Desktop visibility applied: %s (%s, %.3fs)',
                         'show' if visible else 'tray', generation, time.monotonic() - started)
            except Exception:
                with self._lock:
                    if generation == self._generation:
                        self._wanted = None  # Permit a retry after a native failure.
                log.exception('Could not %s desktop window', 'restore' if visible else 'hide')

        try:
            self._post(apply)
        except Exception:
            with self._lock:
                if generation == self._generation:
                    self._wanted = None
            log.exception('Could not queue desktop visibility change')

    def _native_post(self, callback):
        if sys.platform == 'win32':
            from System import Action
            # Always post, even when already on the UI thread: FormClosing must
            # finish cancelling the close before any visibility change is applied.
            self.window.native.BeginInvoke(Action(callback))
        else:
            threading.Thread(target=callback, daemon=True).start()

    def _native_apply(self, visible):
        if sys.platform != 'win32':
            if visible:
                self.window.show()
                self.window.restore()
            else:
                self.window.hide()
            return
        from System.Windows.Forms import FormWindowState
        native = self.window.native
        if native.IsDisposed:
            return
        if visible:
            native.Show()
            if native.WindowState == FormWindowState.Minimized:
                native.WindowState = FormWindowState.Normal
            native.Activate()
            native.Invalidate(True)
        else:
            native.Hide()
