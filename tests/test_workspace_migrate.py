"""Migrating a realm built before the workspace setting existed.

This rewrites the owner's own prompt text across every job in the realm, so it previews by default,
refuses to leave a job file unparseable, and touches nothing but jobs.
"""
import json

from armada import workspace


def _realm(tmp_path, jobs, ws=None):
    r = tmp_path / "realm"
    for agent, js in jobs.items():
        (r / "agents" / agent / "jobs").mkdir(parents=True)
        for jid, prompt in js.items():
            (r / "agents" / agent / "jobs" / f"{jid}.json").write_text(
                json.dumps({"id": jid, "name": jid, "prompt": prompt}, indent=2), encoding="utf-8")
    cfg = {"name": "R"}
    if ws:
        cfg["workspace"] = ws
    r.mkdir(parents=True, exist_ok=True)
    (r / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    return r


def _prompt(r, agent, jid):
    return json.loads((r / "agents" / agent / "jobs" / f"{jid}.json").read_text(encoding="utf-8"))["prompt"]


def test_preview_changes_nothing_on_disk(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "read D:\\Work\\Finance\\x.csv"}})
    res = workspace.migrate(r, "D:\\Work")
    assert res["ok"] and res["refs"] == 1 and res["applied"] is False
    assert _prompt(r, "warren", "a") == "read D:\\Work\\Finance\\x.csv", "preview wrote to disk"


def test_apply_rewrites_the_prompts(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "read D:\\Work\\Finance\\x.csv"}})
    res = workspace.migrate(r, "D:\\Work", apply=True)
    assert res["applied"] is True and res["refs"] == 1
    assert _prompt(r, "warren", "a") == "read {workspace}\\Finance\\x.csv"


def test_the_file_is_still_a_valid_job_afterwards(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "D:\\Work\\a and D:/Work/b and **D:\\Work**"}})
    workspace.migrate(r, "D:\\Work", apply=True)
    d = json.loads((r / "agents" / "warren" / "jobs" / "a.json").read_text(encoding="utf-8"))
    assert d["id"] == "a" and d["name"] == "a"
    assert "D:\\Work" not in d["prompt"] and "D:/Work" not in d["prompt"]


def test_it_reports_per_file_counts_across_agents(tmp_path):
    r = _realm(tmp_path, {
        "warren": {"a": "D:\\Work\\x", "b": "D:\\Work\\y and D:\\Work\\z"},
        "galen": {"c": "nothing here"},
    })
    res = workspace.migrate(r, "D:\\Work")
    paths = {f["path"]: f["refs"] for f in res["files"]}
    assert paths == {"warren/a.json": 1, "warren/b.json": 2}, paths
    assert res["refs"] == 3 and res["changed"] == 2


def test_untouched_jobs_are_not_listed(tmp_path):
    r = _realm(tmp_path, {"warren": {"clean": "no paths"}})
    res = workspace.migrate(r, "D:\\Work")
    assert res["files"] == [] and res["refs"] == 0


def test_history_is_not_rewritten(tmp_path):
    """A thread records what an agent was actually told. That was a real path at the time, and
    editing the past to look portable would be forging the record."""
    r = _realm(tmp_path, {"warren": {"a": "D:\\Work\\x"}})
    th = r / "agents" / "warren" / "threads" / "main"
    th.mkdir(parents=True)
    hist = th / "messages.jsonl"
    hist.write_text('{"role":"user","content":"look in D:\\\\Work\\\\x"}\n', encoding="utf-8")
    runs = r / "agents" / "warren" / "runs"
    runs.mkdir()
    (runs / "warren.jsonl").write_text('{"task":"a","summary":"wrote D:\\\\Work\\\\x"}\n', encoding="utf-8")

    workspace.migrate(r, "D:\\Work", apply=True)
    assert "D:\\\\Work" in hist.read_text(encoding="utf-8")
    assert "D:\\\\Work" in (runs / "warren.jsonl").read_text(encoding="utf-8")


def test_memory_and_mandates_are_left_alone(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "D:\\Work\\x"}})
    m = r / "agents" / "warren" / "memory"
    m.mkdir(parents=True)
    note = m / "note.md"
    note.write_text("my files are in D:\\Work\\Finance", encoding="utf-8")
    workspace.migrate(r, "D:\\Work", apply=True)
    assert "D:\\Work\\Finance" in note.read_text(encoding="utf-8")


def test_no_root_is_refused_rather_than_guessed(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "D:\\Work\\x"}})
    res = workspace.migrate(r, "")
    assert res["ok"] is False and "error" in res
    assert _prompt(r, "warren", "a") == "D:\\Work\\x"


def test_migrating_twice_is_harmless(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "D:\\Work\\x"}})
    workspace.migrate(r, "D:\\Work", apply=True)
    second = workspace.migrate(r, "D:\\Work", apply=True)
    assert second["refs"] == 0
    assert _prompt(r, "warren", "a") == "{workspace}\\x"


def test_set_root_persists_and_reports_whether_it_exists(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "x"}})
    target = tmp_path / "newwork"
    target.mkdir()
    res = workspace.set_root(r, str(target))
    assert res["ok"] and res["exists"] is True
    assert workspace.root(r) == str(target)
    # and the rest of realm.json survives
    assert json.loads((r / "realm.json").read_text(encoding="utf-8"))["name"] == "R"


def test_set_root_strips_a_trailing_separator(tmp_path):
    r = _realm(tmp_path, {"warren": {"a": "x"}})
    workspace.set_root(r, "D:\\Work\\")
    assert workspace.root(r) == "D:\\Work"


def test_dashboard_section_assets_are_migrated(tmp_path):
    """A section pointing at a local asset folder is as machine-bound as a job prompt."""
    r = _realm(tmp_path, {"warren": {"a": "x"}})
    cfg = json.loads((r / "realm.json").read_text(encoding="utf-8"))
    cfg["sections"] = [{"name": "Digest", "assets": "D:\\Work\\Development\\digest", "entry": "index.html"},
                       {"name": "Usage", "widget": "usage"}]
    (r / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")

    res = workspace.migrate(r, "D:\\Work", apply=True)
    out = json.loads((r / "realm.json").read_text(encoding="utf-8"))
    assert out["sections"][0]["assets"] == "{workspace}\\Development\\digest"
    assert out["sections"][1] == {"name": "Usage", "widget": "usage"}, "untouched sections must survive"
    assert any("realm.json" in f["path"] for f in res["files"])


def test_exported_from_is_left_as_a_record(tmp_path):
    """Provenance, not configuration: it says where this realm came from, and that stays true."""
    r = _realm(tmp_path, {"warren": {"a": "x"}})
    cfg = json.loads((r / "realm.json").read_text(encoding="utf-8"))
    cfg["exported_from"] = "D:\\Work\\Hand"
    (r / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    workspace.migrate(r, "D:\\Work", apply=True)
    assert json.loads((r / "realm.json").read_text(encoding="utf-8"))["exported_from"] == "D:\\Work\\Hand"


def test_end_to_end_move_to_another_machine(tmp_path):
    """The whole point: migrate here, set a different root there, prompts resolve."""
    r = _realm(tmp_path, {"warren": {"a": "read D:\\Work\\Finance\\x.csv"}})
    workspace.migrate(r, "D:\\Work", apply=True)
    workspace.set_root(r, "C:\\Users\\m\\Work")
    assert workspace.expand(_prompt(r, "warren", "a"), r) == "read C:\\Users\\m\\Work\\Finance\\x.csv"
