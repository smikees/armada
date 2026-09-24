"""Characterization tests for the business rules currently living inside serve.py handlers.

These pin the OBSERVABLE behavior (request in → realm.json / dashboard.json state out) of the
section and dashboard endpoints, so that when P4 extracts this logic into a domain/ layer the
behavior is provably unchanged. They exercise the real HTTP surface against a fresh, isolated
fixture realm.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from tests import golden_support as g


@pytest.fixture()
def served(tmp_path):
    realm = g.build_fixture(tmp_path / "realm")
    with g.ServedRealm(realm) as srv:
        yield srv


def _sections(realm: str) -> list:
    cfg = json.loads((Path(realm) / "realm.json").read_text(encoding="utf-8-sig"))
    return cfg.get("sections", [])


# ---- sections: add / rename / reorder / delete -------------------------------------------------

def test_add_section_appends_and_returns_index(served):
    r = served.post("/api/add-section", {"name": "Digest", "src": "shared/digest.html"})
    assert r.get("ok") is True
    secs = _sections(served.realm)
    assert secs[-1]["name"] == "Digest"
    assert secs[-1].get("path") == "shared/digest.html"
    assert r.get("index") == len(secs) - 1


def test_add_section_url_vs_path(served):
    served.post("/api/add-section", {"name": "Ext", "src": "https://example.com"})
    assert _sections(served.realm)[-1].get("url") == "https://example.com"


def test_rename_section_preserves_target(served):
    # fixture ships one section: {name: Handbook, path: shared/handbook.md}
    r = served.post("/api/rename-section", {"index": 0, "name": "Guide"})
    assert r.get("ok") is True
    s0 = _sections(served.realm)[0]
    assert s0["name"] == "Guide"
    assert s0.get("path") == "shared/handbook.md"  # target preserved across a rename


def test_rename_section_requires_name(served):
    r = served.post("/api/rename-section", {"index": 0, "name": "   "})
    assert r.get("ok") is False


def test_reorder_sections_permutes(served):
    served.post("/api/add-section", {"name": "B", "src": "shared/b.md"})
    served.post("/api/add-section", {"name": "C", "src": "shared/c.md"})
    names_before = [s["name"] for s in _sections(served.realm)]
    assert names_before == ["Handbook", "B", "C"]
    r = served.post("/api/reorder-sections", {"order": [2, 0, 1]})
    assert r.get("ok") is True
    assert [s["name"] for s in _sections(served.realm)] == ["C", "Handbook", "B"]


def test_reorder_rejects_non_permutation(served):
    r = served.post("/api/reorder-sections", {"order": [0, 0]})
    assert r.get("ok") is False
    assert _sections(served.realm)[0]["name"] == "Handbook"  # unchanged


def test_delete_section_removes(served):
    served.post("/api/add-section", {"name": "B", "src": "shared/b.md"})
    r = served.post("/api/delete-section", {"index": 0})
    assert r.get("ok") is True
    assert [s["name"] for s in _sections(served.realm)] == ["B"]


# ---- dashboard save --------------------------------------------------------------------------

def test_save_dashboard_persists(served):
    layout = {"single": {"register": True}, "order": ["register", "usage"],
              "spans": {"register": 20, "usage": 10}, "heights": {}, "threads": []}
    r = served.post("/api/save-dashboard", layout)
    assert r.get("ok") is True
    saved = json.loads((Path(served.realm) / "dashboard.json").read_text(encoding="utf-8-sig"))
    assert saved["order"] == ["register", "usage"]
    assert saved["spans"]["register"] == 20
