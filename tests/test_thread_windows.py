"""Independent views share a persisted conversation and retain their realm identity."""
import http.client
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import MagicMock, Mock
from urllib.parse import urlencode

import pytest

from armada import app, reader, serve, thread_windows, util
from armada.execution import RunSession
from armada.request_context import RealmContext, RunContext
from armada.threads import Thread
from armada.webui import thread_window, threadsview
from golden_support import ServedRealm, build_fixture


@pytest.fixture
def realm(tmp_path):
    return build_fixture(tmp_path / "realm")


def request(server, route, context, body=None, companion=False):
    headers = {**server.auth_headers(), "X-Armada-Realm": context.realm_id,
               "Content-Type": "application/json"}
    if companion:
        headers["X-Armada-Companion"] = "thread"
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    try:
        conn.request("POST" if body is not None else "GET", route,
                     json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def test_companion_renders_same_conversation_controls_and_crescent(realm):
    agent_file = Path(realm) / "agents/captain/agent.json"
    cfg = util.read_json_state(agent_file)
    cfg["color"] = "#e0a040"
    util.write_json_atomic(agent_file, cfg)
    # Find by identity: fixture order is not an API contract.
    a = next(a for a in reader.read(realm).agents if a.id == "captain")
    expected = threadsview._render_turns(realm, a, "main")
    rendered = thread_window.render(realm, "captain", "main")
    assert expected in rendered
    assert "mc-avdisc" in rendered and "#e0a040" in rendered
    for control in ("mc-msg", "mc-send", "mc-stop", "mc-plus", "mc-file", "mc-cttitle"):
        assert f'id="{control}"' in rendered
    for script in ("chat", "thread_sync", "threadlist", "confirm", "thread_window", "font_size"):
        assert f'/js/{script}.js' in rendered
    assert "mc-thgrid" not in rendered and 'id="mc-rail"' not in rendered
    assert "pywebview-drag-region" in rendered and "data-thread-close" in rendered


def test_every_thread_has_accessible_open_action(realm):
    Thread(Path(realm) / "agents/captain", "other").append("Question", "Answer")
    a = next(a for a in reader.read(realm).agents if a.id == "captain")
    rendered = threadsview._tab_threads(reader.read(realm), Path(realm), a, "main")
    assert rendered.count('class="mc-thread-detach"') == 2
    assert rendered.count('>Detach thread</span>') == 2
    assert "mc-thread-popout" not in rendered
    other_menu = rendered.split('data-slug="other"', 1)[1].split('class="mc-thmenu"', 1)[1]
    assert other_menu.index(">Pin</span>") < other_menu.index(">Detach thread</span>") < other_menu.index(">Mark as")



@pytest.mark.parametrize("agent,thread", [("../captain", "main"), ("captain", "../main"),
                                         ("missing", "main"), ("captain", "missing")])
def test_invalid_targets_never_create_or_fall_back(realm, agent, thread):
    before = sorted(str(p) for p in Path(realm).rglob("*"))
    with pytest.raises((util.StateError, util.UnsafeSegment)):
        thread_windows.target(realm, agent, thread)
    assert sorted(str(p) for p in Path(realm).rglob("*")) == before


def test_state_detects_messages_renames_and_live_progress(realm):
    context = RunContext.capture(realm, "captain", "main", "live")
    th = Thread(Path(realm) / "agents/captain", "main")
    first = thread_windows.state(realm, "captain", "main")
    assert "All hands accounted for." in first["html"]
    assert "html" not in thread_windows.state(realm, "captain", "main", first["revision"])
    with RunSession(context):
        turn = th.begin_turn("A question from the other window")
        th.save_progress(turn, "A partial reply", "Checking", [])
        active = thread_windows.state(realm, "captain", "main", first["revision"])
        assert active["run_id"] == "live"
        assert "A question from the other window" in active["html"]
        assert "A partial reply" in active["html"]
        th.complete_turn(turn, "Final answer")
    final = thread_windows.state(realm, "captain", "main", active["revision"])
    assert not final["run_id"] and "Final answer" in final["html"]
    th.truncate(0)
    empty = thread_windows.state(realm, "captain", "main", final["revision"])
    assert "No messages yet" in empty["html"]


def test_open_route_returns_bound_destination_and_unavailable_is_explicit(realm, monkeypatch):
    monkeypatch.setattr(app, "open_thread", lambda *args: False)
    ctx = RealmContext.capture(realm)
    with ServedRealm(realm) as server:
        result = server.post("/api/open-thread-window", {"agent": "captain", "thread": "main"})
        assert result["ok"] and not result["native"]
        assert ctx.realm_id in result["url"]
        rendered = server.get(result["url"])
        assert 'name="armada-companion" content="thread"' in rendered
        assert 'name="armada-realm" content="' + ctx.realm_id in rendered
        status, data = request(server, "/api/thread-state?agent=captain&thread=missing", ctx)
        assert status == 404 and json.loads(data)["unavailable"]
        status, data = request(server, "/thread-window?agent=captain&thread=missing", ctx)
        assert status == 404 and b"Thread unavailable" in data and b"data-thread-close" in data


def test_companion_stays_bound_after_realm_switch_without_enabling_stale_main_pages(realm, tmp_path):
    a = RealmContext.capture(realm)
    b = RealmContext.capture(build_fixture(tmp_path / "other"))
    with ServedRealm(realm) as server:
        assert request(server, "/switch?" + urlencode({"path": b.root}), a)[0] == 302
        route = "/api/thread-state?agent=captain&thread=main"
        assert request(server, route, a)[0] == 409
        assert request(server, route, a, companion=True)[0] == 200
        body = {"agent": "captain", "thread": "main", "action": "rename", "title": "Window in A"}
        assert request(server, "/api/thread-action", a, body)[0] == 409
        status, data = request(server, "/api/thread-action", a, body, companion=True)
        assert status == 200 and json.loads(data)["ok"]
        assert thread_windows.state(a.root, "captain", "main")["title"] == "Window in A"
        assert thread_windows.state(b.root, "captain", "main")["title"] != "Window in A"
        assert request(server, "/api/save-agent", a, {"agent": "captain"}, companion=True)[0] == 409
        assert request(server, route, RealmContext("", "unknown"), companion=True)[0] == 409


def test_other_view_can_stop_only_original_realms_run(realm, tmp_path):
    a = RunContext.capture(realm, "captain", "main", "same-run-id")
    b = RunContext.capture(build_fixture(tmp_path / "B"), "captain", "main", "same-run-id")
    with ServedRealm(realm) as server, RunSession(a) as run_a, RunSession(b) as run_b:
        proc_a, proc_b = Mock(), Mock()
        run_a.bind(proc_a); run_b.bind(proc_b)
        request(server, "/switch?" + urlencode({"path": b.realm.root}), a.realm)
        assert request(server, "/api/chat-stop?tid=same-run-id", a.realm, companion=True)[0] == 200
        proc_a.kill.assert_called_once()
        proc_b.kill.assert_not_called()


def test_stop_resolves_conversation_even_with_stale_run_id(realm, tmp_path):
    a = RunContext.capture(realm, "captain", "main", "current-run")
    other_thread = RunContext.capture(realm, "captain", "another", "other-thread")
    other_realm = RunContext.capture(build_fixture(tmp_path / "B"), "captain", "main", "other-realm")
    with ServedRealm(realm) as server, RunSession(a) as run, RunSession(other_thread) as sibling, RunSession(other_realm) as outsider:
        proc, sibling_proc, outsider_proc = Mock(), Mock(), Mock()
        run.bind(proc); sibling.bind(sibling_proc); outsider.bind(outsider_proc)
        status, raw = request(server, "/api/chat-stop?agent=captain&thread=main&tid=old-run", a.realm, companion=True)
        assert status == 200 and json.loads(raw) == {"ok": True, "stopped": True}
        proc.kill.assert_called_once()
        sibling_proc.kill.assert_not_called()
        outsider_proc.kill.assert_not_called()
        state = thread_windows.state(realm, "captain", "main")
        assert state["run_id"] == "current-run" and state["stopping"]
        assert state["metrics"]["messages"] == 2


def test_stop_without_admitted_turn_reports_no_cancellation(realm):
    ctx = RealmContext.capture(realm)
    with ServedRealm(realm) as server:
        status, raw = request(server, "/api/chat-stop?agent=captain&thread=main&tid=not-yet-admitted", ctx, companion=True)
        assert status == 200 and json.loads(raw) == {"ok": True, "stopped": False}


def test_failed_process_cancellation_remains_retryable(realm):
    context = RunContext.capture(realm, "captain", "main", "kill-fails")
    with ServedRealm(realm) as server, RunSession(context) as run:
        process = Mock()
        process.kill.side_effect = [OSError("Synthetic kill failure"), None]
        run.bind(process)
        route = "/api/chat-stop?agent=captain&thread=main&tid=stale"
        _, raw = request(server, route, context.realm, companion=True)
        assert json.loads(raw) == {"ok": False, "error": "Synthetic kill failure"}
        assert not thread_windows.state(realm, "captain", "main")["stopping"]
        _, raw = request(server, route, context.realm, companion=True)
        assert json.loads(raw) == {"ok": True, "stopped": True}
        assert thread_windows.state(realm, "captain", "main")["stopping"]
        assert process.kill.call_count == 2


def test_native_windows_reuse_close_reopen_and_separate_realms(realm, tmp_path, monkeypatch):
    other = build_fixture(tmp_path / "other")
    windows = []
    def create(*args, **kwargs):
        window = Mock(events=MagicMock())
        windows.append((window, args, kwargs))
        return window
    monkeypatch.setattr(app, "_main_window", Mock())
    monkeypatch.setattr(app, "_app_url", "http://127.0.0.1:8756/")
    monkeypatch.setattr(app, "_thread_windows", {})
    monkeypatch.setattr(app, "_quitting", False)
    monkeypatch.setattr(app, "_alexander_position", lambda: {"width": 520, "height": 720})
    monkeypatch.setattr(app.threading, "Thread", Mock())
    monkeypatch.setitem(__import__("sys").modules, "webview", Mock(create_window=create))
    monkeypatch.setattr("armada.local_auth.browser_url", lambda base, route: base.rstrip("/") + route)
    assert app.open_thread(realm, "captain", "main")
    assert app.open_thread(realm, "captain", "main")
    assert len(windows) == 1
    window, args, options = windows[0]
    window.show.assert_called_once(); window.restore.assert_called_once()
    assert options["frameless"] and options["transparent"] and not options["easy_drag"]
    assert "thread=main" in args[1] and RealmContext.capture(realm).realm_id in args[1]
    window.width, window.height = 400, 500
    assert options["js_api"].resize_step(-20, -20)
    window.resize.assert_called_once_with(400, 500)
    options["js_api"].close_window()
    window.destroy.assert_called_once()
    key = (RealmContext.capture(realm).realm_id, "captain", "main")
    app._clear_thread_window(key, window)
    assert app.open_thread(realm, "captain", "main")
    app._clear_thread_window(key, window)  # a late close event cannot remove the replacement
    assert app._thread_windows[key] is windows[1][0]
    assert app.open_thread(other, "captain", "main")
    assert len(windows) == 3
    monkeypatch.setattr(app, "_alex_window", None)
    app._quit_windows(app._main_window)
    windows[1][0].destroy.assert_called_once()
    windows[2][0].destroy.assert_called_once()
    assert not app.open_thread(realm, "captain", "main")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for script checks")
@pytest.mark.parametrize("harness", ["thread_sync_harness.js", "thread_window_open_harness.js", "thread_chat_harness.js"])
def test_browser_window_interactions(harness):
    result = subprocess.run(["node", str(Path(__file__).with_name(harness))],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
