"""System memory: a read-only, app-maintained digest regenerated from live realm data, with
snapshot versioning and change-only rewrites.
"""
import json
from armada import memory, runner


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


def test_guardrail_reverts_out_of_bounds_memory_writes(tmp_path):
    rr = tmp_path
    (rr / "memory").mkdir(parents=True)
    (rr / "memory" / "realm-note.md").write_text("original", encoding="utf-8")
    (rr / "agents" / "ray" / "memory").mkdir(parents=True)
    (rr / "agents" / "steve" / "memory").mkdir(parents=True)
    (rr / "agents" / "steve" / "memory" / "steve-note.md").write_text("steve original", encoding="utf-8")
    agent_dir = rr / "agents" / "ray"

    snap = runner._guard_snapshot(rr, agent_dir)
    # ray (the acting agent) makes forbidden writes + one allowed write to its OWN memory
    (rr / "memory" / "realm-note.md").write_text("HACKED", encoding="utf-8")
    (rr / "memory" / "new-realm.md").write_text("injected", encoding="utf-8")
    (rr / "agents" / "steve" / "memory" / "steve-note.md").write_text("HACKED", encoding="utf-8")
    (agent_dir / "memory" / "ray-note.md").write_text("ray's own", encoding="utf-8")

    reverted = runner._guard_restore(snap)
    assert reverted == 3
    assert (rr / "memory" / "realm-note.md").read_text(encoding="utf-8") == "original"     # restored
    assert not (rr / "memory" / "new-realm.md").exists()                                    # removed
    assert (rr / "agents" / "steve" / "memory" / "steve-note.md").read_text(encoding="utf-8") == "steve original"
    assert (agent_dir / "memory" / "ray-note.md").read_text(encoding="utf-8") == "ray's own"  # own memory kept


def test_digest_carries_forward_unprobed_env(tmp_path):
    _realm(tmp_path)
    memory.refresh_system_memory(tmp_path, trigger="a")
    # hand-add a GPU line the probe can't produce; a refresh must keep it
    p = tmp_path / "memory" / "core-context.md"
    txt = p.read_text(encoding="utf-8").replace("- App:", "- GPU: Test GPU 9000\n- App:")
    p.write_text(txt, encoding="utf-8")
    body = memory.system_digest(tmp_path)
    assert "Test GPU 9000" in body
