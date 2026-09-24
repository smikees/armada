"""The add-on surface (Phase 2, 2.7): the contract loads what it should, and every malformed input
fails SAFE — the bad add-on (or the one bad contribution inside a good one) is skipped with a reason,
nothing raises, and everything else still loads.

Nothing in the app consumes add-ons yet; these tests are the contract until something does.
"""
import json
import os
import re
from pathlib import Path

import pytest

from armada import addons

DOC = Path(__file__).resolve().parents[1] / "docs" / "dev" / "EXTENSION_POINTS.md"


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    app = tmp_path / "home" / ".armada" / "addons"
    realm = tmp_path / "realm"
    app.mkdir(parents=True)
    (realm / "addons").mkdir(parents=True)
    monkeypatch.setattr(addons, "app_dir", lambda: app)
    return app, realm


def put(root: Path, aid: str, manifest, raw: str | None = None, folder: str | None = None) -> Path:
    d = root / (folder or aid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "addon.json").write_text(raw if raw is not None else json.dumps(manifest), encoding="utf-8")
    return d


def manifest(aid="demo", **provides):
    return {"armada_addon": 1, "id": aid, "name": "Demo", "version": "1.0.0", "provides": provides}


W_MD = {"id": "note", "title": "Morning note", "kind": "markdown", "body": "**Hi.**", "default_span": 8}
W_LINKS = {"id": "links", "title": "Links", "kind": "links",
           "links": [{"label": "Docs", "url": "/docs"}, {"label": "Site", "url": "https://example.com"}]}
F_JOBS = {"id": "broken", "label": "Broken daily jobs", "applies_to": "jobs",
          "match": {"status": ["failed", "warning"], "cadence": ["daily"]}}
T_SEA = {"id": "sea", "name": "Sea", "accent": "#0B3F86", "accent2": "#12a3b8"}
J_WEEKLY = {"id": "weekly-review", "name": "Weekly review", "prompt": "Review the week.",
            "cron": "0 9 * * 1", "summary": "Monday 9am recap", "allow_tools": True}
L_FOCUS = {"id": "focus", "name": "Focus", "order": ["register", "addon:demo/note"],
           "spans": {"register": 12, "addon:demo/note": 8}, "heights": {"register": 400}}


def reasons(reg):
    return [p["reason"] for p in reg.problems]


# ---- the happy path -------------------------------------------------------------------------------

def test_nothing_installed_is_an_empty_registry_not_an_error(dirs):
    reg = addons.load(dirs[1])
    assert reg.addons == [] and reg.problems == [] and all(reg.get(k) == [] for k in addons.KINDS)


def test_every_kind_loads_with_a_qualified_id(dirs):
    app, realm = dirs
    put(app, "demo", manifest(widgets=[W_MD, W_LINKS], filters=[F_JOBS], themes=[T_SEA],
                              job_templates=[J_WEEKLY], layouts=[L_FOCUS]))
    reg = addons.load(realm)
    assert reg.problems == []
    assert [a["id"] for a in reg.addons] == ["demo"]
    assert [w["qid"] for w in reg.get("widgets")] == ["demo/note", "demo/links"]
    assert reg.find("themes", "demo/sea")["accent"] == "#0b3f86"          # normalised
    jt = reg.find("job_templates", "demo/weekly-review")
    assert jt["kind"] == "agent" and jt["cron"] == "0 9 * * 1"
    assert reg.find("layouts", "demo/focus")["spans"] == {"register": 12, "addon:demo/note": 8}
    assert reg.find("filters", "demo/broken")["match"]["status"] == ["failed", "warning"]


def test_a_realm_addon_shadows_the_apps_of_the_same_id(dirs):
    app, realm = dirs
    put(app, "demo", manifest(widgets=[W_MD]))
    put(realm / "addons", "demo", manifest(widgets=[W_LINKS]))
    reg = addons.load(realm)
    assert [w["qid"] for w in reg.get("widgets")] == ["demo/links"]
    assert reg.get("widgets")[0]["scope"] == "realm"
    assert any("shadowed" in r for r in reasons(reg))


def test_themes_are_per_install_so_a_realm_addon_cannot_carry_one(dirs):
    _, realm = dirs
    put(realm / "addons", "demo", manifest(themes=[T_SEA], widgets=[W_MD]))
    reg = addons.load(realm)
    assert reg.get("themes") == [] and len(reg.get("widgets")) == 1
    assert any("per-install" in r for r in reasons(reg))


