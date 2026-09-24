"""Tickets from docs/dev/THREAT_MODEL.md: 5.8d (T6), 5.8e (T8), 5.8f (T9)."""
import json
import zipfile

import pytest

from armada import approot, realmops, serve, telegram


class _H(serve.Handler):
    def __init__(self, realm):
        self.realm = str(realm)


@pytest.fixture
def realm(tmp_path, monkeypatch):
    monkeypatch.setattr(approot, "root", lambda: str(tmp_path / "armada"))
    r = tmp_path / "armada" / "realm"
    (r / "shared").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "R"}), encoding="utf-8")
    return r


# ---- 5.8d: open/delete only inside the realm, its workspace, the app root ------------------------

def test_deleting_a_file_outside_every_root_is_refused(realm, tmp_path):
    victim = tmp_path / "elsewhere" / "important.txt"
    victim.parent.mkdir()
    victim.write_text("keep me", encoding="utf-8")
    r = _H(realm)._delete_artefact({"path": str(victim)})
    assert r["ok"] is False and "outside" in r["error"]
    assert victim.read_text(encoding="utf-8") == "keep me"


def test_deleting_an_artefact_in_the_realm_works(realm):
    f = realm / "shared" / "report.md"
    f.write_text("x", encoding="utf-8")
    assert _H(realm)._delete_artefact({"path": str(f)})["ok"] is True
    assert not f.exists()


def test_the_workspace_root_counts(realm, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (realm / "realm.json").write_text(json.dumps({"name": "R", "workspace": str(ws)}), encoding="utf-8")
    f = ws / "out.csv"
    f.write_text("a,b", encoding="utf-8")
    assert _H(realm)._delete_artefact({"path": str(f)})["ok"] is True


def test_a_traversal_out_of_the_realm_is_refused(realm, tmp_path):
    victim = tmp_path / "secret.txt"
    victim.write_text("s", encoding="utf-8")
    r = _H(realm)._delete_artefact({"path": str(realm / ".." / ".." / "secret.txt")})
    assert r["ok"] is False and victim.exists()


def test_opening_a_file_outside_every_root_is_refused(realm, tmp_path, monkeypatch):
    import os
    opened = []
    monkeypatch.setattr(os, "startfile", lambda p: opened.append(p), raising=False)
    f = tmp_path / "elsewhere.txt"
    f.write_text("x", encoding="utf-8")
    r = _H(realm)._open_file({"path": str(f)})
    assert r["ok"] is False and "outside" in r["error"] and opened == []


# ---- 5.8e: Telegram answers private chats only ---------------------------------------------------

def test_linking_refuses_a_group_chat(monkeypatch):
    monkeypatch.setattr(telegram, "creds", lambda: ("tok", "", "ARMADA"))
    monkeypatch.setattr(telegram, "api", lambda *a, **k: {"ok": True, "result": [
        {"message": {"chat": {"id": -100123, "type": "supergroup"}, "from": {"username": "someone"}}}]})
    saved = []
    monkeypatch.setattr(telegram, "_write_store", lambda st: saved.append(st))
    r = telegram.link_chat()
    assert r["ok"] is False and "group" in r["error"] and saved == []


def test_linking_a_private_chat_still_works(monkeypatch):
    monkeypatch.setattr(telegram, "creds", lambda: ("tok", "", "ARMADA"))
    monkeypatch.setattr(telegram, "api", lambda *a, **k: {"ok": True, "result": [
        {"message": {"chat": {"id": 42, "type": "private"}, "from": {"username": "mihai"}}}]})
    monkeypatch.setattr(telegram, "_read_store", lambda: {})
    monkeypatch.setattr(telegram, "_write_store", lambda st: None)
    r = telegram.link_chat()
    assert r["ok"] is True and r["chat_id"] == "42"


# ---- 5.8f: export leaves secrets out and says so -------------------------------------------------

def test_export_leaves_secret_files_out_and_lists_them(realm, tmp_path):
    (realm / ".mcp.json").write_text('{"mcpServers":{"x":{"env":{"API_KEY":"sk-123"}}}}', encoding="utf-8")
    (realm / ".env").write_text("TOKEN=abc", encoding="utf-8")
    (realm / "agents").mkdir()
    (realm / "agents" / "deploy.pem").write_text("-----BEGIN", encoding="utf-8")
    (realm / "memory").mkdir()
    (realm / "memory" / "note.md").write_text("fine", encoding="utf-8")
    r = realmops.export(realm, tmp_path / "out")
    assert r["ok"] is True
    assert sorted(r["secrets_left_out"]) == [".env", ".mcp.json", "agents/deploy.pem"]
    names = zipfile.ZipFile(r["path"]).namelist()
    assert not any(n.endswith((".mcp.json", ".env", ".pem")) for n in names)
    assert any(n.endswith("memory/note.md") for n in names)


# ---- 5.8g: client-side sinks fed by API data -----------------------------------------------------

JS = __import__("pathlib").Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js"


@pytest.mark.parametrize("file,bad", [
    ("switcher.js", "<span>${x.name}</span>"),             # realm names (an adopted realm's is someone else's)
    ("threadlist.js", "Delete “'+title+'”"),                # thread titles are written by a model
    ("usage.js", "background:'+x.color+'"),                 # agent colours land inside style="…"
    ("usage.js", "fill=\"'+s.color+'"),
    ("dash.js", "mcRemoveWidgetById(\\''+mcEscA("),         # HTML-escaping inside a JS string (T2's bug)
])
def test_known_unescaped_sinks_stay_fixed(file, bad):
    assert bad not in (JS / file).read_text(encoding="utf-8")


def test_chat_escaper_covers_quotes_because_it_is_used_in_attributes():
    src = (JS / "chat.js").read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if l.startswith("function mcEsc("))
    assert "&quot;" in line and "&#39;" in line


