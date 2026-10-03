"""Legacy appointment history survives configuration edits, copying and retirement."""
import datetime
import json
import os

import pytest

from armada import agentdates, agentops, reader, realmformat, util


def _profile(root, aid="finance", base="agents", **extra):
    directory = root / base / aid
    directory.mkdir(parents=True)
    util.write_json_atomic(directory / "agent.json", {"id": aid, **extra})
    return directory


@pytest.mark.parametrize("fields,expected", [
    ({"appointed": "2026-08-10", "created": "2026-07-01"}, "2026-08-10"),
    ({"created": "2026-07-01"}, "2026-07-01"),
])
def test_recorded_dates_override_filesystem_dates(tmp_path, fields, expected):
    directory = _profile(tmp_path, **fields)
    assert agentdates.appointment_date(fields, directory) == expected


def test_reader_uses_folder_creation_instead_of_recent_config_save(tmp_path, monkeypatch):
    directory = _profile(tmp_path)
    born = datetime.datetime(2026, 9, 16, 15).timestamp()
    monkeypatch.setattr(agentdates, "_birthtime", lambda path: born)
    os.utime(directory / "agent.json", None)
    assert reader.read_native(tmp_path).agents[0].appointed == "2026-09-16"


def test_no_birthtime_uses_profile_history_and_excludes_old_portraits(tmp_path, monkeypatch):
    directory = _profile(tmp_path)
    monkeypatch.setattr(agentdates, "_birthtime", lambda path: None)
    soul = directory / "soul.md"
    soul.write_text("Profile", encoding="utf-8")
    old = datetime.datetime(2026, 9, 16, 15).timestamp()
    os.utime(soul, (old, old))
    avatar = directory / "avatar.png"
    avatar.write_bytes(b"portrait")
    os.utime(avatar, (0, 0))
    assert agentdates.appointment_date({}, directory) == "2026-09-16"


def test_migration_freezes_dates_through_future_edits_and_reinstatement(tmp_path, monkeypatch):
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Test", "schema_version": 2})
    active = _profile(tmp_path)
    retired = _profile(tmp_path, "education", "retired", created="2026-08-01")
    born = datetime.datetime(2026, 9, 16, 15).timestamp()
    monkeypatch.setattr(agentdates, "_birthtime", lambda path: born)
    assert realmformat.migrate(tmp_path)["ok"]
    assert util.read_json_state(active / "agent.json")["appointed"] == "2026-09-16"
    assert util.read_json_state(retired / "agent.json")["appointed"] == "2026-08-01"
    # Simulate a later move/copy and model update replacing the file.
    monkeypatch.setattr(agentdates, "_birthtime", lambda path: datetime.datetime.now().timestamp())
    util.mutate_json(active / "agent.json", lambda cfg: {**cfg, "model": "gpt-6-sol"})
    assert reader.read_native(tmp_path).agents[0].appointed == "2026-09-16"
    assert agentops.list_retired(tmp_path)[0]["appointed"] == "2026-08-01"
    assert agentops.reinstate(tmp_path, "education")["ok"]
    assert {a.id: a.appointed for a in reader.read_native(tmp_path).agents} == {
        "finance": "2026-09-16", "education": "2026-08-01"}
    assert not realmformat.migrate(tmp_path)["changed"]


def test_migration_preserves_explicit_appointment_byte_for_byte(tmp_path):
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Test", "schema_version": 2})
    directory = _profile(tmp_path, appointed="2026-08-01", model="gpt-6-sol")
    before = (directory / "agent.json").read_bytes()
    assert realmformat.migrate(tmp_path)["ok"]
    assert (directory / "agent.json").read_bytes() == before


def test_corrupt_profile_prevents_migration_stamp_and_is_not_overwritten(tmp_path):
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Test", "schema_version": 2})
    directory = _profile(tmp_path)
    path = directory / "agent.json"
    path.write_text("{broken", encoding="utf-8")
    assert not realmformat.migrate(tmp_path)["ok"]
    assert json.loads((tmp_path / "realm.json").read_text())["schema_version"] == 2
    assert path.read_text() == "{broken"
