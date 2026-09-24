"""Thread artifacts rail: input artifacts (owner attachments) vs output artifacts (agent files).

Covers the internal-artifact filter (proposals/threads/memory/underscore files are plumbing, not
deliverables) and the input/output split the rail renders.
"""
import json
from types import SimpleNamespace
from pathlib import Path
from armada import runner, webui


def test_is_internal_artifact_filters_plumbing(tmp_path):
    ad = tmp_path / "agents" / "warren"
    ad.mkdir(parents=True)
    # inside the agent dir: plumbing → internal
    assert runner._is_internal_artifact(str(ad / "jobs" / "_pending" / "x.json"), ad)
    assert runner._is_internal_artifact(str(ad / "threads" / "main" / "messages.jsonl"), ad)
    assert runner._is_internal_artifact(str(ad / "memory" / "note.md"), ad)
    assert runner._is_internal_artifact(str(ad / "_ledger.jsonl"), ad)
    # a real deliverable the agent wrote outside its own dir → NOT internal
    assert not runner._is_internal_artifact(str(tmp_path / "Hand" / "assets.md"), ad)
    # a plain file directly in the agent dir → NOT internal
    assert not runner._is_internal_artifact(str(ad / "report.xlsx"), ad)


def test_thread_artifacts_splits_inputs_and_outputs(tmp_path):
    ad = tmp_path / "agents" / "warren"
    ad.mkdir(parents=True)
    deliverable = tmp_path / "Hand" / "report.xlsx"
    deliverable.parent.mkdir(parents=True)
    deliverable.write_text("x", encoding="utf-8")
    msgs = [
        {"role": "user", "content": "make it",
         "attachments": [{"kind": "image", "name": "in.png", "file": "abc.png"},
                         {"kind": "file", "name": "spec.txt"}]},
        {"role": "assistant", "content": "done",
         "outputs": [{"kind": "output", "name": "report.xlsx", "path": str(deliverable)},
                     {"kind": "output", "name": "gone.txt", "path": str(tmp_path / "nope.txt")}]},
    ]
    ins, outs = webui._thread_artifacts(ad, "warren", "main", msgs)
    assert [i["name"] for i in ins] == ["in.png", "spec.txt"]
    assert ins[0]["url"].startswith("/thread-file?")          # image is viewable
    assert [o["name"] for o in outs] == ["report.xlsx", "gone.txt"]
    assert outs[0]["exists"] is True                           # on disk → revealable
    assert outs[1]["exists"] is False                          # missing → dimmed, not clickable


def test_fs_snapshot_sees_deliverables_not_plumbing(tmp_path):
    ad = tmp_path / "agents" / "strategy"
    (ad / "jobs" / "_pending").mkdir(parents=True)
    (ad / "threads" / "main").mkdir(parents=True)
    (ad / "memory").mkdir(parents=True)
    # a real deliverable written into the agent dir root (e.g. by Bash) — must be seen
    (ad / "Test PDF1.pdf").write_text("%PDF-1.4", encoding="utf-8")
    # plumbing the walk must prune
    (ad / "jobs" / "_pending" / "x.json").write_text("{}", encoding="utf-8")
    (ad / "threads" / "main" / "messages.jsonl").write_text("{}", encoding="utf-8")
    (ad / "memory" / "note.md").write_text("x", encoding="utf-8")
    (ad / "_scratch.tmp").write_text("x", encoding="utf-8")
    snap = runner._fs_snapshot(ad)
    names = {Path(p).name for p in snap}
    assert "Test PDF1.pdf" in names
    assert names.isdisjoint({"x.json", "messages.jsonl", "note.md", "_scratch.tmp"})


