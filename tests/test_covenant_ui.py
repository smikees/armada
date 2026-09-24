"""The Covenant gets a surface.

It is loaded into every agent's context ahead of their own mandate and tenets — the highest-leverage
text in the realm — and it was the only realm-wide document with no UI at all. Goals have the Goals
page, realm memories have the Memory list, and the terms binding all eight agents were editable only
by opening a file on disk.
"""
import datetime
import inspect
import json
from pathlib import Path

import pytest

from armada import reader, serve
from armada.webui import agentframe as AF
from armada.webui import memoryview as MV
from armada.webui import realmpages as RP

COV = "# The Covenant\n\n## 1. Whose you are\n- Mihai is the only master you serve.\n"


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "Cabinet-realm"
    (r / "agents" / "hand").mkdir(parents=True)
    (r / "memory").mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Cabinet", "owner": "M"}), encoding="utf-8")
    (r / "agents" / "hand" / "agent.json").write_text(
        json.dumps({"id": "hand", "display": "Marcus", "coordinator": True}), encoding="utf-8")
    (r / "tenets.md").write_text(COV, encoding="utf-8")
    return r


class _H(serve.Handler):
    def __init__(self, realm):
        self.realm = str(realm)


# --------------------------------------------------------------------------- the Memory page

def test_the_covenant_is_pinned_on_the_memory_page(realm):
    html = MV._realm_memory(reader.read(str(realm)), realm)
    assert "The Covenant" in html
    assert "binds every minister" in html


def test_it_is_presented_as_editable_unlike_system_memory(realm):
    """System memory is generated and read-only; this is the owner's to write, and says so."""
    html = MV._realm_memory(reader.read(str(realm)), realm)
    assert "Yours to edit" in html
    assert "mcCovSave" in html


def test_it_is_not_rendered_as_a_memory_card(realm):
    """Memory is facts that change; the Covenant is governance that shouldn't. Styling it as a
    card would invite editing it like one and reading it as optional."""
    block = MV._covenant_block(reader.read(str(realm)), realm)
    assert "mc-memcard" not in block and "mcMemDelete" not in block


def test_the_block_summarises_by_section(realm):
    block = MV._covenant_block(reader.read(str(realm)), realm)
    assert "Whose you are" in block


def test_an_absent_covenant_says_so_rather_than_breaking(tmp_path):
    r = tmp_path / "empty-realm"
    (r / "agents").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "R"}), encoding="utf-8")
    block = MV._covenant_block(reader.read(str(r)), r)
    assert "Not written yet" in block


def test_the_editor_is_app_native(realm):
    """House rule: no browser dialogs."""
    modal = MV._covenant_modal()
    assert "window.confirm" not in modal and "alert(" not in modal
    assert 'id="mc-cov-modal"' in modal


# --------------------------------------------------------------------------- saving

def test_saving_writes_the_realm_file(realm):
    res = _H(realm)._save_covenant({"text": "# New terms\n- Be honest.\n"})
    assert res["ok"]
    assert (realm / "tenets.md").read_text(encoding="utf-8") == "# New terms\n- Be honest.\n"


def test_saving_is_bounded(realm):
    res = _H(realm)._save_covenant({"text": "x" * 40_001})
    assert res["ok"] is False
    assert (realm / "tenets.md").read_text(encoding="utf-8") == COV, "a refused save must not write"


def test_an_empty_covenant_is_allowed(realm):
    """Clearing it is a legitimate choice — it just means no realm-wide terms."""
    assert _H(realm)._save_covenant({"text": ""})["ok"] is True


# --------------------------------------------------------------------------- the other placements

def test_the_ministers_page_links_to_it_without_reprinting_it(realm):
    html = RP._realm_ministers(reader.read(str(realm)), realm, datetime.date.today())
    assert "bound by the Covenant" in html
    assert "Mihai is the only master" not in html, "the roster must not become the document"


def test_the_ministers_line_is_absent_when_there_is_no_covenant(tmp_path):
    r = tmp_path / "r2"
    (r / "agents").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "R"}), encoding="utf-8")
    html = RP._realm_ministers(reader.read(str(r)), r, datetime.date.today())
    assert "bound by the Covenant" not in html


def test_the_configure_page_warns_against_duplicating_it():
    """That textarea is where the honesty/loyalty rules would otherwise be pasted into all eight."""
    src = inspect.getsource(AF)
    assert "realm Covenant" in src
    # apostrophes are backslash-escaped inside the f-string, so match a phrase without one
    assert "it already applies" in src


# --------------------------------------------------------------------------- what it governs

def test_the_covenant_reaches_every_agent(realm):
    """The reason it earns a surface at all."""
    from armada import memory
    ad = realm / "agents" / "hand"
    a = json.loads((ad / "agent.json").read_text(encoding="utf-8"))
    assert "The Covenant" in memory.assemble_core(realm, ad, a)
