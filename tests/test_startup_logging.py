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


# --- the restart race (found 2026-09-24, cause of the v0.99.51 restart that never came back) -------

class _Boom:
    def serve_forever(self):
        raise OSError(10038, "An operation was attempted on something that is not a socket")


def test_a_closed_socket_during_a_restart_is_not_a_crash(monkeypatch):
    import threading
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)
    serve.RESTARTING.set()
    try:
        # the re-exec "fails" partway: the restart thread clears the flag, and the wait ends
        t = threading.Timer(0.05, serve.RESTARTING.clear)
        t.start()
        serve._serve_until_done(_Boom())          # must not raise, must not return early with the
        t.join()                                  # process still wanted by the restart thread
    finally:
        serve.RESTARTING.clear()


def test_a_closed_socket_otherwise_is_still_an_error():
    import pytest as _pytest
    serve.RESTARTING.clear()
    with _pytest.raises(OSError):
        serve._serve_until_done(_Boom())


def test_restart_raises_the_flag_before_it_closes_the_socket():
    import inspect
    src = inspect.getsource(serve.Handler._restart)
    assert src.index("RESTARTING.set()") < src.index("self.server.socket.close()")
