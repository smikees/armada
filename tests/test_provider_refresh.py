"""Concurrent refreshes are shared without caching mutable connection state."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from armada import providers, appconfig


def test_concurrent_force_refresh_joins_one_probe_per_provider(monkeypatch):
    entered = {p: threading.Event() for p in providers.NAMES}
    release = threading.Event()
    calls = []
    def probe(provider, force):
        calls.append((provider, force))
        entered[provider].set()
        assert release.wait(3)
        return True, {"ok": True, "logged_in": True}
    monkeypatch.setattr(providers, "_probe", probe)
    monkeypatch.setattr(providers, "_probes", {})
    with ThreadPoolExecutor(max_workers=9) as pool:
        first = pool.submit(providers.statuses, True)
        try:
            assert all(event.wait(2) for event in entered.values())
            joined = [providers._observation(p, True) for p in providers.NAMES for _ in range(3)]
            assert len({id(future) for future in joined}) == 3
            providers.disconnect("codex")
        finally:
            release.set()
        result = first.result(3)
    assert sorted(calls) == [(p, True) for p in sorted(providers.NAMES)]
    assert result["claude"]["connected"]
    assert not result["codex"]["connected"]


def test_unchanged_observation_does_not_rewrite_config(monkeypatch):
    providers._save("codex", logged_in=True)
    before = appconfig._path().read_bytes()
    monkeypatch.setattr(providers.util, "write_json_atomic", lambda *a: pytest.fail("unchanged state written"))
    providers._save("codex", logged_in=True)
    assert appconfig._path().read_bytes() == before


def test_failed_probe_can_be_retried(monkeypatch):
    monkeypatch.setattr(providers, "_probes", {})
    def broken(*args):
        raise OSError("synthetic failure")
    monkeypatch.setattr(providers, "_probe", broken)
    with pytest.raises(OSError, match="synthetic"):
        providers.status("codex")
    monkeypatch.setattr(providers, "_probe", lambda *args: (True, {"ok": True, "logged_in": True}))
    assert providers.status("codex")["connected"]