def test_gather_artifacts_across_realm(tmp_path):
    td = tmp_path / "agents" / "ray" / "threads" / "main"
    td.mkdir(parents=True)
    deliverable = tmp_path / "agents" / "ray" / "report.pdf"
    deliverable.write_text("%PDF", encoding="utf-8")
    msgs = [
        {"role": "user", "ts": "2026-09-01T10:00:00+02:00", "content": "hi",
         "attachments": [{"kind": "file", "name": "brief.txt"}]},
        {"role": "assistant", "ts": "2026-09-02T10:00:00+02:00", "content": "done",
         "outputs": [{"kind": "output", "name": "report.pdf", "path": str(deliverable)}]},
    ]
    (td / "messages.jsonl").write_text("\n".join(json.dumps(m) for m in msgs), encoding="utf-8")
    realm = SimpleNamespace(agents=[SimpleNamespace(id="ray", display="Ray")])
    rows = webui._gather_artifacts(realm, tmp_path)
    assert {r["type"] for r in rows} == {"input", "output"}
    out = next(r for r in rows if r["type"] == "output")
    assert out["owner"] == "Ray" and out["ext"] == "pdf" and out["exists"] is True and out["thread"] == "Main"
    inp = next(r for r in rows if r["type"] == "input")
    assert inp["name"] == "brief.txt" and inp["path"] == ""      # a bare file ref has no on-disk path
    assert rows[0]["date_iso"] >= rows[-1]["date_iso"]           # newest-touched first


def test_capability_usage_matching(tmp_path):
    rr = tmp_path
    ad = tmp_path / "agents" / "ray"
    ad.mkdir(parents=True)
    (rr / "realm.json").write_text(json.dumps({"toolkit": {
        "connectors": [{"id": "telegram", "name": "Telegram"}],
        "plugins": [{"id": "finance", "name": "Finance"}]}}), encoding="utf-8")
    # The index covers what the agent may USE, so the grants have to exist for the matching itself
    # to be what's under test here. (Coverage of the grant rule lives in test_capabilities.py.)
    (ad / "agent.json").write_text(json.dumps({"id": "ray", "toolkit": {
        "connectors": [{"id": "telegram", "name": "Telegram"}],
        "plugins": [{"id": "finance", "name": "Finance"}]}}), encoding="utf-8")
    idx = runner._capability_index(rr, ad)
    # a real MCP tool call to the telegram server → the Telegram connector counts as used
    hits = runner._match_capabilities("mcp__telegram__send_message", {}, idx)
    assert [(k, c["name"]) for k, c in hits] == [("connectors", "Telegram")]
    # built-in tools are NOT capabilities — no false positive (the old keyword bug)
    assert runner._match_capabilities("Bash", {"command": "echo finance data owner"}, idx) == []
    assert runner._match_capabilities("Write", {"file_path": "x.pdf"}, idx) == []


def test_thread_caps_used_reads_persisted(tmp_path):
    msgs = [
        {"role": "user", "content": "what are our goals?"},
        {"role": "assistant", "content": "here they are"},          # used nothing → nothing shows
    ]
    assert webui._thread_caps_used(msgs) == {}
    msgs2 = [
        {"role": "assistant", "content": "sent",
         "caps_used": [{"type": "connectors", "id": "telegram", "name": "Telegram"}]},
        {"role": "assistant", "content": "again",
         "caps_used": [{"type": "connectors", "id": "telegram", "name": "Telegram"}]},   # dedup
    ]
    used = webui._thread_caps_used(msgs2)
    assert list(used) == ["connectors"] and len(used["connectors"]) == 1


def test_touch_last_thread_persists(tmp_path):
    ad = tmp_path / "agents" / "ray"
    (ad / "threads").mkdir(parents=True)
    webui._touch_last_thread(ad, "taxes")
    meta = json.loads((ad / "threads" / "meta.json").read_text(encoding="utf-8"))
    assert meta["last"] == "taxes"


def test_thread_artifacts_dedupes(tmp_path):
    ad = tmp_path / "agents" / "warren"
    ad.mkdir(parents=True)
    msgs = [
        {"role": "assistant", "outputs": [{"kind": "output", "name": "a.md", "path": "/x/a.md"}]},
        {"role": "assistant", "outputs": [{"kind": "output", "name": "a.md", "path": "/x/a.md"}]},
    ]
    _, outs = webui._thread_artifacts(ad, "warren", "main", msgs)
    assert len(outs) == 1