def test_without_a_realm_only_the_apps_addons_load(dirs):
    app, realm = dirs
    put(app, "a", manifest("a", widgets=[W_MD]))
    put(realm / "addons", "b", manifest("b", widgets=[W_MD]))
    assert [a["id"] for a in addons.load().addons] == ["a"]


# ---- a malformed add-on is skipped whole ----------------------------------------------------------

@pytest.mark.parametrize("raw,why", [
    ("{not json", "not valid JSON"),
    ("[1, 2, 3]", "must be a JSON object"),
    (json.dumps({"id": "demo", "provides": {}}), "contract version"),
    (json.dumps({"armada_addon": "1", "id": "demo", "provides": {}}), "contract version"),
    (json.dumps({"armada_addon": 2, "id": "demo", "provides": {}}), "update ARMADA"),
    (json.dumps({"armada_addon": 1, "id": "Demo!", "provides": {}}), "lowercase"),
    (json.dumps({"armada_addon": 1, "id": "other", "provides": {}}), "must match its folder"),
    (json.dumps({"armada_addon": 1, "id": "demo", "provides": []}), "'provides' must be an object"),
    ("", "not valid JSON"),
])
def test_a_malformed_manifest_is_skipped_with_a_reason(dirs, raw, why):
    app, realm = dirs
    put(app, "demo", None, raw=raw)
    put(app, "good", manifest("good", widgets=[W_MD]))                # a neighbour still loads
    reg = addons.load(realm)
    assert [a["id"] for a in reg.addons] == ["good"]
    assert any(why in r for r in reasons(reg)), reasons(reg)


def test_a_folder_without_a_manifest_is_reported(dirs):
    app, realm = dirs
    (app / "empty").mkdir()
    assert any("no addon.json" in r for r in reasons(addons.load(realm)))


def test_an_oversized_manifest_is_not_even_parsed(dirs, monkeypatch):
    app, realm = dirs
    monkeypatch.setattr(addons, "MAX_MANIFEST_BYTES", 100)
    put(app, "demo", manifest(widgets=[W_MD] * 1))
    reg = addons.load(realm)
    assert reg.addons == [] and any("the limit is 100" in r for r in reasons(reg))


@pytest.mark.skipif(os.name == "nt", reason="creating symlinks needs privileges on Windows")
def test_a_symlinked_addon_is_refused(dirs, tmp_path):
    app, realm = dirs
    elsewhere = put(tmp_path / "outside", "demo", manifest(widgets=[W_MD]))
    (app / "demo").symlink_to(elsewhere, target_is_directory=True)
    reg = addons.load(realm)
    assert reg.addons == [] and any("symlinked" in r for r in reasons(reg))


def test_an_addons_path_that_is_a_file_is_just_empty(tmp_path, monkeypatch):
    f = tmp_path / "addons"
    f.write_text("oops", encoding="utf-8")
    monkeypatch.setattr(addons, "app_dir", lambda: f)
    reg = addons.load(None)
    assert reg.addons == []


def test_a_loader_bug_costs_one_addon_not_the_app(dirs, monkeypatch):
    app, realm = dirs
    put(app, "a", manifest("a", widgets=[W_MD]))
    put(app, "b", manifest("b", filters=[F_JOBS]))

    def boom(d):
        raise RuntimeError("validator bug")

    monkeypatch.setitem(addons._VALIDATORS, "widgets", boom)
    reg = addons.load(realm)
    assert [a["id"] for a in reg.addons] == ["b"]
    assert any("could not be loaded" in r for r in reasons(reg))


# ---- a bad contribution is skipped alone ----------------------------------------------------------

