"""Update & Restart must relaunch in the same mode it was started in (window stays a window)."""
import socket
import sys
import threading
import urllib.error
import urllib.request

import pytest

from armada import app, serve


def _argv(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    return serve._launch_mode()


def test_app_launch_restarts_as_app(monkeypatch):
    assert _argv(monkeypatch, ["__main__.py", "app", r"D:\Work\Hand-realm"]) == "app"


def test_serve_launch_restarts_as_serve(monkeypatch):
    assert _argv(monkeypatch, ["__main__.py", "serve", r"D:\Work\Hand-realm", "--port", "8756"]) == "serve"


def test_app_with_port_flag(monkeypatch):
    assert _argv(monkeypatch, ["__main__.py", "app", "realm", "--port", "8756"]) == "app"


def test_say_survives_no_console(monkeypatch):
    """pythonw has no stdout (sys.stdout is None). Note builtin print() is already a no-op in that
    case — _say earns its keep on the broken/limited-encoding stream below, not here."""
    monkeypatch.setattr(sys, "stdout", None)
    serve._say("banner text")   # must not raise


def test_server_keeps_address_reuse_so_restart_can_rebind():
    """Update & Restart re-execs and must rebind a port still in TIME_WAIT — so address reuse
    stays ON. Duplicate instances are blocked by the pre-bind port_owner() check instead; turning
    reuse off to stop duplicates breaks restart, which is a worse bug than the one it fixes."""
    assert bool(serve._Server.allow_reuse_address) is True


def test_serve_refuses_to_start_over_a_live_server(monkeypatch):
    """A second instance must fail loudly rather than bind alongside the first and answer nothing."""
    monkeypatch.setattr(serve, "port_owner", lambda p=8756: True)
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)      # don't really wait out the grace
    with pytest.raises(OSError, match="already"):
        serve.serve("D:\\nope", 8756)


def test_serve_waits_out_a_restart_handover(monkeypatch, tmp_path):
    """During Update & Restart the outgoing process may still hold the port for a moment. That's a
    handover, not a duplicate — serve() must wait rather than refuse (the bug that broke restart)."""
    from armada import local_auth
    monkeypatch.setattr(local_auth.util, "data_dir", lambda: tmp_path / "data")
    calls = {"n": 0}

    def owner(p=8756):
        calls["n"] += 1
        return calls["n"] < 3          # busy twice, then free

    monkeypatch.setattr(serve, "port_owner", owner)
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)
    # gets past the port guard, then fails later on the bogus realm — proving it did NOT refuse
    with pytest.raises(SystemExit):
        serve.serve("D:\\nope", 8756)
    assert calls["n"] >= 3


def test_port_owner_detects_a_free_port():
    # nothing is listening on this high port, so it must report False (and never raise)
    assert serve.port_owner(59_413) is False


def test_instance_probe_identifies_realm_without_rendering_dashboard(tmp_path, monkeypatch):
    monkeypatch.setattr(serve.Handler, "realm", str(tmp_path))
    monkeypatch.setattr(serve.Handler, "_route_get", lambda self: (_ for _ in ()).throw(RuntimeError("broken dashboard")))
    from armada import local_auth
    monkeypatch.setattr(local_auth.util, "data_dir", lambda: tmp_path / "data")
    server = serve._Server(("127.0.0.1", 0), serve.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(url, headers=local_auth.headers(server.server_port)), timeout=2)
        assert error.value.code == 500
        assert app._server_matches(url, str(tmp_path))
        assert not app._server_matches(url, str(tmp_path / "other"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_occupied_default_port_selects_another_pair():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        if port > 65330:
            pytest.skip("OS assigned a port too close to the end of the range")
        chosen = app._free_port_pair(port)
        assert chosen != port and chosen >= port + 2


def test_say_survives_broken_stream(monkeypatch):
    class Broken:
        def write(self, *a):
            raise ValueError("I/O operation on closed file")

        def flush(self, *a):
            raise ValueError("closed")

    monkeypatch.setattr(sys, "stdout", Broken())
    serve._say("banner text")   # must not raise


def test_say_writes_when_console_exists(capsys):
    serve._say("hello console")
    assert "hello console" in capsys.readouterr().out


def test_unknown_argv_defaults_to_serve(monkeypatch):
    # a realm path literally named 'app' must not be mistaken for the subcommand: the subcommand
    # comes first, so the first recognised token wins and a bare/odd argv falls back to headless.
    assert _argv(monkeypatch, ["__main__.py"]) == "serve"
    assert _argv(monkeypatch, ["__main__.py", "doctor", "realm"]) == "serve"
