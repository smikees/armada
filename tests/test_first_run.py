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


def test_every_page_is_the_welcome_page(srv):
    for path in ("/", "/settings", "/jobs", "/agent/pm"):
        html = srv.get(path)
        assert "Welcome to ARMADA" in html and "Choose ARMADA’s folder" in html, path
        assert 'id="mc-authbar"' in html and "authbar.js" in html      # sign-in matters from minute one


def test_static_assets_still_load(srv):
    code, body = _status(srv, "GET", "/static/js/welcome.js")
    assert code == 200 and "mcWelcomeCreate" in body


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
