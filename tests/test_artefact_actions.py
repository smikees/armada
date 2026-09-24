"""Artifact row actions: open, reveal-instead-of-run, and delete."""
from pathlib import Path

import pytest

from armada import serve


class _H:
    """Minimal stand-in: only needs the bits the two methods touch."""
    _RUNNABLE = serve.Handler._RUNNABLE
    revealed = None

    def _reveal(self, body):
        self.revealed = body["path"]
        return {"ok": True}

    _open_file = serve.Handler._open_file
    _delete_artefact = serve.Handler._delete_artefact
    # Since 5.8d the two only act inside the realm / its workspace / the app root.
    _artefact_roots = serve.Handler._artefact_roots
    _within_artefact_roots = serve.Handler._within_artefact_roots
    _OUTSIDE = serve.Handler._OUTSIDE
    realm = "."


@pytest.fixture(autouse=True)
def _files_live_in_the_realm(tmp_path, monkeypatch):
    from armada import approot
    monkeypatch.setattr(_H, "realm", str(tmp_path))
    monkeypatch.setattr(approot, "root", lambda: "")


@pytest.mark.parametrize("ext", [".exe", ".bat", ".ps1", ".cmd", ".vbs", ".py", ".lnk", ".reg", ".jar"])
def test_runnable_files_are_revealed_not_opened(tmp_path, monkeypatch, ext):
    """Agents write these files, so the list isn't a trusted source of things to execute. Anything
    runnable must be shown in the folder, never handed to the shell to launch."""
    f = tmp_path / f"payload{ext}"
    f.write_text("x", encoding="utf-8")
    started = []
    monkeypatch.setattr(serve.os, "startfile", lambda p: started.append(p), raising=False)
    h = _H()
    r = h._open_file({"path": str(f)})
    assert r["revealed"] is True and h.revealed == str(f.resolve())
    assert started == []                       # never launched
    assert ext in r["error"]


@pytest.mark.parametrize("ext", [".pdf", ".docx", ".xlsx", ".md", ".png", ".txt", ".csv"])
def test_ordinary_documents_open(tmp_path, monkeypatch, ext):
    f = tmp_path / f"report{ext}"
    f.write_text("x", encoding="utf-8")
    started = []
    monkeypatch.setattr(serve.os, "name", "nt")
    monkeypatch.setattr(serve.os, "startfile", lambda p: started.append(p), raising=False)
    assert _H()._open_file({"path": str(f)})["ok"] is True
    assert started == [str(f.resolve())]


def test_open_rejects_missing_and_empty_paths(tmp_path):
    h = _H()
    assert h._open_file({"path": ""})["ok"] is False
    assert h._open_file({"path": str(tmp_path / "ghost.txt")})["ok"] is False


def test_delete_removes_the_file(tmp_path):
    f = tmp_path / "out.md"
    f.write_text("bye", encoding="utf-8")
    assert _H()._delete_artefact({"path": str(f)})["ok"] is True
    assert not f.exists()


def test_delete_refuses_a_directory(tmp_path):
    d = tmp_path / "folder"
    d.mkdir()
    assert _H()._delete_artefact({"path": str(d)})["ok"] is False
    assert d.exists()                          # must not touch directories


def test_delete_rejects_empty_path():
    assert _H()._delete_artefact({"path": ""})["ok"] is False


def test_row_actions_never_inline_a_path_into_javascript():
    """A Windows path inside a JS string literal is destroyed by escape processing — '\\finance'
    carries a form feed, '\\Work' silently loses its backslash — so the server received a mangled
    path and reported 'file not found on disk'. Paths must ride in data- attributes instead."""
    import re
    from armada.webui import agentcommon
    src = Path(agentcommon.__file__).read_text(encoding="utf-8")
    row = src[src.index('if r["exists"]:'):src.index('cells.append(f\'<td style="padding:6px 8px;'
                                                     'white-space:nowrap;text-align:right"')]
    assert 'data-path="{p}"' in row
    # no onclick in the actions may carry the path variable
    assert not re.search(r"onclick=[^\n]*\{p\}", row)


def test_js_uses_delegated_handlers_with_data_attributes():
    import re
    js = (Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js"
          / "artefacts.js").read_text(encoding="utf-8")
    assert "getAttribute('data-path')" in js
    assert ".mc-art-go" in js and ".mc-art-del" in js
    assert "mcArtConfirm(" in js                              # deletes go through the styled dialog
    # no bare browser confirm()/alert() — ARMADA uses its own dialog and toast (ignore comments)
    code = re.sub(r"//[^\n]*", "", js)
    assert not re.search(r"(?<![\w.])(confirm|alert)\(", code)
