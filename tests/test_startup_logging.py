"""A server or window that fails to start says why in armada.log (2026-09-24: an Update & Restart
re-exec died with no trace — under pythonw nothing sees stderr)."""
import logging

import pytest

from armada import cli, serve


def test_a_start_up_failure_is_logged_not_just_raised(monkeypatch, tmp_path, caplog):
    def boom(realm, port):
        raise OSError("port 8756 is already serving")
    monkeypatch.setattr(serve, "serve", boom)
    realm = tmp_path / "r"
    realm.mkdir()
    (realm / "realm.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with caplog.at_level(logging.ERROR, logger="armada"):
        with pytest.raises(OSError):
            cli.main(["serve", str(realm)])
    assert any("serve failed to start" in r.getMessage() and r.exc_info for r in caplog.records)


def test_restart_logs_what_it_re_executes():
    import inspect
    src = inspect.getsource(serve.Handler._restart)
    assert 'log.info("restart: re-executing' in src and "log.exception" in src
