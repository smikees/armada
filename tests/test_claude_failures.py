"""Provider refusals must reach the owner even when the CLI exits without stderr."""
import json

import pytest

from armada.engine import claude
from armada.engine.process import ProcessResult


QUOTA = "You've hit your session limit · resets 5:20pm (Europe/Madrid)"


def transport(monkeypatch, event, process):
    engine = claude.ClaudeEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(engine, "_direct", lambda: True)
    monkeypatch.setattr(engine, "_env", lambda: {})
    calls = []
    def supervise(argv, *, on_line, **kw):
        calls.append(argv)
        on_line(json.dumps(event))
        return process
    monkeypatch.setattr(claude, "supervise", supervise)
    return engine, calls


def quota_event():
    # Actual 429 responses use subtype=success with is_error=true, not error_api.
    return {"type": "result", "subtype": "success", "is_error": True,
            "terminal_reason": "api_error", "api_error_status": 429,
            "result": QUOTA, "usage": {}, "modelUsage": {}}


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("stderr", ["", "Additional provider diagnostic\n"])
def test_structured_refusal_survives_nonzero_cli_exit(monkeypatch, streaming, stderr):
    process = ProcessResult(returncode=1, stderr=stderr,
                            error=f"CLI exited with code 1: {stderr}")
    engine, _ = transport(monkeypatch, quota_event(), process)
    seen = []
    result = (engine.run_stream("", "review", on_event=seen.append) if streaming
              else engine.run("", "review"))
    expected = QUOTA + (f"\nCLI stderr: {stderr.strip()}" if stderr else "")
    assert not result.ok and result.error == expected and result.output == QUOTA
    if streaming:
        assert seen[-1] == {"kind": "error", "error": expected}


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("failure, flags", [
    ("CLI timed out after 300s", {"timed_out": True}),
    ("Cancelled by owner", {"cancelled": True}),
    ("stdout protocol failed", {}),
])
def test_host_failures_remain_authoritative(monkeypatch, streaming, failure, flags):
    engine, _ = transport(monkeypatch, quota_event(),
                          ProcessResult(returncode=1, error=failure, **flags))
    result = (engine.run_stream if streaming else engine.run)("", "review")
    assert not result.ok and result.error == failure
    for flag, value in flags.items():
        assert getattr(result, flag) == value


@pytest.mark.parametrize("streaming", [False, True])
def test_success_payload_cannot_hide_nonzero_exit(monkeypatch, streaming):
    error = "CLI exited with code 1: "
    engine, _ = transport(monkeypatch,
        {"type": "result", "subtype": "success", "result": "finished", "usage": {}},
        ProcessResult(returncode=1, error=error))
    result = (engine.run_stream if streaming else engine.run)("", "review")
    assert not result.ok and result.error == error


def test_skill_review_returns_the_quota_reason_without_expanding_tools(monkeypatch):
    from armada.catalogue import review_url
    engine, calls = transport(monkeypatch, quota_event(),
        ProcessResult(returncode=1, error="CLI exited with code 1: "))
    monkeypatch.setattr(engine, "doctor", lambda: (True, "connected"))
    result = review_url("https://github.com/example/skill", engine=engine)
    assert result == {"ok": False, "error": QUOTA}
    assert len(calls) == 1 and "--safe-mode" in calls[0]
    assert calls[0][calls[0].index("--tools") + 1] == "WebFetch,WebSearch"
    assert "--dangerously-skip-permissions" not in calls[0]
