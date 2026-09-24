"""A realm export is a backup. It must contain everything in the realm folder, and when it can't
read a file it must say so rather than report a clean success over a hole in the archive.
"""
import json
import os
import zipfile
from pathlib import Path

from armada import realmops


def _realm(tmp_path):
    r = tmp_path / "Testrealm"
    (r / "agents" / "scribe" / "threads" / "main").mkdir(parents=True)
    (r / "agents" / "scribe" / "memory").mkdir()
    (r / "memory").mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    (r / "agents" / "scribe" / "agent.json").write_text(json.dumps({"id": "scribe"}), encoding="utf-8")
    (r / "agents" / "scribe" / "threads" / "main" / "messages.jsonl").write_text(
        '{"role":"user","content":"hi"}\n', encoding="utf-8")
    (r / "agents" / "scribe" / "memory" / "note.md").write_text("# note\n", encoding="utf-8")
    (r / "memory" / "realm.md").write_text("# realm memory\n", encoding="utf-8")
    (r / "system_jobs.json").write_text("{}", encoding="utf-8")
    return r


def _members(zp):
    with zipfile.ZipFile(zp) as z:
        return {n for n in z.namelist() if not n.endswith("/")}


def test_export_contains_every_file_in_the_realm(tmp_path):
    r = _realm(tmp_path)
    dest = tmp_path / "out"
    res = realmops.export(r, dest)
    assert res["ok"], res
    names = _members(res["path"])

    on_disk = set()
    for root, dirs, files in os.walk(r):
        dirs[:] = [d for d in dirs if d not in realmops._SKIP_DIRS]
        for f in files:
            on_disk.add((Path(root) / f).relative_to(r.parent).as_posix())
    assert on_disk - {n.replace("\\", "/") for n in names} == set()
    assert res["files"] == len(on_disk)


def test_export_carries_the_things_a_new_realm_needs(tmp_path):
    r = _realm(tmp_path)
    res = realmops.export(r, tmp_path / "out")
    names = " ".join(_members(res["path"])).replace("\\", "/")
    for needed in ["realm.json", "agents/scribe/agent.json", "memory/realm.md",
                   "agents/scribe/memory/note.md", "agents/scribe/threads/main/messages.jsonl",
                   "system_jobs.json"]:
        assert needed in names, needed


def test_export_skips_caches(tmp_path):
    r = _realm(tmp_path)
    (r / "__pycache__").mkdir()
    (r / "__pycache__" / "x.pyc").write_text("junk", encoding="utf-8")
    res = realmops.export(r, tmp_path / "out")
    assert not any("__pycache__" in n for n in _members(res["path"]))


def test_a_clean_export_reports_nothing_skipped(tmp_path):
    res = realmops.export(_realm(tmp_path), tmp_path / "out")
    assert res["ok"] and "skipped" not in res and "skipped_n" not in res


def test_an_unreadable_file_is_reported_not_swallowed(tmp_path, monkeypatch):
    """The whole point: the export carries on past a locked file, but the caller is told which
    ones didn't make it. Reporting a plain success over a hole is how a backup fails silently."""
    r = _realm(tmp_path)
    doomed = "messages.jsonl"
    real_write = zipfile.ZipFile.write

    def flaky(self, filename, arcname=None, *a, **kw):
        if Path(filename).name == doomed:
            raise PermissionError("file is in use by another process")
        return real_write(self, filename, arcname, *a, **kw)

    monkeypatch.setattr(zipfile.ZipFile, "write", flaky)
    res = realmops.export(r, tmp_path / "out")

    assert res["ok"], "one locked file must not abort the whole export"
    assert res.get("skipped_n") == 1
    assert any(doomed in s for s in res["skipped"]), res.get("skipped")
    assert not any(doomed in n for n in _members(res["path"])), "claimed skipped but actually wrote it"


def test_skipped_list_is_bounded(tmp_path, monkeypatch):
    r = _realm(tmp_path)
    for i in range(80):
        (r / f"f{i}.txt").write_text("x", encoding="utf-8")

    def always_fail(self, filename, arcname=None, *a, **kw):
        raise OSError("nope")

    monkeypatch.setattr(zipfile.ZipFile, "write", always_fail)
    res = realmops.export(r, tmp_path / "out")
    assert res["skipped_n"] > 50               # the true count is honest
    assert len(res["skipped"]) == 50           # the sample is capped


def test_missing_realm_is_an_error_not_an_empty_archive(tmp_path):
    res = realmops.export(tmp_path / "does-not-exist", tmp_path / "out")
    assert not res["ok"] and "error" in res


def test_the_archive_never_contains_itself(tmp_path):
    """Exporting into the realm's own parent writes the zip beside it; a second export must not
    swallow the first one's output into itself."""
    r = _realm(tmp_path)
    first = realmops.export(r, r)             # dest inside the realm
    assert first["ok"]
    assert not any(n.endswith(Path(first["path"]).name) for n in _members(first["path"]))
