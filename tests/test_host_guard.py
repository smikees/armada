"""DNS-rebinding guard (found writing the 5.8 threat model, 2026-09-24).

The server binds 127.0.0.1 and blocks cross-origin POSTs by comparing Origin with Host. A page whose
own domain has been re-pointed at 127.0.0.1 defeats that: to the browser it is same-origin, its
Origin and Host agree (both the attacker's name), and a POST to /api/chat-stream starts an agent turn
that runs with the engine's permission prompts skipped. The fix is to refuse any Host that isn't a
local name. These tests drive a real server over HTTP, because the attack is at the HTTP layer.
"""
import http.client
import json

import pytest

from golden_support import ServedRealm, build_fixture
from armada import serve


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    realm = build_fixture(tmp_path_factory.mktemp("hostguard") / "realm")
    with ServedRealm(realm) as s:
        yield s


def _req(srv, method, path, host, origin=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
    headers = {"Host": host}
    if origin:
        headers["Origin"] = origin
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    c.putrequest(method, path, skip_host=True)
    for k, v in headers.items():
        c.putheader(k, v)
    if data:
        c.putheader("Content-Length", str(len(data)))
    c.endheaders(data)
    r = c.getresponse()
    out = (r.status, r.read())
    c.close()
    return out


@pytest.mark.parametrize("host", ["127.0.0.1:{p}", "localhost:{p}", "[::1]:{p}", "127.0.0.1"])
def test_local_names_are_served(srv, host):
    status, _ = _req(srv, "GET", "/api/realms", host.format(p=srv.port))
    assert status == 200


@pytest.mark.parametrize("host", ["evil.example:{p}", "evil.example", "127.0.0.1.evil.example:{p}",
                                  "localhost.evil.example", ""])
def test_a_rebound_name_is_refused_on_get(srv, host):
    status, body = _req(srv, "GET", "/api/realms", host.format(p=srv.port))
    assert status == 421
    assert b"realms" not in body          # nothing about the realm leaks


def test_a_rebound_post_with_a_matching_origin_is_refused(srv):
    """The exact shape of the attack: Origin and Host agree, and neither is ours."""
    h = f"evil.example:{srv.port}"
    status, _ = _req(srv, "POST", "/api/new-thread", h, origin=f"http://{h}",
                     body={"agent": "x", "title": "y"})
    assert status == 421


def test_same_origin_post_from_the_app_still_works(srv):
    h = f"127.0.0.1:{srv.port}"
    status, _ = _req(srv, "POST", "/api/dryrun", h, origin=f"http://{h}", body={})
    assert status in (200, 400)           # reached the route (400 is its own error path)


def test_host_parsing():
    class H(serve.Handler):
        def __init__(self, host):
            self.headers = {"Host": host} if host is not None else {}

    assert H("127.0.0.1:8756")._host_ok() and H("LOCALHOST:1")._host_ok() and H("[::1]:8756")._host_ok()
    assert not H("evil.example:8756")._host_ok()
    assert not H(None)._host_ok()
    assert not H("127.0.0.1:8756:evil")._host_ok()
