"""The Claude engine loads the full harness (MCP/skills/plugins) on tool turns and only adds
--safe-mode on no-tool turns — so agents can actually use their capabilities from the app.
"""
from armada.engine import claude as C


class _R:
    returncode = 0
    stdout = '{"result":"ok","usage":{},"model":"m"}'
    stderr = ""


def _argv_for(monkeypatch, allow_tools, system_override=None, **kw):
    eng = C.ClaudeEngine()
    monkeypatch.setattr(eng, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(eng, "_direct", lambda: True)
    cap = {}
    monkeypatch.setattr(C.subprocess, "run", lambda argv, **k: (cap.__setitem__("argv", argv) or _R()))
    eng.run(system=("s" if system_override is None else system_override),
            prompt="p", allow_tools=allow_tools, **kw)
    return cap["argv"]


def test_tool_turn_has_no_safe_mode(monkeypatch):
    argv = _argv_for(monkeypatch, True)
    assert "--safe-mode" not in argv
    assert "--tools" in argv and "default" in argv


def test_no_tool_turn_keeps_safe_mode(monkeypatch):
    argv = _argv_for(monkeypatch, False)
    assert "--safe-mode" in argv


def test_fallback_model_reaches_cli(monkeypatch):
    argv = _argv_for(monkeypatch, False, fallback_model="claude-opus-4-8")
    assert argv[argv.index("--fallback-model") + 1] == "claude-opus-4-8"


def test_max_budget_reaches_cli(monkeypatch):
    argv = _argv_for(monkeypatch, False, max_budget_usd=2.5)
    assert argv[argv.index("--max-budget-usd") + 1] == "2.5"


def test_advanced_flags_absent_by_default(monkeypatch):
    argv = _argv_for(monkeypatch, False)
    assert "--fallback-model" not in argv and "--max-budget-usd" not in argv


def test_zero_or_blank_advanced_are_noops(monkeypatch):
    argv = _argv_for(monkeypatch, False, fallback_model="", max_budget_usd=0)
    assert "--fallback-model" not in argv and "--max-budget-usd" not in argv


def test_disallowed_tools_blocked_on_tool_turn(monkeypatch):
    argv = _argv_for(monkeypatch, True, disallowed_tools=["mcp__brightdata", "mcp__nimble"])
    i = argv.index("--disallowedTools")
    assert argv[i + 1] == "mcp__brightdata" and argv[i + 2] == "mcp__nimble"


# ---------------------------------------------------------------- a big context off the argv
# Windows caps a command line at 32,767 characters. A real minister's assembled context runs
# 21K–34K, and the first one over the line failed every single turn with "[WinError 206] The
# filename or extension is too long" — a message that names neither the flag nor the cause.

import os


def test_a_short_system_prompt_still_travels_on_argv():
    args, path = C._system_args("you are brief")
    assert args == ["--system-prompt", "you are brief"]
    assert path == "", "a short prompt should not touch the disk"


def test_a_long_system_prompt_travels_by_file():
    big = "x" * (C._SYSTEM_ARGV_MAX + 1)
    args, path = C._system_args(big)
    try:
        assert args[0] == "--system-prompt-file" and args[1] == path
        assert open(path, encoding="utf-8").read() == big, "the file is not the prompt"
    finally:
        C._drop_system_file(path)
    assert not os.path.exists(path)


def test_the_threshold_leaves_room_under_the_windows_limit():
    """32,767 is the whole command line, not just this one argument."""
    assert C._SYSTEM_ARGV_MAX <= 32767 - 8000


def test_an_empty_system_prompt_contributes_nothing():
    assert C._system_args("") == ([], "")


def test_a_real_sized_context_does_not_reach_the_command_line(monkeypatch):
    big = "y" * 34494                      # Warren's actual assembled context, to the character
    argv = _argv_for(monkeypatch, True, system_override=big)
    assert big not in argv, "the context is still on the command line"
    assert "--system-prompt-file" in argv
    assert sum(len(a) for a in argv) < 32767, "command line still over the Windows limit"


def test_the_file_is_cleaned_up_after_the_run(monkeypatch):
    seen = {}
    eng = C.ClaudeEngine()
    monkeypatch.setattr(eng, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(eng, "_direct", lambda: True)

    def _run(argv, **k):
        i = argv.index("--system-prompt-file")
        seen["path"] = argv[i + 1]
        seen["existed"] = os.path.exists(seen["path"])
        return _R()
    monkeypatch.setattr(C.subprocess, "run", _run)
    eng.run(system="z" * (C._SYSTEM_ARGV_MAX + 1), prompt="p")
    assert seen["existed"], "the file was not there when the CLI ran"
    assert not os.path.exists(seen["path"]), "a system-prompt file was left behind"


def test_a_failed_write_falls_back_to_argv(monkeypatch):
    """Losing the turn would be worse than a long command line."""
    monkeypatch.setattr(C.tempfile, "mkstemp", lambda **k: (_ for _ in ()).throw(OSError("full")))
    args, path = C._system_args("q" * (C._SYSTEM_ARGV_MAX + 1))
    assert args[0] == "--system-prompt" and path == ""

