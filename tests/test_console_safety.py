"""Console output must never be load-bearing.

The bug: after an agent had successfully completed a delegated task, printing a 60-character rule
('─' * 60) raised UnicodeEncodeError on a cp1252 stdout. The exception escaped the run, so a task
that had genuinely succeeded was recorded as failed, the sender was told it failed, and a failure
notification fired. Diagnostics killed the work they were describing.
"""
import io
import re
from pathlib import Path

import pytest

from armada import runner


class _Cp1252Out(io.TextIOBase):
    """A stdout that behaves like a Windows console/pipe: it simply can't encode box-drawing."""
    encoding = "cp1252"

    def write(self, s):
        s.encode("cp1252")      # raises UnicodeEncodeError on '─', '·', '→'
        return len(s)


def test_the_exact_line_that_broke_it(monkeypatch):
    monkeypatch.setattr(runner.sys, "stdout", _Cp1252Out())
    runner._say("─" * 60)       # must not raise


@pytest.mark.parametrize("text", ["─" * 60, "ARMADA run · a/b · engine=claude",
                                  "run-report → x.jsonl", "plain ascii"])
def test_say_survives_any_unencodable_text(monkeypatch, text):
    monkeypatch.setattr(runner.sys, "stdout", _Cp1252Out())
    runner._say(text)


def test_say_survives_no_console(monkeypatch):
    monkeypatch.setattr(runner.sys, "stdout", None)
    runner._say("─" * 60)


def test_say_survives_a_broken_stream(monkeypatch):
    class Broken(io.TextIOBase):
        def write(self, s):
            raise ValueError("I/O operation on closed file")
    monkeypatch.setattr(runner.sys, "stdout", Broken())
    runner._say("anything")


def test_say_still_prints_on_a_normal_console(capsys):
    runner._say("hello", "world")
    assert "hello world" in capsys.readouterr().out


def test_no_bare_prints_remain_in_the_runner():
    """Every diagnostic in the runner goes through the guarded helper — a new bare print() would
    reintroduce exactly this failure."""
    src = Path(runner.__file__).read_text(encoding="utf-8")
    helper = src[src.index("def _say("):src.index("def _thread_href(")]
    rest = src.replace(helper, "")
    assert not re.search(r"^\s+print\(", rest, flags=re.M), "use _say(), not print()"


def test_cli_makes_the_console_utf8():
    """The belt to _say's braces: where a console exists, it should render the characters rather
    than merely fail to crash on them."""
    from armada import cli
    src = Path(cli.__file__).read_text(encoding="utf-8")
    assert "_utf8_console" in src and 'encoding="utf-8"' in src
    assert "_utf8_console()" in src[src.index("def main("):]


def test_utf8_console_tolerates_odd_streams(monkeypatch):
    from armada import cli

    class NoReconfigure:
        pass
    monkeypatch.setattr(cli.sys, "stdout", NoReconfigure())
    monkeypatch.setattr(cli.sys, "stderr", None)
    cli._utf8_console()          # must not raise
