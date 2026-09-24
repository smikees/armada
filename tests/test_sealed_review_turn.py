"""A bring-a-link review is sealed to reading the web (launch plan 5.8b, THREAT_MODEL T4).

The link is someone else's content. A reviewer that could also run commands, write files or use the
owner's connectors would take instructions planted in that content with the owner's permissions.
These check the command line the Claude engine is actually given, not just the intent.
"""
from types import SimpleNamespace

from armada.engine import claude as C


def _argv_for(monkeypatch, **run_kw):
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv
        return SimpleNamespace(returncode=0, stdout='{"result": "ok", "usage": {}}', stderr="")
    monkeypatch.setattr(C.subprocess, "run", fake_run)
    eng = C.ClaudeEngine()
    monkeypatch.setattr(eng, "_launcher", lambda: ["claude"])
    eng.run("system", "prompt", **run_kw)
    return seen["argv"]


def test_sealed_args_name_exactly_the_tools_and_nothing_that_bypasses_them():
    a = C._sealed_tool_args(["WebFetch", "WebSearch"])
    assert a[a.index("--tools") + 1] == "WebFetch,WebSearch"
    assert "--safe-mode" in a                                  # no MCP servers, skills or plugins
    assert a[a.index("--permission-prompts") + 1] == "none"    # anything else is refused, not asked
    i = a.index("--allowedTools")
    assert a[i + 1:i + 3] == ["WebFetch", "WebSearch"]
    assert "--dangerously-skip-permissions" not in a


def test_the_engine_uses_the_sealed_args_and_ignores_allow_tools(monkeypatch):
    argv = _argv_for(monkeypatch, only_tools=["WebFetch", "WebSearch"], allow_tools=True)
    assert "--dangerously-skip-permissions" not in argv
    assert argv[argv.index("--tools") + 1] == "WebFetch,WebSearch"
    assert "default" not in argv


def test_an_ordinary_tool_turn_is_unchanged(monkeypatch):
    argv = _argv_for(monkeypatch, allow_tools=True, disallowed_tools=["mcp__x"])
    assert argv[argv.index("--tools") + 1] == "default" and "--dangerously-skip-permissions" in argv


def test_the_review_asks_for_the_sealed_turn():
    from armada.catalogue import realm as R
    assert R.REVIEW_TOOLS == ("WebFetch", "WebSearch")
