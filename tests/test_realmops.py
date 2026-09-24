"""Realm lifecycle: archive, export, delete.

Delete is the most destructive thing the app can do, so most of these are about what it REFUSES
to do: shred without a safety net, remove the realm currently in use, or proceed on a mis-click.
"""
import json
import zipfile
from pathlib import Path

import pytest

from armada import realmops


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "TestRealm"
    (r / "agents" / "finance" / "runs").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "t"}), encoding="utf-8")
    (r / "agents" / "finance" / "agent.json").write_text("{}", encoding="utf-8")
    (r / "agents" / "finance" / "runs" / "log.jsonl").write_text("{}\n", encoding="utf-8")
    (r / "__pycache__").mkdir()
    (r / "__pycache__" / "junk.pyc").write_bytes(b"\x00")
    return r


# ---- export -----------------------------------------------------------------------------------

def test_export_captures_the_whole_realm(realm):
    r = realmops.export(realm)
    assert r["ok"] and Path(r["path"]).is_file()
    names = zipfile.ZipFile(r["path"]).namelist()
    assert any(n.endswith("realm.json") for n in names)
    assert any(n.endswith("agent.json") for n in names)
    assert any(n.endswith("log.jsonl") for n in names)


def test_export_skips_caches(realm):
    names = zipfile.ZipFile(realmops.export(realm)["path"]).namelist()
    assert not any("__pycache__" in n for n in names), "caches aren't worth moving between machines"


def test_export_paths_are_rooted_at_the_realm_folder(realm):
    """So unzipping recreates the realm as a folder rather than spilling into the target."""
    names = zipfile.ZipFile(realmops.export(realm)["path"]).namelist()
    assert all(n.startswith("TestRealm/") for n in names)


def test_export_does_not_modify_the_realm(realm):
    before = sorted(p.name for p in realm.rglob("*"))
    realmops.export(realm)
    after = sorted(p.name for p in realm.rglob("*") if not p.name.endswith(".zip"))
    assert before == after


def test_export_of_a_missing_realm_fails_cleanly(tmp_path):
    r = realmops.export(tmp_path / "gone")
    assert r["ok"] is False and r["error"]


# ---- delete -----------------------------------------------------------------------------------

def test_delete_refuses_the_realm_in_use(realm):
    r = realmops.delete(realm, current_realm=realm)
    assert r["ok"] is False and "switch" in r["error"].lower()
    assert realm.is_dir(), "the folder must be untouched"


def test_delete_refuses_a_missing_folder(tmp_path):
    assert realmops.delete(tmp_path / "gone")["ok"] is False


def test_delete_does_not_escalate_to_a_permanent_wipe(realm, monkeypatch):
    """If the Recycle Bin path fails, stop — don't quietly upgrade to an unrecoverable delete."""
    monkeypatch.setattr(realmops, "_recycle", lambda p: {"ok": False, "error": "shell said no"})
    r = realmops.delete(realm)
    assert r["ok"] is False
    assert realm.is_dir(), "a failed safe delete must leave the realm alone"


def test_delete_uses_the_recycle_bin_when_it_can(realm, monkeypatch):
    seen = {}
    monkeypatch.setattr(realmops, "_recycle", lambda p: seen.setdefault("p", p) and None or {"ok": True})
    r = realmops.delete(realm)
    assert r["ok"] and r["recycled"] is True
    assert realm.is_dir(), "the stubbed recycle didn't really remove it — that's the point"


def test_permanent_delete_is_opt_in(realm, monkeypatch):
    monkeypatch.setattr(realmops, "_recycle", lambda p: {"ok": False, "error": "no-recycle-bin"})
    r = realmops.delete(realm, permanent=True)
    assert r["ok"] and r["recycled"] is False and not realm.exists()


def test_no_recycle_bin_platform_falls_back(realm, monkeypatch):
    """On a platform without one, deleting still works rather than being impossible — but only
    because there's no safe option, not because the safe one failed."""
    monkeypatch.setattr(realmops, "_recycle", lambda p: {"ok": False, "error": "no-recycle-bin"})
    r = realmops.delete(realm)
    assert r["ok"] and r["recycled"] is False and not realm.exists()


def test_recycle_is_a_no_op_off_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(realmops.os, "name", "posix")
    assert realmops._recycle(tmp_path)["error"] == "no-recycle-bin"


# ---- the confirmation gate (server side) -------------------------------------------------------

def test_delete_endpoint_requires_the_folder_name_typed_back():
    import inspect
    from armada import serve
    src = inspect.getsource(serve.Handler._realm_delete)
    assert 'confirm.lower() != p.name.lower()' in src, "a mis-click must not be able to delete"


def test_realm_management_is_folded_inside_advanced():
    """Delete is the most destructive thing here, so it sits behind a deliberate expand rather
    than in the open where a stray click can reach it."""
    from armada.webui import pages
    src = Path(pages.__file__).read_text(encoding="utf-8")
    # slice forward FROM the Advanced block — the file has other <details> in it now, and anchoring
    # the end on the first "</details>')" anywhere in the file matched one of those instead
    start = src.index("<details class=\"mc-frame\"")
    adv = src[start:src.index("</details>')", start)]
    assert "_realm_manage_box" in adv, "manage-realm must render inside the Advanced block"
    assert "Manage this realm" in adv


def test_archive_endpoint_touches_no_files():
    import inspect
    from armada import serve
    src = inspect.getsource(serve.Handler._realm_archive)
    for destructive in ("rmtree", "unlink", "remove(", "realmops"):
        assert destructive not in src, f"archive must not {destructive}"
    assert "_reg_save" in src        # it only edits the registry
