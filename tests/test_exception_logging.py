"""No silent broad excepts (Phase 2, 2.5).

ARMADA catches `Exception` in ~280 places on purpose — a badge must not break a page, telemetry must
not fail a job — and until 2.5, ~270 of those threw the reason away. Each now logs before it falls
back: `util.swallowed(log, ...)` for the ordinary case, `log.debug(..., exc_info=True)` where the
failure is the expected path (a probe, a per-event write to a client that has gone, a date that
doesn't parse), and an explicit `# silent-ok: <reason>` comment for the one or two places where
logging is itself what failed.

The scan below is what stops the count creeping back up: a new broad except that neither logs, nor
re-raises, nor says why it's silent, fails the suite.
"""
import ast
import logging
import pathlib

import pytest

from armada import util

ROOT = pathlib.Path(__file__).resolve().parents[1] / "armada"
_LOG_ATTRS = {"exception", "error", "warning", "info", "debug", "critical", "log"}


def _broad(h: ast.ExceptHandler) -> bool:
    t = h.type
    if t is None:
        return True
    names = [t.id] if isinstance(t, ast.Name) else \
        [getattr(e, "id", "") for e in t.elts] if isinstance(t, ast.Tuple) else []
    return bool({"Exception", "BaseException"} & set(names))


def _accounted_for(h: ast.ExceptHandler, line: str) -> bool:
    if "silent-ok:" in line:
        return True
    for n in (x for b in h.body for x in ast.walk(b)):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in _LOG_ATTRS:
                return True
            if isinstance(f, ast.Name) and f.id == "swallowed":
                return True
    return False


def test_every_broad_except_logs_reraises_or_says_why_not():
    offenders = []
    for f in sorted(ROOT.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        lines = src.splitlines()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.ExceptHandler) and _broad(n) and not _accounted_for(n, lines[n.lineno - 1]):
                offenders.append(f"{f.relative_to(ROOT.parent)}:{n.lineno}")
    assert not offenders, ("broad except that swallows silently — call util.swallowed(log, ...) before "
                           "the fallback, or mark the line '# silent-ok: <reason>':\n  " + "\n  ".join(offenders))


# ---- util.swallowed -------------------------------------------------------------------------------

@pytest.fixture
def fresh(monkeypatch):
    monkeypatch.setattr(util, "_swallow_last", {})
    monkeypatch.setattr(util, "_swallow_hidden", {})
    return logging.getLogger("armada.test.swallowed")


def test_logs_the_exception_being_handled_with_its_traceback(fresh, caplog):
    caplog.set_level(logging.DEBUG, logger="armada")
    try:
        raise ValueError("bad json")
    except Exception:
        util.swallowed(fresh, "f: failed; using a default")
    [rec] = caplog.records
    assert rec.levelno == logging.ERROR and rec.getMessage() == "f: failed; using a default"
    assert rec.exc_info and rec.exc_info[0] is ValueError


def test_a_missing_file_is_the_absent_case_not_an_error(fresh, caplog):
    caplog.set_level(logging.DEBUG, logger="armada")
    try:
        raise FileNotFoundError("no feed yet")
    except Exception:
        util.swallowed(fresh, "feed: failed")
    [rec] = caplog.records
    assert rec.levelno == logging.DEBUG and rec.exc_info


def test_repeats_are_held_back_and_counted_on_the_next_one_through(fresh, caplog, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(util.time, "monotonic", lambda: clock["t"])
    caplog.set_level(logging.INFO, logger="armada")

    def fail():
        try:
            raise KeyError("x")
        except Exception:
            util.swallowed(fresh, "render: failed; showing 0")

    for _ in range(5):
        fail()
    assert len(caplog.records) == 1                       # a render-path failure can't flood the log
    clock["t"] += util.SWALLOW_WINDOW + 1
    fail()
    assert len(caplog.records) == 2
    assert "+4 more like this" in caplog.records[1].getMessage()


def test_different_messages_are_not_held_back_by_each_other(fresh, caplog):
    caplog.set_level(logging.INFO, logger="armada")
    for what in ("a: failed", "b: failed"):
        try:
            raise RuntimeError(what)
        except Exception:
            util.swallowed(fresh, what)
    assert [r.getMessage() for r in caplog.records] == ["a: failed", "b: failed"]


def test_outside_an_except_block_it_does_nothing(fresh, caplog):
    caplog.set_level(logging.DEBUG, logger="armada")
    util.swallowed(fresh, "nothing to report")
    assert caplog.records == []


def test_it_never_raises_even_with_a_broken_logger(fresh):
    class Broken:
        name = "broken"

        def log(self, *a, **k):
            raise OSError("disk full")

        debug = log

    try:
        raise ValueError("x")
    except Exception:
        util.swallowed(Broken(), "whatever")      # must not raise


def test_a_swallowed_route_error_reaches_the_log(tmp_path, caplog):
    """End to end through a real call site: a delete of a file that can't be removed returns the
    same error dict as before AND leaves a traceback behind."""
    from armada import serve

    class H(serve.Handler):
        def __init__(self, realm):
            self.realm = str(realm)

    caplog.set_level(logging.INFO, logger="armada")
    util._swallow_last.clear()
    out = H(tmp_path)._delete_goal({"stem": "../../etc"})
    assert out["ok"] is False and out["error"]
    assert any(r.exc_info for r in caplog.records if r.name.startswith("armada"))


def test_init_logging_writes_under_home_once(tmp_path, monkeypatch):
    monkeypatch.setattr(util.Path, "home", classmethod(lambda cls: tmp_path))
    root = logging.getLogger("armada")
    saved = (list(root.handlers), getattr(root, "_armada_configured", False), root.level)
    try:
        root.handlers = []
        root._armada_configured = False
        util.init_logging("scheduler.log")
        util.init_logging("scheduler.log")
        files = [h for h in root.handlers if hasattr(h, "baseFilename")]
        assert len(files) == 1 and files[0].baseFilename.endswith("scheduler.log")
        assert (tmp_path / ".armada" / "logs" / "scheduler.log").exists()
    finally:
        for h in root.handlers:
            if h not in saved[0]:
                h.close()
        root.handlers, root._armada_configured, root.level = saved[0], saved[1], saved[2]