@pytest.mark.parametrize("kind,entry,why", [
    ("widgets", {**W_MD, "kind": "html"}, "'markdown' or 'links'"),
    ("widgets", {**W_MD, "body": "x" * (addons.MAX_TEXT + 1)}, "markdown widget needs a body"),
    ("widgets", {**W_MD, "title": ""}, "needs a title"),
    ("widgets", {**W_MD, "default_span": 30}, "default_span"),
    ("widgets", {**W_LINKS, "links": [{"label": "x", "url": "javascript:alert(1)"}]}, "http(s) or app-local"),
    ("widgets", {**W_LINKS, "links": [{"label": "x", "url": "//evil.example"}]}, "http(s) or app-local"),
    ("filters", {**F_JOBS, "applies_to": "memories"}, "applies_to"),
    ("filters", {**F_JOBS, "match": {"owner": ["x"]}}, "not something a jobs filter"),
    ("filters", {**F_JOBS, "match": {"status": ["exploded"]}}, "values must be from"),
    ("filters", {**F_JOBS, "match": {}}, "non-empty match"),
    ("themes", {**T_SEA, "accent": "blue"}, "#rrggbb"),
    ("job_templates", {**J_WEEKLY, "kind": "command", "run": "rm -rf /"}, "never command jobs"),
    ("job_templates", {**J_WEEKLY, "cron": "every monday"}, "5-field cron"),
    ("job_templates", {**J_WEEKLY, "prompt": ""}, "needs a prompt"),
    ("job_templates", {**J_WEEKLY, "allow_tools": "yes"}, "true or false"),
    ("layouts", {**L_FOCUS, "order": ["thread:finance:main"]}, "thread widgets are realm-specific"),
    ("layouts", {**L_FOCUS, "spans": {"register": 99}}, "integer 4–20"),
    ("layouts", {**L_FOCUS, "order": ["register", "register"]}, "twice"),
    ("layouts", {**L_FOCUS, "heights": {"usage": 300}}, "isn't in order"),
])
def test_a_bad_contribution_is_skipped_and_its_neighbours_load(dirs, kind, entry, why):
    app, realm = dirs
    good = {"widgets": W_LINKS, "filters": {**F_JOBS, "id": "other"}, "themes": {**T_SEA, "id": "other"},
            "job_templates": {**J_WEEKLY, "id": "other"}, "layouts": {**L_FOCUS, "id": "other"}}[kind]
    if kind == "widgets":
        entry = {**entry, "id": "bad"}
    put(app, "demo", manifest(**{kind: [entry, good]}))
    reg = addons.load(realm)
    assert [i["id"] for i in reg.get(kind)] == [good["id"]]
    assert any(why in r for r in reasons(reg)), reasons(reg)


def test_duplicate_ids_and_unknown_kinds_and_too_many(dirs, monkeypatch):
    app, realm = dirs
    monkeypatch.setattr(addons, "MAX_PER_KIND", 2)
    put(app, "demo", manifest(widgets=[W_MD, W_MD], filters=[F_JOBS] * 3, gadgets=[{"id": "x"}],
                              themes=[T_SEA]))
    reg = addons.load(realm)
    rs = reasons(reg)
    assert len(reg.get("widgets")) == 1 and any("duplicate id" in r for r in rs)
    assert reg.get("filters") == [] and any("the limit is 2" in r for r in rs)
    assert any("unknown kind 'gadgets'" in r for r in rs)
    assert len(reg.get("themes")) == 1                                    # the rest still loaded


def test_unknown_keys_are_ignored_for_forward_compatibility(dirs):
    app, realm = dirs
    put(app, "demo", {**manifest(widgets=[{**W_MD, "icon": "sun"}]), "homepage": "https://x"})
    reg = addons.load(realm)
    assert reg.problems == [] and "icon" not in reg.get("widgets")[0]


# ---- the contract stays in step with the app it describes -----------------------------------------

def test_filter_vocabularies_match_the_lists_the_app_renders():
    from armada import capabilities
    from armada.webui import schedfmt
    assert list(addons.JOB_STATUS) == [v for v, _ in schedfmt._STATUS_FILTERS]
    assert list(addons.JOB_CADENCE) == [v for v, _ in schedfmt._CADENCE_FILTERS]
    assert tuple(addons.CAP_KINDS) == tuple(capabilities.KINDS)


def test_layout_clamps_match_what_the_dashboard_saves(tmp_path):
    from armada import serve

    class H(serve.Handler):
        def __init__(self, realm):
            self.realm = str(realm)

    H(tmp_path)._save_dashboard({"spans": {"a": 1, "b": 99}, "heights": {"a": 1, "b": 99999}})
    d = json.loads((tmp_path / "dashboard.json").read_text(encoding="utf-8"))
    assert (d["spans"]["a"], d["spans"]["b"]) == (addons.SPAN_MIN, addons.SPAN_MAX)
    assert (d["heights"]["a"], d["heights"]["b"]) == (addons.HEIGHT_MIN, addons.HEIGHT_MAX)


def test_the_example_in_the_contract_doc_loads_cleanly(dirs):
    """docs/dev/EXTENSION_POINTS.md's worked example is the first thing anyone (or Alexander) copies."""
    app, realm = dirs
    m = re.search(r"<!-- example:addon.json -->\s*```json\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S)
    assert m, "the doc's example block is missing its marker"
    ex = json.loads(m.group(1))
    put(app, ex["id"], ex)
    reg = addons.load(realm)
    assert reg.problems == [], reg.problems
    assert all(reg.get(k) for k in addons.KINDS), "the example should show every kind"
