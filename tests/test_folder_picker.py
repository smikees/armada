"""Folder picker (ADR-009 prerequisite): the app window's native dialog first, tkinter only as the
browser-mode fallback — the installed build's embeddable Python has no tkinter."""
import sys
import types

from armada.routes.realm import RealmRoutes


class _Win:
    def __init__(self, result):
        self.result, self.asked = result, []

    def create_file_dialog(self, kind, *a, **k):
        self.asked.append(kind)
        return self.result


def _fake_webview(monkeypatch, windows):
    wv = types.ModuleType("webview")
    wv.windows = windows
    wv.FileDialog = types.SimpleNamespace(FOLDER=20)
    monkeypatch.setitem(sys.modules, "webview", wv)


def test_uses_the_window_dialog_when_there_is_a_window(monkeypatch):
    w = _Win(("C:\\Users\\me\\ARMADA",))
    _fake_webview(monkeypatch, [w])
    assert RealmRoutes._pick_folder(object()) == {"ok": True, "path": "C:\\Users\\me\\ARMADA"}
    assert w.asked == [20]


def test_cancel_is_not_an_error(monkeypatch):
    _fake_webview(monkeypatch, [_Win(None)])
    assert RealmRoutes._pick_folder(object()) == {"ok": False, "path": ""}


def test_no_window_falls_back_to_tkinter(monkeypatch):
    _fake_webview(monkeypatch, [])
    tk = types.ModuleType("tkinter")
    fd = types.ModuleType("tkinter.filedialog")
    fd.askdirectory = lambda **k: "/home/me/ARMADA"

    class _Tk:
        def withdraw(self): pass
        def attributes(self, *a): pass
        def destroy(self): pass
    tk.Tk = _Tk
    tk.filedialog = fd
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", fd)
    assert RealmRoutes._pick_folder(object()) == {"ok": True, "path": "/home/me/ARMADA"}
