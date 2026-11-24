"""Real HWND stacking on a private desktop, never the owner's visible desktop."""
import ctypes
from ctypes import wintypes as w
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows HWND ordering')
def test_background_refresh_keeps_decorations_below_foreground_window():
    from armada.thread_frame import _api, _Shadow
    from armada.thread_edge import Edge

    def exercise():
        user, _ = _api()
        user.CreateDesktopW.restype = w.HANDLE
        user.CreateDesktopW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.LPVOID, w.DWORD, w.DWORD, w.LPVOID]
        user.SetThreadDesktop.argtypes = [w.HANDLE]
        user.CloseDesktop.argtypes = [w.HANDLE]
        user.GetThreadDesktop.restype = w.HANDLE
        user.GetThreadDesktop.argtypes = [w.DWORD]
        kernel = ctypes.WinDLL('kernel32')
        original = user.GetThreadDesktop(kernel.GetCurrentThreadId())
        desktop = user.CreateDesktopW('armada-stacking-'+str(kernel.GetCurrentThreadId()), None, None, 0, 0x01ff, None)
        assert desktop and user.SetThreadDesktop(desktop)
        handles = []
        try:
            def create(owner=None):
                handle = user.CreateWindowExW(0x080800A0 if owner else 0, 'Static', '', 0x80000000,
                                             50, 50, 500, 600, owner, None, None, None)
                assert handle
                handles.append(handle)
                user.ShowWindow(handle, 4)
                return handle

            back, front = create(), create()
            native = SimpleNamespace(Handle=SimpleNamespace(ToInt64=lambda: back), Left=50, Top=50,
                                     ClientSize=SimpleNamespace(Width=500, Height=600), _scale=1,
                                     Visible=True, WindowState='Normal', IsDisposed=False)
            shadow = _Shadow.__new__(_Shadow)
            shadow.native, shadow.user, shadow.handle = native, user, create(back)
            shadow.size, shadow.bitmap = (500, 600, 1), None
            edge = Edge.__new__(Edge)
            edge.native, edge.user, edge.handle = native, user, create(back)
            edge.closed, edge.size, edge.bitmap = False, (500, 600, 1), object()

            def above(upper, lower):
                current = lower
                for _ in range(30):
                    current = user.GetWindow(current, 3)
                    if not current:
                        return False
                    if current == upper:
                        return True
                raise AssertionError('Window-order cycle')

            def check():
                assert above(front, back), 'Refreshing a background frame raised its owner'
                for decoration in (shadow.handle, edge.handle):
                    assert above(front, decoration), 'Background decoration covers the foreground thread'
                    assert above(decoration, back), 'Decoration must stay above its own clipped window'

            # Delayed initialization after another restored thread is already in front.
            for _ in range(3):
                shadow.refresh()
                edge.position()
                check()
            # Hidden/minimized owners, re-show, movement and late perimeter captures.
            for visible, state in ((False, 'Normal'), (True, 'Minimized'), (True, 'Normal')):
                native.Visible, native.WindowState = visible, state
                native.Left += 20
                shadow.refresh()
                edge.position()
                check()
            # A user raises the back thread, then selects the other one again.
            user.SetWindowPos(back, None, 0, 0, 0, 0, 0x0013)
            shadow.refresh()
            edge.position()
            assert above(shadow.handle, back) and above(edge.handle, back)
            assert above(back, front)
            user.SetWindowPos(front, None, 0, 0, 0, 0, 0x0013)
            edge.position()
            shadow.refresh()
            check()
        finally:
            for handle in reversed(handles):
                user.DestroyWindow(handle)
            assert user.SetThreadDesktop(original)
            assert user.CloseDesktop(desktop)

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(exercise).result(timeout=20)
