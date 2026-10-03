"""System memory: a read-only, app-maintained digest regenerated from live realm data, with
snapshot versioning and change-only rewrites.
"""
import json
from armada import memory


def _realm(tmp_path, name="Test Realm", owner="Mihai"):
    (tmp_path / "realm.json").write_text(
        json.dumps({"name": name, "user": {"name": owner, "timezone": "Europe/Madrid"}}),
        encoding="utf-8")


def test_refresh_creates_read_only_digest(tmp_path):
    _realm(tmp_path)
    r = memory.refresh_system_memory(tmp_path, trigger="test")
    assert r["changed"] is True
    p = tmp_path / "memory" / "core-context.md"
    meta, body = memory._frontmatter(p.read_text(encoding="utf-8"))
    assert meta.get("kind") == "system" and meta.get("managed") == "true" and meta.get("updated")
    assert "## Owner" in body and "Mihai" in body and "Test Realm" in body


def test_refresh_is_idempotent_and_versions_on_change(tmp_path):
    _realm(tmp_path)
    memory.refresh_system_memory(tmp_path, trigger="a")
    # nothing changed → no rewrite, no snapshot
    assert memory.refresh_system_memory(tmp_path, trigger="b")["changed"] is False
    vdir = tmp_path / "memory" / memory._SYS_VERSIONS_DIR
    before = len(list(vdir.glob("*.md"))) if vdir.exists() else 0
    # a real change → rewrite + snapshot the prior version + ledger line
    _realm(tmp_path, name="Renamed Realm")
    assert memory.refresh_system_memory(tmp_path, trigger="c")["changed"] is True
    assert len(list(vdir.glob("*.md"))) == before + 1
    assert (vdir / "_ledger.jsonl").exists()


def test_digest_carries_forward_unprobed_env(tmp_path):
    _realm(tmp_path)
    memory.refresh_system_memory(tmp_path, trigger="a")
    # hand-add a GPU line the probe can't produce; a refresh must keep it
    p = tmp_path / "memory" / "core-context.md"
    txt = p.read_text(encoding="utf-8").replace("- App:", "- GPU: Test GPU 9000\n- App:")
    p.write_text(txt, encoding="utf-8")
    body = memory.system_digest(tmp_path)
    assert "Test GPU 9000" in body
