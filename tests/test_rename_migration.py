"""The matcap → armada rename (v0.99.56, ADR-010) loses nothing that was set up under the old name:
the per-machine folder moves, and realms written before it (format v1) are rewritten on open."""
import json
import os
from pathlib import Path

from armada import realmformat, util


def test_data_dir_is_dot_armada_in_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert util.data_dir() == tmp_path / ".armada"


def test_the_old_folder_moves_with_everything_in_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    old = tmp_path / ".matcap"
    (old / "logs").mkdir(parents=True)
    (old / "config.json").write_text('{"app_root": "D:/x"}', encoding="utf-8")
    (old / "realms.json").write_text("[]", encoding="utf-8")
    d = util.data_dir()
    assert (d / "config.json").read_text(encoding="utf-8") == '{"app_root": "D:/x"}'
    assert (d / "realms.json").exists() and (d / "logs").is_dir()
    assert not old.exists()                                   # moved, not copied, when it can be


def test_an_existing_new_folder_is_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".matcap").mkdir(); (tmp_path / ".matcap" / "config.json").write_text("old", encoding="utf-8")
    (tmp_path / ".armada").mkdir(); (tmp_path / ".armada" / "config.json").write_text("new", encoding="utf-8")
    assert (util.data_dir() / "config.json").read_text(encoding="utf-8") == "new"


def test_a_refused_rename_falls_back_to_a_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".matcap").mkdir(); (tmp_path / ".matcap" / "telegram.json").write_text("{}", encoding="utf-8")
    def refuse(self, target):
        raise PermissionError("file in use")
    monkeypatch.setattr(Path, "rename", refuse)
    assert (util.data_dir() / "telegram.json").exists()


def _v1_realm(root: Path) -> Path:
    (root / "agents" / "hand" / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({
        "name": "R", "schema_version": 1,
        "env": {"App": "MATCAP, running locally at 127.0.0.1:8756", "CPU": "x"}}), encoding="utf-8")
    (root / "agents" / "hand" / "jobs" / "refresh.json").write_text(json.dumps({
        "id": "refresh", "kind": "command",
        "run": ["D:\\Work\\Development\\MATCAP\\.venv\\Scripts\\python.exe", "-m", "matcap", "system-refresh", "."]}),
        encoding="utf-8")
    (root / "agents" / "hand" / "jobs" / "str.json").write_text(json.dumps({
        "id": "str", "kind": "command", "run": "python -m matcap validate ."}), encoding="utf-8")
    (root / "agents" / "hand" / "jobs" / "other.json").write_text(json.dumps({
        "id": "other", "kind": "command", "run": ["python", "collect_matcap_stats.py"]}), encoding="utf-8")
    (root / ".matcap").mkdir()
    (root / ".matcap" / "models.json").write_text("{}", encoding="utf-8")
    return root


def test_a_v1_realm_is_brought_to_v2(tmp_path):
    root = _v1_realm(tmp_path / "r")
    res = realmformat.migrate(root)
    assert res["ok"] and res["from"] == 1 and res["to"] == realmformat.CURRENT == 2
    cfg = json.loads((root / "realm.json").read_text(encoding="utf-8"))
    assert cfg["env"]["App"] == "ARMADA, running locally at 127.0.0.1:8756" and cfg["env"]["CPU"] == "x"
    jobs = root / "agents" / "hand" / "jobs"
    refresh = json.loads((jobs / "refresh.json").read_text(encoding="utf-8"))["run"]
    assert refresh[1:3] == ["-m", "armada"]
    assert refresh[0] == "D:\\Work\\Development\\MATCAP\\.venv\\Scripts\\python.exe"   # paths untouched
    assert json.loads((jobs / "str.json").read_text(encoding="utf-8"))["run"] == "python -m armada validate ."
    assert json.loads((jobs / "other.json").read_text(encoding="utf-8"))["run"] == ["python", "collect_matcap_stats.py"]
    assert (root / ".armada" / "models.json").exists() and not (root / ".matcap").exists()


def test_the_step_is_idempotent(tmp_path):
    root = _v1_realm(tmp_path / "r")
    cfg = json.loads((root / "realm.json").read_text(encoding="utf-8"))
    once = realmformat._m1_to_2(dict(cfg), root)
    twice = realmformat._m1_to_2(dict(once), root)
    assert once == twice