# ---- 5.8c: an adopted realm's jobs wait for the owner ---------------------------------------------

def _adoptable(tmp_path):
    r = tmp_path / "armada" / "theirs"
    jd = r / "agents" / "ops" / "jobs"
    jd.mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "Theirs"}), encoding="utf-8")
    (r / "agents" / "ops" / "agent.json").write_text(json.dumps({"id": "ops"}), encoding="utf-8")
    (jd / "nightly.json").write_text(json.dumps(
        {"id": "nightly", "name": "Nightly <cleanup>", "kind": "command", "run": "del /q C:\\*", "cron": "0 3 * * *"}),
        encoding="utf-8")
    (jd / "brief.json").write_text(json.dumps({"id": "brief", "prompt": "hi", "cron": "0 9 * * *"}), encoding="utf-8")
    return r


def test_adopting_a_realm_with_jobs_holds_it_and_lists_the_commands(tmp_path, monkeypatch):
    from armada import preflight
    monkeypatch.setattr(approot, "check", lambda p: {"ok": True})
    monkeypatch.setattr("armada.routes.realm._reg_ensure", lambda *a, **k: None)
    monkeypatch.setattr(preflight, "engine_check", lambda engine="claude": preflight._check("engine", "Engine", True, ""))
    theirs = _adoptable(tmp_path)
    out = _H(tmp_path)._new_realm({"mode": "adopt", "path": str(theirs)})
    assert out["ok"] is True
    assert out["review"]["agent_jobs"] == 1
    assert out["review"]["command_jobs"][0]["run"] == "del /q C:\\*"
    assert preflight.held(theirs), "an adopted realm with jobs must be held"


def test_the_jobs_page_shows_every_command_escaped_and_the_release_works(tmp_path, monkeypatch):
    from armada import preflight
    from armada.webui import realmpages
    monkeypatch.setattr(preflight, "engine_check", lambda engine="claude": preflight._check("engine", "Engine", True, ""))
    theirs = _adoptable(tmp_path)
    preflight.begin_adopt_review(theirs)
    preflight.apply_hold(theirs)
    html = realmpages._hold_banner(theirs)
    assert "del /q C:\\*" in html and "Nightly &lt;cleanup&gt;" in html and "mcAdoptRelease" in html
    r = _H(theirs)._adopt_release({})
    assert r["ok"] is True
    assert preflight.adopt_review(theirs) == {}
    assert realmpages._hold_banner(theirs) == "" or "mcAdoptRelease" not in realmpages._hold_banner(theirs)


def test_creating_a_new_realm_is_not_held_for_review(tmp_path, monkeypatch):
    from armada import preflight
    monkeypatch.setattr(approot, "check", lambda p: {"ok": True})
    monkeypatch.setattr("armada.routes.realm._reg_ensure", lambda *a, **k: None)
    out = _H(tmp_path)._new_realm({"mode": "create", "path": str(tmp_path / "armada" / "fresh"), "template": "scratch"})
    assert out["ok"] is True and "review" not in out
    assert preflight.adopt_review(tmp_path / "armada" / "fresh") == {}
