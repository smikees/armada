"""Real HTTP checks for bundled-asset confinement and user image isolation (2.11)."""
import http.client
from pathlib import Path
from urllib.parse import quote

import pytest

from armada import origins, serve
from armada.request_context import RealmContext
from tests.golden_support import ServedRealm, build_fixture


@pytest.fixture
def srv(tmp_path_factory):
    root = tmp_path_factory.mktemp("asset-boundary")
    realm = Path(build_fixture(root / "realm"))
    static = root / "static"
    (static / "js").mkdir(parents=True)
    (static / "js" / "safe.js").write_text("console.log('bundled');", encoding="utf-8")
    outside = root / "outside.txt"
    outside.write_text("outside asset directory", encoding="utf-8")
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>fetch("/api/realms")</script></svg>'
    (realm / "icon.svg").write_text(svg, encoding="utf-8")
    (realm / "user").mkdir()
    (realm / "user" / "avatar.svg").write_text(svg, encoding="utf-8")
    (realm / "agents" / "captain" / "avatar.svg").write_text(svg, encoding="utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(serve, "STATIC_ROOT", static)
        with ServedRealm(str(realm)) as server:
            server.static_root, server.outside = static, outside
            yield server


def request(server, path, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    try:
        connection.request("GET", path, headers={**server.auth_headers(), "X-Armada-Realm": RealmContext.capture(server.realm).realm_id, **(headers or {})})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_bundled_script_remains_available_even_cross_site(srv):
    status, headers, data = request(srv, "/static/js/safe.js?v=123", {"Sec-Fetch-Site": "cross-site"})
    assert status == 200 and data == b"console.log('bundled');"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "javascript" in headers["Content-Type"]
    assert "max-age" in headers["Cache-Control"]


@pytest.mark.parametrize("relative", [
    "../outside.txt", "%2e%2e/outside.txt", "js/../../outside.txt", "js/..%20/outside.txt",
    "js\\..\\..\\outside.txt", "js%5c..%5c..%5coutside.txt", "/outside.txt", "//server/share/file",
    "C:/Windows/win.ini", "C:relative.txt", "C%3a%2fWindows/win.ini", "%5c%5cserver%5cshare%5cfile",
    "js/safe.js:stream", "js/safe.js%00", "./js/safe.js", "js//safe.js", "js/safe.js.",
])
def test_ambiguous_and_escaping_paths_are_rejected(srv, relative):
    status, _, data = request(srv, "/static/" + relative, {"Sec-Fetch-Site": "cross-site"})
    assert status in (400, 404)
    assert b"outside asset directory" not in data


def test_actual_absolute_file_outside_static_cannot_be_read(srv):
    for path in (srv.outside.as_posix(), quote(str(srv.outside), safe="")):
        status, _, data = request(srv, "/static/" + path)
        assert status in (400, 404) and b"outside asset directory" not in data


def test_symlink_target_must_remain_inside_static(srv):
    link = srv.static_root / "escape.txt"
    try:
        link.symlink_to(srv.outside)
    except OSError as exc:
        pytest.skip(f"creating symbolic links is unavailable on this host: {exc}")
    try:
        assert request(srv, "/static/escape.txt")[0] == 404
    finally:
        link.unlink()


@pytest.mark.parametrize("path", ["/realm-icon", "/avatar/captain", "/user-avatar"])
def test_svg_images_are_inert_when_opened_as_documents(srv, path):
    status, headers, data = request(srv, path)
    assert status == 200 and b"<svg" in data
    assert headers["Content-Type"] == "image/svg+xml"
    assert headers["Content-Security-Policy"] == origins.IMAGE_CSP
    assert "allow-scripts" not in headers["Content-Security-Policy"]
    assert "allow-same-origin" not in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_image_policy_does_not_leak_to_the_next_response(srv):
    request(srv, "/realm-icon")
    status, headers, _ = request(srv, "/api/realm")
    assert status == 200 and "Content-Security-Policy" not in headers
