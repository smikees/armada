"""Refreshing the capability catalogue must not duplicate or mislabel a server.

Found on the live realm: filesystem, pdf-viewer and windows-mcp each appeared twice — correctly as
Extensions, and again as Connectors claiming to be remote services. The refresh handler filed every
MCP server as a Connector and de-duplicated against the connectors list alone, while capscan sitting
next to it already had the rule right. The catalogue is what grants are made from, so a second entry
for one server means granting the wrong one silently grants nothing.
"""
import json

import pytest

from armada import capscan, serve


class _H(serve.Handler):
    """The handler's request machinery isn't needed — only the two methods under test."""
    def __init__(self, realm):
        self.realm = str(realm)


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "R", "toolkit": {
        "connectors": [{"id": "ibkr", "name": "ibkr", "runs": "service", "touch": ["network"]}],
        "extensions": [{"id": "filesystem", "name": "filesystem", "runs": "code",
                        "touch": ["files", "network"]}],
        "skills": [], "plugins": []}}), encoding="utf-8")
    return r


def _tk(r):
    return json.loads((r / "realm.json").read_text(encoding="utf-8"))["toolkit"]


def _refresh(realm, monkeypatch, servers):
    monkeypatch.setattr(capscan, "list_mcp", lambda: servers)
    return _H(realm)._refresh_connectors({"scope": "realm"})


# --------------------------------------------------------------------------- classification

def test_a_local_server_is_filed_as_an_extension(realm, monkeypatch):
    _refresh(realm, monkeypatch, [{"name": "windows-mcp", "remote": False}])
    tk = _tk(realm)
    assert [c["id"] for c in tk["extensions"]] == ["filesystem", "windows-mcp"]
    assert "windows-mcp" not in [c["id"] for c in tk["connectors"]]


def test_a_remote_server_is_filed_as_a_connector(realm, monkeypatch):
    _refresh(realm, monkeypatch, [{"name": "acme-cloud", "remote": True}])
    tk = _tk(realm)
    assert "acme-cloud" in [c["id"] for c in tk["connectors"]]
    assert "acme-cloud" not in [c["id"] for c in tk["extensions"]]


def test_a_server_already_listed_is_not_added_again(realm, monkeypatch):
    """The exact bug: filesystem is already an Extension, so a refresh must leave it alone."""
    res = _refresh(realm, monkeypatch, [{"name": "filesystem", "remote": False}])
    tk = _tk(realm)
    assert len(tk["extensions"]) == 1 and len(tk["connectors"]) == 1
    assert res["added"] == 0


def test_refresh_is_idempotent(realm, monkeypatch):
    servers = [{"name": "windows-mcp", "remote": False}, {"name": "acme", "remote": True}]
    _refresh(realm, monkeypatch, servers)
    first = _tk(realm)
    _refresh(realm, monkeypatch, servers)
    assert _tk(realm) == first


# --------------------------------------------------------------------------- repairing damage

def test_refresh_removes_a_duplicate_left_by_the_old_handler(realm, monkeypatch):
    js = json.loads((realm / "realm.json").read_text(encoding="utf-8"))
    js["toolkit"]["connectors"].append(
        {"id": "filesystem", "name": "filesystem", "scope": "MCP server (Claude)"})
    (realm / "realm.json").write_text(json.dumps(js), encoding="utf-8")

    res = _refresh(realm, monkeypatch, [])
    tk = _tk(realm)
    assert [c["id"] for c in tk["connectors"]] == ["ibkr"]
    assert [c["id"] for c in tk["extensions"]] == ["filesystem"]
    assert res["removed"] == 1


def test_the_richer_entry_survives_deduplication(realm, monkeypatch):
    """The discovered entry carries runs/touch; the mislabelled copy carried neither. Keeping the
    thin one would lose what the card shows about what it can reach."""
    js = json.loads((realm / "realm.json").read_text(encoding="utf-8"))
    js["toolkit"]["connectors"].append({"id": "filesystem", "name": "filesystem"})
    (realm / "realm.json").write_text(json.dumps(js), encoding="utf-8")
    _refresh(realm, monkeypatch, [])
    kept = _tk(realm)["extensions"][0]
    assert kept["runs"] == "code" and kept["touch"] == ["files", "network"]


def test_deduplication_keeps_distinct_capabilities(realm, monkeypatch):
    _refresh(realm, monkeypatch, [])
    tk = _tk(realm)
    assert len(tk["connectors"]) == 1 and len(tk["extensions"]) == 1


def test_an_entry_without_an_id_or_name_is_left_alone(realm, monkeypatch):
    """Nothing to compare it on; dropping it would be deleting data we can't identify."""
    js = json.loads((realm / "realm.json").read_text(encoding="utf-8"))
    js["toolkit"]["skills"].append({"description": "mystery"})
    (realm / "realm.json").write_text(json.dumps(js), encoding="utf-8")
    _refresh(realm, monkeypatch, [])
    assert len(_tk(realm)["skills"]) == 1


def test_the_handler_no_longer_hardcodes_connectors(realm):
    import inspect
    src = inspect.getsource(serve.Handler._refresh_connectors)
    assert "capscan.reconcile" in src
    assert 'icon": "cap-connector"' not in src, "classification belongs in capscan, not here"
