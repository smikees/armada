"""First run (launch plan 5.3): with no realm to open, the app shows a welcome page instead of
exiting with a sentence nobody sees (pythonw has no console).

Drives a real server started with no realm, because the thing under test is the server's
behaviour in that mode: which routes answer, what every other route does, and the hand-over into
the normal app once a realm exists.
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from golden_support import ServedRealm
from armada import schedsvc, serve


@pytest.fixture
def srv(monkeypatch):
    started = []
    monkeypatch.setattr(schedsvc, "ensure_running", lambda root: started.append(root) or {"ok": True})
    with ServedRealm("") as s:
        s.scheduler_started = started
        yield s
    serve.Handler.realm = "."
    serve.Handler.welcome_note = ""


def _status(srv, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(srv.base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def test_every_page_is_the_setup_wizard(srv):
    for path in ("/", "/settings", "/jobs", "/agent/pm"):
        html = srv.get(path)
        assert "Welcome to ARMADA" in html and "ARMADA’s folder" in html, path
        for step in ("welcome", "checks", "home", "team"):
            assert f'class="mc-su-pane" data-step="{step}"' in html, (path, step)
        assert "mcSuSignIn" in html and "Install Claude Code" in html   # sign-in matters from minute one


def test_static_assets_still_load(srv):
    code, body = _status(srv, "GET", "/static/js/setup.js")
    assert code == 200 and "mcSuAppoint" in body
    with urllib.request.urlopen(srv.base + "/static/alexander.png", timeout=10) as r:
        assert r.status == 200 and r.read(4) == b"\x89PNG"


def test_other_api_calls_are_refused_not_crashed(srv):
    assert _status(srv, "GET", "/api/realms")[0] == 409
    code, body = _status(srv, "POST", "/api/save-user", {"name": "x"})
    assert code == 409 and json.loads(body)["ok"] is False


def test_create_needs_the_folder_first(srv):
    r = srv.post("/api/first-realm", {"name": "Home"})
    assert r["ok"] is False and "folder first" in r["error"]


def test_the_suggested_folder_is_created_but_not_a_whole_tree(srv, tmp_path):
    r = srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    assert r["ok"] and (tmp_path / "ARMADA").is_dir()
    r = srv.post("/api/set-approot", {"root": str(tmp_path / "no" / "such" / "place"), "create": True})
    assert r["ok"] is False and not (tmp_path / "no").exists()


def test_first_realm_lands_in_the_root_named_after_itself(srv, tmp_path):
    root = tmp_path / "ARMADA"
    srv.post("/api/set-approot", {"root": str(root), "create": True})
    r = srv.post("/api/first-realm", {"name": "  My   Team ", "template": "scratch"})
    assert r["ok"], r
    assert Path(r["path"]) == (root / "My Team").resolve() and (root / "My Team" / "realm.json").exists()
    r2 = srv.post("/api/first-realm", {"name": "My Team"})
    assert Path(r2["path"]).name == "My Team 2"          # never over an existing folder
    r3 = srv.post("/api/first-realm", {"name": 'a/b:c?'})
    assert Path(r3["path"]).name == "abc"                # no path tricks through the name
    assert srv.post("/api/first-realm", {"name": "///"})["ok"] is False


def test_switching_into_the_new_realm_leaves_welcome_mode(srv, tmp_path):
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    r = srv.post("/api/first-realm", {"name": "Work"})
    srv.get("/switch?path=" + urllib.request.quote(r["path"], safe=""))
    html = srv.get("/")
    assert "Welcome to ARMADA" not in html and 'id="mc-schedbar"' in html
    assert srv.scheduler_started == [r["path"]]          # the launch-time start had nothing to start for


def test_known_realms_are_offered_when_none_was_remembered(srv, tmp_path):
    from armada.routes._shared import _reg_ensure
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    a = srv.post("/api/first-realm", {"name": "Alpha"})["path"]
    _reg_ensure(a, "Alpha")
    html = srv.get("/")
    assert "Pick up where you left off" in html and "Alpha" in html and "/switch?path=" in html


def test_cli_opens_the_welcome_page_instead_of_exiting(monkeypatch, tmp_path):
    from armada import cli
    calls = []
    monkeypatch.setattr(serve, "serve", lambda realm, port: calls.append(realm))
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    try:
        assert cli.main(["serve", str(tmp_path / "gone")]) == 0
        assert calls == [""]
        assert "isn't a realm folder" in serve.Handler.welcome_note
    finally:
        serve.Handler.welcome_note = ""


# ---- the setup wizard's second half (6.4) --------------------------------------------------------

def _wizard_realm(srv, tmp_path, **extra):
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    r = srv.post("/api/first-realm", {"name": "Home", "template": "company", "owner": "Mihai",
                                      "wizard": True, **extra})
    assert r["ok"], r
    srv.get("/switch?path=" + urllib.request.quote(r["path"], safe=""))
    return Path(r["path"])


def test_a_wizard_realm_resumes_setup_until_it_is_finished(srv, tmp_path):
    root = _wizard_realm(srv, tmp_path)
    cfg = json.loads((root / "realm.json").read_text("utf-8"))
    assert cfg["setup"]["step"] == "capabilities" and cfg["user"]["name"] == "Mihai"
    html = srv.get("/")                                   # redirected to /setup
    assert 'data-step="capabilities"' in html and "Add these" in html and "Low risk" in html
    assert srv.post("/api/setup-step", {"step": "tour"})["ok"]
    assert json.loads((root / "realm.json").read_text("utf-8"))["setup"]["step"] == "tour"
    assert srv.post("/api/setup-step", {"step": "nowhere"})["ok"] is False
    assert srv.post("/api/setup-finish", {})["ok"]
    assert "setup" in json.loads((root / "realm.json").read_text("utf-8"))
    assert 'id="mc-schedbar"' in srv.get("/")             # the normal app from now on


def test_the_wizard_builds_the_team_on_the_server(srv, tmp_path):
    root = _wizard_realm(srv, tmp_path, keep=["cfo"], extra=[{"display": "Ada Lovelace", "role": "Engines"},
                                                           {"display": "<script>", "role": ""}])
    ids = sorted(p.name for p in (root / "agents").iterdir())
    assert ids == ["ada-lovelace", "cfo", "script"]
    coords = [json.loads((root / "agents" / i / "agent.json").read_text("utf-8"))["coordinator"] for i in ids]
    assert coords.count(True) == 1                          # someone always leads
    mandate = (root / "agents" / "cfo" / "mandate.md").read_text("utf-8")
    assert len(mandate) > 40                                # the template's instructions, not the page's


def test_only_recommended_capabilities_go_through_the_wizard(srv, tmp_path):
    _wizard_realm(srv, tmp_path)
    r = srv.post("/api/setup-capability", {"key": "marketplace:claude-plugins-official/desktop-commander"})
    assert r["ok"] is False and "recommended" in r["error"]


def test_an_empty_team_is_refused(srv, tmp_path):
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    r = srv.post("/api/first-realm", {"name": "Empty", "template": "scratch", "keep": [], "extra": [], "wizard": True})
    assert r["ok"] is False and "at least one" in r["error"]
