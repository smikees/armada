"""Socket-level stress cases use a synthetic handler; no jobs or providers run."""
import http.client
import json
import socket
import threading
import time

import pytest

from armada import http_limits, serve


@pytest.fixture
def server(monkeypatch, tmp_path):
    monkeypatch.setattr(http_limits, "LANES", {"ordinary": 2, "stream": 2, "control": 1})
    monkeypatch.setattr(http_limits, "PENDING_CONNECTIONS", 8)
    monkeypatch.setattr(http_limits, "HEADER_SECONDS", 0.6)
    monkeypatch.setattr(http_limits, "BODY_SECONDS", 0.5)
    monkeypatch.setattr(serve.local_auth.util, "data_dir", lambda: tmp_path)
    calls = []
    class Handler(serve.Handler):
        def _bind_request(self, *, mutation=False):
            self._body_cache = None
            if mutation:
                self._body()

        def _route_post(self):
            calls.append(self._body())
            if self.path == "/api/chat-stream" and hasattr(self.server, "stream_release"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                assert self.server.stream_release.wait(2)
                self.wfile.write(b'data: {"done":true}\n\n')
                return
            self._json(200, {"accepted": True})

        def _route_get(self):
            self._json(200, {"ok": True})
    httpd = serve._Server(("127.0.0.1", 0), Handler)
    httpd.calls = calls
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


def connect(server):
    return socket.create_connection(server.server_address, timeout=2)


def headers(server, extra=b"", path=b"/restart"):
    return (b"POST " + path + b" HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer "
            + server.auth.token.encode() + b"\r\n" + extra + b"\r\n")


def response(sock):
    reply = http.client.HTTPResponse(sock)
    reply.begin()
    return reply.status, reply.read()


def health(server, path="/health"):
    conn = http.client.HTTPConnection(*server.server_address, timeout=1)
    try:
        conn.request("GET", path, headers={"Authorization": "Bearer " + server.auth.token})
        reply = conn.getresponse()
        reply.read()
        return reply.status
    finally:
        conn.close()


def wait_control_idle(server):
    """A received body is not proof that its worker finished socket cleanup."""
    slot = server._slots['control']  # This fixture deliberately has just one.
    assert slot.acquire(timeout=2), 'Control worker did not finish cleanup'
    slot.release()


@pytest.mark.parametrize("extra,body,status", [
    (b"Content-Length: -1\r\n", b"", 400),
    (b"Content-Length: abc\r\n", b"", 400),
    (b"Content-Length: 2\r\nContent-Length: 2\r\n", b"{}", 400),
    (b"Transfer-Encoding: chunked\r\n", b"0\r\n\r\n", 400),
    (b"Content-Length: 16777217\r\n", b"", 413),
    (b"Content-Length: 3\r\n", b"{x}", 400),
    (b"Content-Length: 2\r\n", b"[]", 400),
    (b"Content-Length: 1\r\n", b"\xff", 400),
    (b"Content-Length: 9\r\n", b'{"x":NaN}', 400),
])
def test_invalid_body_never_dispatches(server, extra, body, status):
    with connect(server) as sock:
        sock.sendall(headers(server, extra) + body)
        code, result = response(sock)
    assert code == status
    assert json.loads(result)["error"]
    assert server.calls == []


def test_valid_and_empty_bodies_remain_usable(server):
    for extra, body in [(b"Content-Length: 7 \t\r\n", b'{"x":1}'), (b"", b"")]:
        with connect(server) as sock:
            sock.sendall(headers(server, extra) + body)
            assert response(sock)[0] == 200
    assert server.calls == [{"x": 1}, {}]


def test_truncated_body_is_reported(server):
    with connect(server) as sock:
        sock.sendall(headers(server, b"Content-Length: 10\r\n") + b"{")
        sock.shutdown(socket.SHUT_WR)
        assert response(sock)[0] == 400
    assert server.calls == []


def test_body_deadline_is_total_not_reset_by_trickling(server):
    with connect(server) as sock:
        sock.sendall(headers(server, b"Content-Length: 100\r\n") + b"{")
        time.sleep(0.2)
        sock.sendall(b" ")
        time.sleep(0.2)
        sock.sendall(b" ")
        started = time.monotonic()
        assert response(sock)[0] == 408
        assert time.monotonic() - started < 0.4
    assert server.calls == []


def test_incomplete_headers_have_deadline_and_size_bound(server):
    with connect(server) as sock:
        sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n")
        assert response(sock)[0] == 408
    with connect(server) as sock:
        sock.sendall(b"GET / HTTP/1.1\r\nX: " + b"x" * http_limits.HEADER_BYTES)
        assert response(sock)[0] == 431
    assert health(server) == 200


def test_idle_client_burst_is_bounded_and_controls_respond(server):
    sockets = [connect(server) for _ in range(32)]
    try:
        assert health(server) == 200
        wait_control_idle(server)
        assert health(server, "/api/chat-stop") == 200
        with server._gate_lock:
            assert len(server._pending) <= 8
            assert len(server._rejecting) <= 8
            assert len(server._active) <= 5
    finally:
        for sock in sockets:
            sock.close()


def test_oversized_headers_deliver_error_with_unread_input(server):
    for _ in range(20):
        with connect(server) as sock:
            sock.sendall(b"GET / HTTP/1.1\r\nX: " + b"x" * (http_limits.HEADER_BYTES * 2))
            code, body = response(sock)
            assert code == 431
            assert json.loads(body)["error"]
    assert health(server) == 200


def test_refused_client_cannot_keep_drain_socket_open(server):
    with connect(server) as sock:
        sock.sendall(b"INVALID\r\n\r\n")
        assert response(sock)[0] == 400
        deadline = time.monotonic() + 1.5
        while server._rejecting and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not server._rejecting
        assert sock.recv(1) == b""
        assert health(server) == 200


@pytest.mark.parametrize("extra,status,authorized", [
    (b"Content-Length: 16777217\r\n", 413, True),
    (b"Content-Length: 100\r\nContent-Length: 100\r\n", 400, True),
    (b"Content-Length: 131072\r\n", 401, False),
])
def test_handler_error_survives_upload_arriving_after_headers(server, extra, status, authorized):
    with connect(server) as sock:
        packet = headers(server, extra)
        if not authorized:
            packet = packet.replace(b"Authorization: Bearer " + server.auth.token.encode() + b"\r\n", b"")
        sock.sendall(packet)
        reply = http.client.HTTPResponse(sock)
        reply.begin()
        assert reply.status == status
        # Model the upload writer racing the error reader. Already-rejected
        # input must be drained without resetting the response or dispatching it.
        sock.sendall(b"x" * 131072)
        assert reply.read()
    assert server.calls == []


def test_saturated_body_and_stream_lanes_leave_control_capacity(server):
    sockets = []
    try:
        for path in (b"/restart", b"/restart", b"/api/chat-stream", b"/api/chat-stream"):
            sock = connect(server)
            sockets.append(sock)
            sock.sendall(headers(server, b"Content-Length: 100\r\n", path))
        deadline = time.monotonic() + 0.4
        while len(server._active) < 4 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(server._active) == 4
        with connect(server) as sock:
            sock.sendall(headers(server))
            assert response(sock)[0] == 503
        assert health(server) == 200
        wait_control_idle(server)
        assert health(server, "/api/chat-stop") == 200
        assert server.calls == []
    finally:
        for sock in sockets:
            sock.close()


def test_control_response_can_arrive_before_worker_releases_capacity(server, monkeypatch):
    cleaning, release = threading.Event(), threading.Event()
    original = server.process_request_thread
    def delayed_cleanup(*args):
        original(*args)
        cleaning.set()
        assert release.wait(2)
    monkeypatch.setattr(server, 'process_request_thread', delayed_cleanup)
    try:
        assert health(server) == 200
        assert cleaning.wait(1)
        # This is concurrent work even though the client received the first body.
        assert health(server, '/api/chat-stop') == 503
        release.set()
        wait_control_idle(server)
        assert health(server, '/api/chat-stop') == 200
    finally:
        release.set()


def test_second_request_cannot_bypass_admission(server):
    with connect(server) as sock:
        sock.sendall(headers(server) + headers(server))
        assert response(sock)[0] == 200
    assert server.calls == [{}]


def test_stream_can_outlive_input_deadline(server):
    server.stream_release = threading.Event()
    try:
        with connect(server) as sock:
            sock.sendall(headers(server, path=b"/api/chat-stream"))
            reply = http.client.HTTPResponse(sock)
            reply.begin()
            assert reply.status == 200
            time.sleep(http_limits.BODY_SECONDS + 0.1)
            server.stream_release.set()
            assert reply.read() == b'data: {"done":true}\n\n'
    finally:
        server.stream_release.set()


def test_server_close_releases_idle_and_active_clients(server, monkeypatch):
    monkeypatch.setattr(http_limits, "BODY_SECONDS", 10)
    monkeypatch.setattr(http_limits, "HEADER_SECONDS", 10)
    with connect(server) as idle, connect(server) as body:
        body.sendall(headers(server, b"Content-Length: 100\r\n"))
        time.sleep(0.05)
        server.shutdown()
        server.server_close()
        assert not server._gate.is_alive()
        assert idle.recv(1) == b""
        assert body.recv(1) == b""
