"""Real HTTP requests cannot gain owner privileges without the local bootstrap."""
import http.client
import json
import threading

import pytest

from armada import local_auth, serve


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(local_auth.util, "data_dir", lambda: tmp_path / "private")
    monkeypatch.setattr(serve.Handler, "realm", str(tmp_path / "realm"))
    httpd = serve._Server(("127.0.0.1", 0), serve.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def request(server, path, method="GET", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


@pytest.mark.parametrize("path", ["/", "/settings", "/api/instance", "/api/realms", "/api/thread-turns"])
def test_unauthenticated_reads_reveal_no_workspace(server, path):
    status, _, body = request(server, path)
    assert status == 401
    assert server.auth.token.encode() not in body
    assert str(server.RequestHandlerClass.realm).encode() not in body


@pytest.mark.parametrize("path", ["/api/run", "/api/save-user", "/restart", "/auth"])
def test_no_origin_is_not_an_authentication_bypass(server, path):
    assert request(server, path, "POST")[0] == 401


def test_bootstrap_is_public_but_contains_no_secret(server):
    status, headers, body = request(server, "/auth")
    assert status == 200 and server.auth.token.encode() not in body
    assert b"history.replaceState" in body
    assert headers["Referrer-Policy"] == "no-referrer"
    assert json.loads(request(server, "/health")[2]) == {"app": "ARMADA"}


def test_browser_exchange_and_internal_client_authenticate(server):
    auth = local_auth.headers(server.server_port)
    status, headers, _ = request(server, "/auth", "POST", auth)
    assert status == 204
    assert "HttpOnly" in headers["Set-Cookie"] and "SameSite=Strict" in headers["Set-Cookie"]
    cookie = {"Cookie": headers["Set-Cookie"].split(";", 1)[0]}
    assert request(server, "/api/instance", headers=cookie)[0] == 200
    assert request(server, "/api/instance", headers=auth)[0] == 200
    assert request(server, "/api/instance", headers={"Authorization": "Bearer invalid"})[0] == 401
    assert request(server, "/api/instance", headers={"Authorization": "Bearer é"})[0] == 401


def test_cookie_does_not_bypass_content_origin_guards(server):
    cookie = {"Cookie": f"{server.auth.cookie_name}={server.auth.token}"}
    origin = f"http://127.0.0.1:{server.server_port + 1}"
    assert request(server, "/restart", "POST", {**cookie, "Origin": origin})[0] == 403
    assert request(server, "/api/instance", headers={**cookie, "Sec-Fetch-Site": "same-site"})[0] == 403


def test_old_session_cleanup_cannot_remove_a_replacement(server):
    old = server.auth
    replacement = local_auth.Session(server.server_port)
    try:
        assert replacement.token != old.token
        old.close()
        assert local_auth.headers(server.server_port) == {"Authorization": "Bearer " + replacement.token}
        assert not replacement.allows({"Authorization": "Bearer " + old.token})
    finally:
        replacement.close()


def test_file_permissions_must_be_set_before_secret_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(local_auth.util, "data_dir", lambda: tmp_path)
    def deny():
        raise PermissionError("cannot protect directory")
    monkeypatch.setattr(local_auth, "_private_directory", deny)
    with pytest.raises(PermissionError):
        local_auth.Session(12345)
    assert not list(tmp_path.rglob("*.json"))


def test_browser_url_uses_fragment_not_query(server):
    url = local_auth.browser_url(f"http://127.0.0.1:{server.server_port}/")
    assert url.endswith("/auth#" + server.auth.token)
    assert "?" not in url
