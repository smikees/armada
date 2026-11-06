"""Synthetic recovery and failure injection; no real realm or provider is touched."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import zipfile

import pytest

from armada import cli, realm_export as backup, realmops, util


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "SyntheticRealm"
    (root / "agents" / "scribe" / "jobs").mkdir(parents=True)
    (root / "empty").mkdir()
    (root / "realm.json").write_text('{"name":"Synthetic"}')
    (root / "agents/scribe/agent.json").write_text('{"id":"scribe","write_scope":[]}')
    (root / "agents/scribe/jobs/daily.json").write_text('{"enabled":true}')
    (root / "note.md").write_bytes(b"Synthetic content\n")
    (root / "system_jobs.json").write_text('{"usage":{"enabled":true,"attempt":{"state":"claimed","id":"evidence"}}}')
    return root


def exported(realm):
    result = realmops.export(realm)
    assert result["ok"] and result["complete"], result
    return Path(result["path"])


def rewrite(archive, change, extra=None):
    with zipfile.ZipFile(archive) as z:
        entries = {i.filename: z.read(i) for i in z.infolist()}
    name = next(n for n in entries if n.endswith(backup.MANIFEST))
    data = json.loads(entries[name])
    change(data, entries)
    entries[name] = json.dumps(data).encode()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for n, raw in entries.items():
            z.writestr(n, raw)
        if extra:
            z.writestr(*extra)


def test_simultaneous_exports_preserve_previous_success(realm):
    first = exported(realm)
    before = first.read_bytes()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: realmops.export(realm), range(8)))
    assert all(r["ok"] and r["complete"] for r in results), results
    assert len({r["path"] for r in results} | {str(first)}) == 9
    assert first.read_bytes() == before
    assert all(backup.verify(r["path"])["verified"] for r in results)


def test_publish_refuses_existing_destination(tmp_path):
    staged, old = tmp_path / "stage", tmp_path / "old"
    staged.write_bytes(b"new")
    old.write_bytes(b"previous success")
    with pytest.raises(FileExistsError):
        util.publish_new_file(staged, old)
    assert old.read_bytes() == b"previous success" and staged.read_bytes() == b"new"


@pytest.mark.parametrize("phase", ["archive", "verify", "publish", "interrupt"])
def test_failed_export_never_publishes_partial_or_changes_previous(realm, monkeypatch, phase):
    previous = exported(realm)
    raw = previous.read_bytes()
    def fail(*args, **kwargs):
        raise OSError("injected output failure")
    if phase == "archive":
        monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    elif phase == "verify":
        monkeypatch.setattr(backup, "verify", lambda _: {"ok": False, "error": "injected corruption"})
    elif phase == "publish":
        monkeypatch.setattr(util, "publish_new_file", fail)
    else:
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt()
        monkeypatch.setattr(backup, "_capture", interrupt)
    if phase == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            realmops.export(realm)
    else:
        assert not realmops.export(realm)["ok"]
    assert list(realm.parent.glob("*.zip")) == [previous]
    assert not list(realm.parent.glob(".armada-export-*"))
    assert previous.read_bytes() == raw


def test_spool_failure_is_fatal(realm, monkeypatch):
    def fail(*args):
        raise backup.ExportWriteError("disk full")
    monkeypatch.setattr(backup, "_capture", fail)
    result = realmops.export(realm)
    assert not result["ok"] and "disk full" in result["error"]
    assert not list(realm.parent.glob("*.zip"))


def test_change_after_capture_is_incomplete_but_verified(realm, monkeypatch):
    original = backup._capture
    def capture(src, rel, signature, spool):
        result = original(src, rel, signature, spool)
        if rel == "note.md":
            (src / rel).write_bytes(b"changed during export")
            (src / "new.md").write_bytes(b"new")
        return result
    monkeypatch.setattr(backup, "_capture", capture)
    result = realmops.export(realm)
    assert result["ok"] and result["verified"] and not result["complete"]
    assert result["changed_n"] == 2
    manifest = backup.verify(result["path"])["manifest"]
    assert manifest["consistency"] == backup.CONSISTENCY
    assert set(manifest["changed"]) == {"new.md", "note.md"}


def test_source_read_failure_never_leaves_a_half_entry(realm, monkeypatch):
    original = backup._capture
    def capture(src, rel, signature, spool):
        if rel == "note.md":
            spool.write(b"half-read")
            raise OSError("read interrupted")
        return original(src, rel, signature, spool)
    monkeypatch.setattr(backup, "_capture", capture)
    result = realmops.export(realm)
    assert result["ok"] and result["skipped"] == ["note.md"] and not result["complete"]
    with zipfile.ZipFile(result["path"]) as z:
        assert not any(n.endswith("/note.md") for n in z.namelist())
    assert backup.verify(result["path"])["ok"]


def test_secrets_and_runtime_omissions_are_in_manifest(realm):
    (realm / ".env").write_text("synthetic secret")
    (realm / ".scheduler").mkdir()
    (realm / ".scheduler/claim.json").write_text('{"state":"claimed"}')
    (realm / "manifest.lock").write_text('{"pin":"synthetic"}')
    (realm / "__pycache__").mkdir()
    result = realmops.export(realm)
    assert result["complete"] and result["secrets_left_out"] == [".env"]
    manifest = backup.verify(result["path"])["manifest"]
    assert {o["reason"] for o in manifest["omitted"]} == {"credential-name", "cache-or-runtime"}
    assert "empty" in manifest["directories"]
    assert {".scheduler/claim.json", "manifest.lock"} <= {r["path"] for r in manifest["files"]}


@pytest.mark.skipif(os.name != "nt", reason="Windows junction boundary")
def test_escaping_junction_never_exports_external_bytes(realm, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_bytes(b"do not export")
    junction = realm / "linked"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], check=True, capture_output=True)
    try:
        result = realmops.export(realm)
        assert result["ok"] and not result["complete"] and result["skipped"] == ["linked"]
        with zipfile.ZipFile(result["path"]) as z:
            assert not any("private.txt" in n for n in z.namelist())
        assert not realmops.export(junction)["ok"]
    finally:
        junction.rmdir()


@pytest.mark.parametrize("kind", ["checksum", "size", "missing", "unlisted", "duplicate", "case", "symlink", "schema", "complete", "metadata"])
def test_damaged_or_ambiguous_archive_refused(realm, kind):
    archive = exported(realm)
    def change(m, entries):
        row = next(r for r in m["files"] if r["path"] == "note.md")
        if kind == "checksum":
            entries[m["root"] + "/note.md"] = b"X" * row["size"]
        elif kind == "size":
            row["size"] += 1
        elif kind == "missing":
            del entries[m["root"] + "/note.md"]
        elif kind == "schema":
            m["format"] = True
        elif kind == "complete":
            m["changed"] = ["note.md"]
        elif kind == "metadata":
            m["directories"] = [None]
    extra = None
    if kind in ("unlisted", "duplicate", "case"):
        extra = (f"{realm.name}/" + {"unlisted": "extra", "duplicate": "note.md", "case": "NOTE.md"}[kind], b"rogue")
    elif kind == "symlink":
        info = zipfile.ZipInfo(f"{realm.name}/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        extra = (info, b"../outside")
    if kind == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate name"):
            rewrite(archive, change, extra)
    else:
        rewrite(archive, change, extra)
    assert not backup.verify(archive)["ok"]
    target = realm.parent / "Recovered"
    assert not backup.restore_copy(archive, target)["ok"]
    assert not target.exists()


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/drive", "a\\b", "a:stream", "NUL.txt", "COM¹", "a./file", "a/../b", "a//b"])
def test_hostile_paths_rejected_before_extraction(realm, path):
    archive = exported(realm)
    rewrite(archive, lambda m, e: m["directories"].append(path))
    assert not backup.verify(archive)["ok"]


def test_file_directory_alias_rejected(realm):
    archive = exported(realm)
    rewrite(archive, lambda m, e: m["directories"].append("NOTE.MD/child"))
    assert not backup.verify(archive)["ok"]


@pytest.mark.skipif(os.name != "nt", reason="Windows atomic recovery")
def test_restore_preserves_data_policies_and_claims_but_pauses_work(realm):
    archive = exported(realm)
    target = realm.parent / "Recovered"
    result = backup.restore_copy(archive, target)
    assert result["ok"] and result["paused"], result
    assert json.loads((target / "realm.json").read_text())["archived"] is True
    assert json.loads((target / "agents/scribe/jobs/daily.json").read_text())["enabled"] is False
    assert (target / "agents/scribe/agent.json").read_bytes() == (realm / "agents/scribe/agent.json").read_bytes()
    assert (target / "note.md").read_bytes() == (realm / "note.md").read_bytes()
    assert (target / "empty").is_dir()
    state = json.loads((target / "system_jobs.json").read_text())
    assert state["usage"]["attempt"]["id"] == "evidence"
    assert all(not row["enabled"] for row in state.values())
    assert not backup.restore_copy(archive, target)["ok"]
    # A recovered realm must itself remain exportable.
    exported(target)


@pytest.mark.skipif(os.name != "nt", reason="Windows atomic recovery")
def test_incomplete_restore_needs_explicit_choice(realm, monkeypatch):
    original = backup._capture
    def fail_note(src, rel, sig, spool):
        if rel == "note.md":
            raise OSError("locked")
        return original(src, rel, sig, spool)
    monkeypatch.setattr(backup, "_capture", fail_note)
    result = realmops.export(realm)
    target = realm.parent / "Recovered"
    assert not backup.restore_copy(result["path"], target)["ok"]
    assert not target.exists()
    restored = backup.restore_copy(result["path"], target, allow_incomplete=True)
    assert restored["ok"] and not restored["complete"]
    assert not (target / "note.md").exists()


def test_entry_and_size_limits_fail_closed(realm, monkeypatch):
    archive = exported(realm)
    monkeypatch.setattr(backup, "MAX_ENTRIES", 2)
    assert not backup.verify(archive)["ok"]
    assert not realmops.export(realm)["ok"]


def test_cli_verifies_without_starting_app(realm, capsys):
    archive = exported(realm)
    assert cli.main(["backup", "verify", str(archive)]) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True


def test_manifest_checksum_covers_exact_original_bytes(realm):
    result = backup.verify(exported(realm))
    for row in result["manifest"]["files"]:
        assert hashlib.sha256((realm / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_zip64_archive_round_trip(realm, monkeypatch):
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 20)
    assert backup.verify(exported(realm))["complete"]


def test_directory_allocation_limit_precedes_zipfile(tmp_path, monkeypatch):
    archive = tmp_path / "oversized.zip"
    archive.write_bytes(struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1, 32 * 1024**2, 0, 0))
    def should_not_parse(*args, **kwargs):
        pytest.fail("ZipFile allocated metadata before limits were checked")
    monkeypatch.setattr(zipfile, "ZipFile", should_not_parse)
    assert not backup.verify(archive)["ok"]


def test_hard_process_exit_only_leaves_recognizable_partial(realm):
    previous = exported(realm)
    digest = hashlib.sha256(previous.read_bytes()).hexdigest()
    script = '''import os, sys
from armada import realm_export
def crash(*args):
    os._exit(17)
realm_export._capture = crash
realm_export.export(sys.argv[1])
'''
    result = subprocess.run([sys.executable, "-c", script, str(realm)],
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=30)
    assert result.returncode == 17
    assert list(realm.parent.glob("*.zip")) == [previous]
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == digest
    assert len(list(realm.parent.glob(".armada-export-*.partial"))) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows atomic recovery")
@pytest.mark.parametrize("failure", ["copy", "pause", "publish", "destination-race"])
def test_restore_failure_never_publishes_partial(realm, monkeypatch, failure):
    archive = exported(realm)
    target = realm.parent / "Recovered"
    if failure == "copy":
        original = backup._verified
        def failed_copy(z, extract_to=None):
            if extract_to:
                (extract_to / "partial").write_bytes(b"part")
                raise OSError("copy failed")
            return original(z)
        monkeypatch.setattr(backup, "_verified", failed_copy)
    elif failure == "pause":
        def failed_pause(_):
            raise ValueError("bad job settings")
        monkeypatch.setattr(backup, "_hold_restored", failed_pause)
    else:
        rename = os.rename
        def failed_publish(src, dst):
            if failure == "destination-race":
                target.mkdir()
                (target / "owner.txt").write_bytes(b"keep")
                return rename(src, dst)
            raise OSError("rename failed")
        monkeypatch.setattr(os, "rename", failed_publish)
    assert not backup.restore_copy(archive, target)["ok"]
    assert not list(realm.parent.glob(".armada-restore-*"))
    if failure == "destination-race":
        assert (target / "owner.txt").read_bytes() == b"keep"
        assert not (target / "realm.json").exists()
    else:
        assert not target.exists()
