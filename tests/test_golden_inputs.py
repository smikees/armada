"""Derived snapshot data must not depend on when/where the fixture was built."""
import socket
from pathlib import Path

from armada import clock, memory
from tests import golden_support as g


def test_fixture_pins_environment_and_clock_before_generating_context(tmp_path, monkeypatch):
    def forbidden_probe():
        raise AssertionError("fixture construction probed the developer's machine")

    monkeypatch.setattr(memory, "default_env", forbidden_probe)
    monkeypatch.setattr(memory, "probe_environment", forbidden_probe)
    copies = []
    for year in (2030, 2040):
        with clock.frozen(f"{year}-03-01T11:00:00+00:00"):
            realm = Path(g.build_fixture(tmp_path / str(year)))
            copies.append((realm / "memory" / memory.SYSTEM_MEMORY_FILE).read_text("utf-8"))
            assert clock.now().year == year, "building the fixture must restore the caller's clock"
    assert copies[0] == copies[1]
    assert "updated: 2026-09-19T20:12:00" in copies[0]
    assert "fixture-machine" in copies[0]


def test_served_fixture_closes_both_ports_and_restores_clock(tmp_path):
    from armada import origins
    realm = g.build_fixture(tmp_path / "realm")
    with clock.frozen("2040-03-01T11:00:00+00:00"):
        with g.ServedRealm(realm) as server:
            ports = (server.port, origins.content_port())
            assert server.get("/api/realm")
        assert clock.now().year == 2040
        for port in ports:
            with socket.socket() as client:
                client.settimeout(0.3)
                assert client.connect_ex(("127.0.0.1", port)) != 0
