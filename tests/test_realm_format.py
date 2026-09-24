"""Realm format versioning (Phase 2, 2.8): realm.json carries an integer schema_version and
realmformat.migrate() walks a realm up to CURRENT on open and on import.

The first migration is a no-op that only stamps the version, so most of what's worth pinning here is
the machinery around it: legacy stamps, a realm from a NEWER build left alone, idempotence, a broken
realm.json not stopping the app, the per-change memo, and the four places a realm is opened or
imported actually calling it.
"""
import json

import pytest

from armada import realmformat, scheduler, serve, setup, validate


def _write(root, cfg, raw=None):
    root.mkdir(parents=True, exist_ok=True)
    (root / "realm.json").write_text(raw if raw is not None else json.dumps(cfg, indent=2), encoding="utf-8")
    return root


def _read(root):
    return json.loads((root / "realm.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_memo():
    realmformat._checked.clear()
    yield
    realmformat._checked.clear()


# ---- version_of / plan ---------------------------------------------------------------------------

@pytest.mark.parametrize("stamp,expected", [
    (None, 0), ("0.1", 0), ("junk", 0), (True, 0), ({"x": 1}, 0), (-3, 0),
    (1, 1), ("1", 1), (7, 7),
])
def test_version_of_reads_every_shape_a_realm_has_been_stamped_with(stamp, expected):
    cfg = {"name": "R"} if stamp is None else {"name": "R", "schema_version": stamp}
    assert realmformat.version_of(cfg) == expected


def test_there_is_a_registered_step_for_every_version_below_current():
    assert sorted(realmformat.MIGRATIONS) == list(range(realmformat.CURRENT))


def test_plan_on_a_newer_realm_does_nothing_and_says_so():
    pl = realmformat.plan({"schema_version": realmformat.CURRENT + 1})
    assert pl["newer"] and pl["steps"] == []


# ---- migrate -------------------------------------------------------------------------------------

def test_an_unstamped_realm_is_stamped_and_nothing_else_changes(tmp_path):
    cfg = {"name": "R", "timezone": "Europe/Madrid", "sections": [{"name": "S"}], "toolkit": {"skills": []}}
    root = _write(tmp_path / "r", cfg)
    res = realmformat.migrate(root)
    assert res == {"ok": True, "from": 0, "to": realmformat.CURRENT, "changed": True}
    out = _read(root)
    assert out.pop("schema_version") == realmformat.CURRENT
    assert out == cfg
    # Placed right after "name", where someone opening the file will see it.
    assert list(_read(root))[:2] == ["name", "schema_version"]


def test_the_legacy_string_stamp_becomes_the_integer(tmp_path):
    root = _write(tmp_path / "r", {"name": "R", "schema_version": "0.1", "theme_ref": "theme.json"})
    assert realmformat.migrate(root)["from"] == 0
    assert _read(root)["schema_version"] == realmformat.CURRENT and isinstance(_read(root)["schema_version"], int)


def test_a_current_realm_is_not_rewritten(tmp_path):
    root = _write(tmp_path / "r", {"name": "R", "schema_version": realmformat.CURRENT})
    before = (root / "realm.json").stat().st_mtime_ns
    res = realmformat.migrate(root)
    assert res["ok"] and not res["changed"]
    assert (root / "realm.json").stat().st_mtime_ns == before


def test_migrate_is_idempotent(tmp_path):
    root = _write(tmp_path / "r", {"name": "R"})
    realmformat.migrate(root)
    once = (root / "realm.json").read_text(encoding="utf-8")
    assert not realmformat.migrate(root)["changed"]
    assert (root / "realm.json").read_text(encoding="utf-8") == once


def test_a_realm_from_a_newer_armada_is_left_byte_for_byte(tmp_path):
    raw = json.dumps({"name": "R", "schema_version": realmformat.CURRENT + 5, "future_field": {"a": 1}})
    root = _write(tmp_path / "r", None, raw=raw)
    res = realmformat.migrate(root)
    assert res["ok"] and res["newer"] and not res["changed"]
    assert (root / "realm.json").read_text(encoding="utf-8") == raw


def test_steps_run_in_order_from_the_realms_own_version(tmp_path, monkeypatch):
    """What the next real migration will rely on: v0 → v1 → v2 in sequence, each seeing the last."""
    seen = []

    def m1(cfg, root):
        seen.append(("m1", dict(cfg)))
        cfg = dict(cfg)
        old = cfg.pop("old", None)
        return {**cfg, "renamed": old}

    monkeypatch.setattr(realmformat, "CURRENT", 2)
    monkeypatch.setitem(realmformat.MIGRATIONS, 1, m1)
    root = _write(tmp_path / "r", {"name": "R", "old": "x"})
    assert realmformat.migrate(root)["from"] == 0
    out = _read(root)
    assert out["schema_version"] == 2 and out["renamed"] == "x" and "old" not in out
    assert [s[0] for s in seen] == ["m1"]


def test_a_failing_step_leaves_the_file_alone_and_does_not_raise(tmp_path, monkeypatch):
    def boom(cfg, root):
        raise ValueError("nope")

    monkeypatch.setitem(realmformat.MIGRATIONS, 0, boom)
    raw = json.dumps({"name": "R"})
    root = _write(tmp_path / "r", None, raw=raw)
    res = realmformat.migrate(root)
    assert not res["ok"] and "nope" in res["error"]
    assert (root / "realm.json").read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]"])
def test_a_broken_realm_json_is_reported_not_raised(tmp_path, raw):
    root = _write(tmp_path / "r", None, raw=raw)
    res = realmformat.migrate(root)
    assert not res["ok"]
    assert (root / "realm.json").read_text(encoding="utf-8") == raw


def test_a_folder_without_realm_json_is_skipped(tmp_path):
    (tmp_path / "cabinet").mkdir()
    res = realmformat.migrate(tmp_path)
    assert res["ok"] and res.get("skipped")


def test_migration_takes_the_realm_json_lock(tmp_path, monkeypatch):
    calls = []
    real = realmformat.util.file_lock

    def spy(target, *a, **kw):
        calls.append(str(target))
        return real(target, *a, **kw)

    monkeypatch.setattr(realmformat.util, "file_lock", spy)
    root = _write(tmp_path / "r", {"name": "R"})
    realmformat.migrate(root)
    assert calls == [str(root / "realm.json")]


# ---- ensure (the per-change memo) ----------------------------------------------------------------

def test_ensure_runs_once_until_realm_json_changes(tmp_path, monkeypatch):
    root = _write(tmp_path / "r", {"name": "R"})
    n = {"migrate": 0}
    real = realmformat.migrate

    def counting(r):
        n["migrate"] += 1
        return real(r)

    monkeypatch.setattr(realmformat, "migrate", counting)
    realmformat.ensure(root)
    realmformat.ensure(root)
    realmformat.ensure(root)
    assert n["migrate"] == 1
    import os
    p = root / "realm.json"
    p.write_text(json.dumps({"name": "R"}), encoding="utf-8")   # e.g. restored from a backup
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    realmformat.ensure(root)
    assert n["migrate"] == 2
    assert _read(root)["schema_version"] == realmformat.CURRENT


def test_ensure_on_a_missing_folder_is_quiet(tmp_path):
    assert realmformat.ensure(tmp_path / "nope") is None


# ---- where it's wired in -------------------------------------------------------------------------

def test_a_new_realm_is_born_at_the_current_format(tmp_path):
    setup.scaffold(str(tmp_path / "r"), "scratch", "R")
    assert _read(tmp_path / "r")["schema_version"] == realmformat.CURRENT


def test_the_scheduler_pass_migrates_but_a_dry_run_does_not(tmp_path):
    root = _write(tmp_path / "r", {"name": "R"})
    scheduler.tick(root, dry_run=True)
    assert "schema_version" not in _read(root)
    scheduler.tick(root)
    assert _read(root)["schema_version"] == realmformat.CURRENT


class _H(serve.Handler):
    def __init__(self, realm):
        self.realm = str(realm)


def test_adopting_an_existing_realm_migrates_it(tmp_path, monkeypatch):
    from armada import approot
    monkeypatch.setattr(approot, "check", lambda p: {"ok": True})
    monkeypatch.setattr("armada.routes.realm._reg_ensure", lambda *a, **k: None)
    root = _write(tmp_path / "old", {"name": "Old", "schema_version": "0.1"})
    out = _H(tmp_path)._new_realm({"mode": "adopt", "path": str(root)})
    assert out["ok"], out
    assert _read(root)["schema_version"] == realmformat.CURRENT
    assert "format_warning" not in out


def test_adopting_a_newer_realm_warns_and_leaves_it(tmp_path, monkeypatch):
    from armada import approot
    monkeypatch.setattr(approot, "check", lambda p: {"ok": True})
    monkeypatch.setattr("armada.routes.realm._reg_ensure", lambda *a, **k: None)
    # The arrival preflight writes its own scheduler_hold on this machine; that's not what's under test.
    monkeypatch.setattr("armada.preflight.apply_hold", lambda p: {"checks": []})
    raw = json.dumps({"name": "New", "schema_version": realmformat.CURRENT + 1})
    root = _write(tmp_path / "new", None, raw=raw)
    out = _H(tmp_path)._new_realm({"mode": "adopt", "path": str(root)})
    assert out["ok"] and "newer version of ARMADA" in out["format_warning"]
    assert (root / "realm.json").read_text(encoding="utf-8") == raw


def test_validate_reports_the_format(tmp_path):
    root = _write(tmp_path / "r", {"name": "R", "timezone": "UTC"})
    rep = validate.validate(root)
    assert any("upgraded to v" in i for i in rep["info"])
    newer = _write(tmp_path / "n", {"name": "N", "timezone": "UTC", "schema_version": 99})
    assert any("newer than this ARMADA" in w for w in validate.validate(newer)["warnings"])
