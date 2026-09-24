"""The shared app-native confirm dialog.

The bug these guard: a second global named mcConfirm with a different signature. Section-delete and
job-proposal-reject call it with an OPTIONS OBJECT; the newer inbox code calls it POSITIONALLY.
Whichever definition loaded last won, and the loser's callers got "[object Object]" as the dialog
title — a broken dialog on a destructive action.
"""
import re
from pathlib import Path

import pytest

_JS = Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js"


def _read(name):
    return (_JS / name).read_text(encoding="utf-8")


def test_only_one_definition_of_the_dialog_exists():
    defs = []
    for f in _JS.glob("*.js"):
        src = f.read_text(encoding="utf-8")
        if re.search(r"(function\s+mcConfirm\s*\(|mcConfirm\s*=\s*function)", src):
            defs.append(f.name)
    assert defs == ["confirm.js"], f"mcConfirm must be defined once, found in {defs}"


def test_the_dialog_accepts_both_call_shapes():
    src = _read("confirm.js")
    assert "typeof title==='object'" in src, "the options-object form must still work"
    for key in ("o.body", "o.confirm", "o.title", "o.danger"):
        assert key in src, f"the options-object form must read {key}"


@pytest.mark.parametrize("name,needle", [
    ("section_edit.js", "mcConfirm({title:'Remove section?'"),
    ("job_proposal.js", "mcConfirm({title:'Reject job proposal?'"),
])
def test_existing_object_form_callers_are_untouched(name, needle):
    """These call sites were correct all along — the fix belongs in the dialog, not in them."""
    assert needle in _read(name)


def test_no_page_carries_a_private_copy():
    """A local definition would shadow the shared one depending on script order — which is exactly
    how this broke."""
    for f in _JS.glob("*.js"):
        if f.name == "confirm.js":
            continue
        src = f.read_text(encoding="utf-8")
        assert "window.mcConfirm=" not in src, f"{f.name} redefines the shared dialog"


def test_the_dialog_is_loaded_for_every_page():
    layout = (_JS.parents[1] / "layout.py").read_text(encoding="utf-8")
    assert "_CONFIRM_JS" in layout


def test_no_browser_dialogs_anywhere_in_the_ui():
    """ARMADA's standing rule: modals are app-native, never the browser's."""
    for f in _JS.glob("*.js"):
        code = re.sub(r"//[^\n]*", "", f.read_text(encoding="utf-8"))
        hit = re.search(r"(?<![\w.])(confirm|alert)\(", code)
        assert not hit, f"{f.name} uses a browser dialog: {hit.group(0)}"
