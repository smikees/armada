"""Untrusted content lives on its own origin (launch plan 5.8a, THREAT_MODEL T3).

A section's mini-site, a mirrored page, an HTML attachment: HTML and JavaScript ARMADA didn't write.
Served from the app's origin, a script in it could call /api/chat-stream and start an agent turn with
the owner's permissions. These drive real servers, because the property is about origins and HTTP.
"""
import http.client
import json
from pathlib import Path

import pytest

from golden_support import ServedRealm, build_fixture
from armada import origins, serve


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    root = Path(build_fixture(tmp_path_factory.mktemp("content") / "realm"))
    site = root / "shared" / "site"
    site.mkdir(parents=True)
    (site / "index.html").write_text("<html><head></head><body><script>fetch('/api/realms')</script>hi</body></html>",
                                     encoding="utf-8")
    (site / "app.js").write_text("console.log(1)", encoding="utf-8")
    cfg = json.loads((root / "realm.json").read_text(encoding="utf-8"))
    cfg["sections"].append({"name": "Mini", "assets": str(site), "entry": "index.html"})
    (root / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    att = root / "agents" / next(p.name for p in (root / "agents").iterdir() if p.is_dir()) / "threads" / "main" / "attachments"
    att.mkdir(parents=True, exist_ok=True)
    (att / "page.html").write_text("<script>alert(1)</script>", encoding="utf-8")
    (att / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    with ServedRealm(str(root)) as s:
        s.agent = att.parts[-4]
        yield s
    origins.set_content_port(None)


def _req(port, method, path, headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Host": f"127.0.0.1:{port}", **(headers or {})}
    data = json.dumps(body).encode() if body is not None else None
    if data:
        h["Content-Type"] = "application/json"
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read().decode("utf-8", "replace")


def test_a_content_server_runs_beside_the_app(srv):
    assert origins.content_port() and origins.content_port() != srv.port


def test_the_app_sends_untrusted_pages_to_the_content_origin(srv):
    st, h, _ = _req(srv.port, "GET", "/section-raw/1")
    assert st == 302 and h["Location"] == f"http://127.0.0.1:{origins.content_port()}/section-raw/1"
    st, h, _ = _req(srv.port, "GET", f"/thread-file?agent={srv.agent}&thread=main&name=page.html")
    assert st == 302 and h["Location"].startswith(f"http://127.0.0.1:{origins.content_port()}/thread-file")


def test_images_stay_on_the_app_origin(srv):
    st, h, body = _req(srv.port, "GET", f"/thread-file?agent={srv.agent}&thread=main&name=pic.png")
    assert st == 200 and h["Content-Type"] == "image/png"


def test_the_content_server_serves_the_content(srv):
    st, _, body = _req(origins.content_port(), "GET", "/section-raw/1")
    assert st == 200 and "hi" in body and '<base href="/section-asset/1/">' in body
    st, _, body = _req(origins.content_port(), "GET", "/section-asset/1/app.js")
    assert st == 200 and "console.log" in body


def test_the_content_server_has_no_api(srv):
    cp = origins.content_port()
    for path in ("/", "/settings", "/api/realms", "/api/auth-status"):
        assert _req(cp, "GET", path)[0] == 404, path
    assert _req(cp, "POST", "/api/chat-stream", body={"agent": "x"})[0] == 403
    assert _req(cp, "POST", "/api/save-user", body={"name": "x"})[0] == 403


def test_the_app_refuses_what_the_content_origin_sends_it(srv):
    cp = origins.content_port()
    origin = {"Origin": f"http://127.0.0.1:{cp}"}
    assert _req(srv.port, "POST", "/api/save-user", headers=origin, body={"name": "x"})[0] == 403
    for sfs in ("same-site", "cross-site"):
        assert _req(srv.port, "GET", "/api/realms", headers={"Sec-Fetch-Site": sfs})[0] == 403, sfs
        assert _req(srv.port, "GET", "/switch?path=x", headers={"Sec-Fetch-Site": sfs})[0] == 403, sfs


def test_the_app_window_itself_is_not_refused(srv):
    for sfs in (None, "none", "same-origin"):
        h = {"Sec-Fetch-Site": sfs} if sfs else {}
        assert _req(srv.port, "GET", "/api/realms", headers=h)[0] == 200, sfs
    assert _req(srv.port, "GET", "/static/brand.css", headers={"Sec-Fetch-Site": "cross-site"})[0] == 200


def test_section_frames_point_at_the_content_origin_and_cannot_steer_the_window(srv):
    html = srv.get("/section/1")
    assert f'src="http://127.0.0.1:{origins.content_port()}/section-raw/1"' in html
    assert 'sandbox="' in html and "allow-top-navigation" not in html


def test_without_a_content_server_the_app_sandboxes_the_content_itself(srv, monkeypatch):
    monkeypatch.setattr(origins, "_content_port", None)
    st, h, _ = _req(srv.port, "GET", "/section-raw/1")
    assert st == 200 and h["Content-Security-Policy"].startswith("sandbox ")
    assert "allow-same-origin" not in h["Content-Security-Policy"]
    st, h, _ = _req(srv.port, "GET", "/api/realms")
    assert "Content-Security-Policy" not in h                  # only the untrusted responses


def test_active_types():
    for n in ("a.html", "A.HTM", "x.svg", "y.js", "z.xhtml"):
        assert origins.is_active(n), n
    for n in ("a.png", "b.pdf", "c.md", "d.txt", ""):
        assert not origins.is_active(n), n
