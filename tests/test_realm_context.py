"""Realm switches cannot retarget admitted work, content or cancellation (2.17)."""
import http.client
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.parse import urlencode

import pytest

from armada import origins, runner, serve, util
from armada.engine.base import RunResult
from armada.request_context import RealmContext, RunContext, navigation_url
from armada.routes.agents import AgentRoutes
from armada.threads import Thread
from golden_support import ServedRealm, build_fixture


def request(server, path, *, context=None, body=None, port=None):
    conn = http.client.HTTPConnection("127.0.0.1", port or server.port, timeout=10)
    headers = {**server.auth_headers(), "Content-Type": "application/json"}
    if context:
        headers["X-Armada-Realm"] = context.realm_id
    try:
        conn.request("POST" if body is not None else "GET", path,
                     json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


@pytest.fixture
def realms(tmp_path):
    return [RealmContext.capture(build_fixture(tmp_path / name)) for name in ("A", "B")]


def switch(server, context):
    assert request(server, "/switch?" + urlencode({"path": context.root}))[0] == 302


def test_stale_mutations_and_polling_fail_without_touching_either_realm(realms):
    a, b = realms
    with ServedRealm(a.root) as server:
        page = server.get("/")
        assert f'name="armada-realm" content="{a.realm_id}"' in page
        assert page.index('js/realm-context.js') < page.index('js/dash.js')
        switch(server, b)
        before = [(Path(c.root) / "agents/captain/agent.json").read_bytes() for c in realms]
        for context, body in [(None, {}), (a, {}), (b, {"_realm": a.realm_id})]:
            status, _, data = request(server, "/api/save-agent", context=context,
                                      body={"agent": "captain", "display": "WRONG", **body})
            assert status == 409 and json.loads(data)["code"] == "realm_mismatch"
        assert request(server, "/api/agent-activity", context=a)[0] == 409
        assert [(Path(c.root) / "agents/captain/agent.json").read_bytes() for c in realms] == before
        status, _, data = request(server, "/api/save-agent", context=b,
                                  body={"agent": "captain", "display": "Changed in B"})
        assert status == 200 and json.loads(data)["ok"]
        assert (Path(a.root) / "agents/captain/agent.json").read_bytes() == before[0]
        assert util.read_json_state(Path(b.root) / "agents/captain/agent.json")["display"] == "Changed in B"


def test_content_urls_keep_their_realm_across_switches(realms):
    a, b = realms
    for context in realms:
        root = Path(context.root)
        (root / "icon.png").write_bytes(context.realm_id.encode())
        site = root / "shared/site"
        site.mkdir()
        (site / "index.html").write_text('<html><head></head><script src="app.js"></script></html>')
        (site / "app.js").write_text(context.realm_id)
        config = util.read_json_state(root / "realm.json")
        config["sections"].append({"name": "Site", "assets": str(site), "entry": "index.html"})
        util.write_json_atomic(root / "realm.json", config)
    with ServedRealm(a.root) as server:
        switch(server, b)
        assert request(server, "/realm-icon")[0] == 409
        assert request(server, "/realm-icon?_realm=unknown")[0] == 409
        assert request(server, f"/r/{a.realm_id}/api/realms")[0] == 409
        assert request(server, f"/realm-icon?_realm={a.realm_id}")[2] == a.realm_id.encode()
        status, _, data = request(server, f"/r/{a.realm_id}/section-raw/1", port=origins.content_port())
        assert status == 200 and f'<base href="/r/{a.realm_id}/section-asset/1/">'.encode() in data
        assert request(server, f"/r/{a.realm_id}/section-asset/1/app.js", port=origins.content_port())[2] == a.realm_id.encode()
        # Notification destinations explicitly select A, then open a bound page in A.
        status, headers, _ = request(server, navigation_url("/agent/captain", a.root))
        assert status == 302 and a.realm_id in headers["Location"]
        assert request(server, headers["Location"])[0] == 200
        assert serve.Handler.realm == a.root


def test_request_capture_is_reset_on_reused_handler(realms, monkeypatch):
    a, b = realms
    handler = object.__new__(serve.Handler)
    handler.headers = {}
    handler.path = "/"
    monkeypatch.setattr(serve.Handler, "realm", a.root)
    handler._bind_request()
    monkeypatch.setattr(serve.Handler, "realm", b.root)
    assert handler.realm == a.root
    handler._bind_request()
    assert handler.realm == b.root


def test_same_ids_in_two_realms_keep_turns_reports_titles_and_cancellation_separate(realms, monkeypatch):
    a, b = realms
    started = {c.root: threading.Event() for c in realms}
    release = {c.root: threading.Event() for c in realms}
    titled = {c.root: threading.Event() for c in realms}
    killed = []
    errors = []
    workers = []
    title_roots = []
    contexts = [RunContext.capture(c.root, "captain", "new-chat-race", "same-run") for c in realms]

    class Engine:
        name = "mock"
        def run_stream(self, *, cwd, on_proc, on_event, **kwargs):
            root = str(Path(cwd).parent.parent)
            class Process:
                def kill(self):
                    killed.append(root)
                    release[root].set()
            on_proc(Process())
            on_event({"kind": "text", "text": "partial " + root})
            started[root].set()
            assert release[root].wait(15)
            (Path(cwd) / "result.txt").write_text(root)
            return RunResult(root not in killed, "answer " + root)

    monkeypatch.setattr(runner, "get_engine", lambda *args, **kwargs: Engine())
    def title(adir, message):
        title_roots.append(str(Path(adir).parent.parent))
        return "Title in A"
    monkeypatch.setattr("armada.routes.agents._llm_title", title)
    original_title = AgentRoutes._autoname_thread
    def autoname(self, agent, thread, message, context):
        try:
            return original_title(self, agent, thread, message, context)
        finally:
            titled[context.realm.root].set()
    monkeypatch.setattr(AgentRoutes, "_autoname_thread", autoname)

    with ServedRealm(a.root) as server:
        def stream(context):
            conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=20)
            try:
                conn.request("POST", "/api/chat-stream", json.dumps({"agent": "captain", "thread": "new-chat-race",
                             "message": "ping", "tid": "same-run"}),
                             {**server.auth_headers(), "Content-Type": "application/json", "X-Armada-Realm": context.realm_id})
                response = conn.getresponse()
                assert response.status == 200
                while line := response.readline():
                    if line.startswith(b"data: "):
                        event = json.loads(line[6:])
                        assert event["kind"] != "error", event
                        if event["kind"] == "done":
                            return
                raise AssertionError("stream ended without completion")
            except BaseException as exc:
                errors.append(exc)
            finally:
                conn.close()
        try:
            for c in realms:
                if c == b:
                    switch(server, b)
                worker = threading.Thread(target=stream, args=(c,))
                workers.append(worker)
                worker.start()
                assert started[c.root].wait(10), errors
            assert all(c.marker.is_file() for c in contexts)
            # Duplicate admission must leave the original registry entry untouched.
            entry = serve.Handler._streams[contexts[1].key]
            assert request(server, "/api/chat-stream", context=b,
                           body={"agent": "captain", "thread": "new-chat-race", "tid": "same-run", "message": "duplicate"})[0] == 409
            assert serve.Handler._streams[contexts[1].key] is entry
            release[a.root].set()
            assert titled[a.root].wait(10)
            assert not contexts[0].marker.exists() and contexts[1].marker.exists()
            meta = util.read_json_state(Path(a.root) / "agents/captain/threads/meta.json")
            assert meta["titles"]["new-chat-race"] == "Title in A"
            assert meta["unread"]["new-chat-race"]
            meta_b = util.read_json_state(Path(b.root) / "agents/captain/threads/meta.json", default=dict)
            assert not meta_b.get("titles", {}).get("new-chat-race")
            assert not meta_b.get("unread", {}).get("new-chat-race")
            assert title_roots == [a.root]
            assert request(server, "/api/chat-stop?tid=same-run", context=a)[0] == 200
            assert killed == [] and contexts[1].key in serve.Handler._streams
            assert request(server, "/api/chat-stop?tid=same-run", context=b)[0] == 200
            for worker in workers:
                worker.join(10)
            assert not errors and killed == [b.root]
            for c, run in zip(realms, contexts):
                adir = Path(c.root) / "agents/captain"
                assert (adir / "result.txt").read_text() == c.root
                messages = Thread(adir, "new-chat-race").snapshot()[1]
                assert any("answer " + c.root in m.get("content", "") for m in messages)
                reports = [json.loads(line) for p in (adir / "runs").glob("*.jsonl")
                           for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
                assert any(r.get("realm_id") == c.realm_id and r.get("run_id") == "same-run" for r in reports)
                assert not run.marker.exists() and run.key not in serve.Handler._streams
        finally:
            for event in release.values():
                event.set()
            for worker in workers:
                worker.join(20)


def test_cancel_before_process_creation_and_header_failure_cleanup(realms, monkeypatch):
    a, _ = realms
    killed = []
    class Handler(AgentRoutes):
        realm = a.root
        _streams = {}
        wfile = io.BytesIO()
        send_response = send_header = end_headers = lambda *args: None
    handler = Handler()
    def stream(*args, on_proc, **kwargs):
        assert handler._chat_stop({"tid": "early"})["ok"]
        class Process:
            def kill(self): killed.append(True)
        on_proc(Process())
        return {"ok": False}
    monkeypatch.setattr(runner, "chat_stream", stream)
    handler._chat_stream({"agent": "captain", "tid": "early"})
    assert killed == [True] and not Handler._streams
    def broken(*args): raise ConnectionError("closed before headers")
    handler.end_headers = broken
    with pytest.raises(ConnectionError):
        handler._chat_stream({"agent": "captain", "tid": "broken"})
    assert not Handler._streams


def test_runner_refuses_mismatched_context_before_starting(realms):
    a, b = realms
    context = RunContext.capture(a.root, "captain")
    with pytest.raises(ValueError, match="context"):
        runner.chat_stream(b.root, "captain", "main", "ping", lambda e: None, context=context)


def test_reusing_a_run_id_cannot_lose_the_new_activity_marker(realms, monkeypatch):
    a, _ = realms
    context = RunContext.capture(a.root, "captain", "main", "reused")
    deleting, allow_delete, attempted, second_started, finish_second = [threading.Event() for _ in range(5)]
    errors = []
    original_unlink = Path.unlink
    first_delete = True
    def unlink(path, *args, **kwargs):
        nonlocal first_delete
        if path == context.marker and first_delete:
            first_delete = False
            deleting.set()
            assert allow_delete.wait(10)
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", unlink)
    class Handler(AgentRoutes):
        realm = a.root
        _streams = {}
        send_response = send_header = end_headers = lambda *args: None
        def __init__(self): self.wfile = io.BytesIO()
    def stream(root, agent, thread, message, **kwargs):
        if message == "second":
            second_started.set()
            assert finish_second.wait(10)
        return {"ok": False}
    monkeypatch.setattr(runner, "chat_stream", stream)
    def run(message):
        try:
            if message == "second": attempted.set()
            Handler()._chat_stream({"agent": "captain", "tid": "reused", "message": message})
        except BaseException as exc:
            errors.append(exc)
    first = threading.Thread(target=run, args=("first",))
    second = threading.Thread(target=run, args=("second",))
    try:
        first.start()
        assert deleting.wait(10)
        second.start()
        assert attempted.wait(10)
        assert not second_started.wait(0.1)  # admission waits for the previous marker cleanup
        allow_delete.set()
        assert second_started.wait(10)
        first.join(10)
        assert context.marker.exists() and context.key in Handler._streams
        finish_second.set()
        second.join(10)
        assert not errors and not context.marker.exists() and not Handler._streams
    finally:
        allow_delete.set()
        finish_second.set()
        for worker in (first, second):
            if worker.ident: worker.join(15)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for the browser harness")
def test_browser_requests_keep_the_document_identity():
    result = subprocess.run(["node", str(Path(__file__).with_name("realm_context_harness.js"))],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
