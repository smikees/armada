"""Backspace-as-back.

Browsers dropped this binding because it destroyed people's typing: Backspace meant "delete a
character", focus wasn't where they assumed, and the page navigated away. So the guards are the
feature. The behavioural checks run in node against a DOM stub (navkeys_harness.js) — asserting on
the source text wouldn't tell us whether a guard actually fires.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_JS = _HERE.parents[0] / "armada" / "webui" / "static" / "js" / "navkeys.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_every_guard_behaves(capsys):
    r = subprocess.run(["node", str(_HERE / "navkeys_harness.js")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"guard failures:\n{r.stdout}\n{r.stderr}"


def test_the_binding_is_loaded_on_every_page():
    layout = (_JS.parents[2] / "layout.py").read_text(encoding="utf-8")
    assert "_NAVKEYS_JS" in layout


def test_it_only_binds_backspace():
    src = _JS.read_text(encoding="utf-8")
    assert "e.key!=='Backspace'" in src


def test_it_explains_why_the_guards_exist():
    """This binding is famous for losing people's work; the next person to edit it should know
    that before they simplify a guard away."""
    src = _JS.read_text(encoding="utf-8").lower()
    assert "browsers removed this" in src
