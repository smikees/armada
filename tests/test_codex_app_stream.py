"""Codex's app-server stream must expose deltas without weakening turn isolation."""
import sys
import pytest

from armada.engine.codex import CodexEngine


def _fake_server(tmp_path, body):
    script = tmp_path / "fake_app_server.py"
    script.write_text("import json,sys,time\n" + body, encoding="utf-8")
    return script


@pytest.mark.parametrize("model", ["gpt-6-sol", "codex:default"])
def test_app_server_emits_real_deltas_and_authoritative_result(tmp_path, monkeypatch, model):
    script = _fake_server(tmp_path, '''
def reply(value): print(json.dumps(value), flush=True)
for line in sys.stdin:
    msg=json.loads(line)
    if msg.get("method")=="initialize":
        reply({"id":1,"result":{}})
    elif msg.get("method")=="thread/start":
        assert ('model_verbosity="high"' in sys.argv) == ("model" in msg["params"])
        assert msg["params"]["ephemeral"] is True
        assert msg["params"]["approvalPolicy"]=="never"
        reply({"id":2,"result":{"thread":{"id":"thr_1"},"model":"gpt-6-sol"}})
    elif msg.get("method")=="turn/start":
        assert msg["params"]["sandboxPolicy"]["type"]=="workspaceWrite"
        assert msg["params"]["sandboxPolicy"]["networkAccess"] is True
        assert msg["params"]["sandboxPolicy"]["writableRoots"]==["EXTERNAL_FOLDER"]
        assert msg["params"]["approvalPolicy"]=="never"
        reply({"id":3,"result":{"turn":{"id":"turn_1"}}})
        for text in ("Hello", " world"):
            reply({"method":"item/agentMessage/delta","params":{
                "threadId":"thr_1","turnId":"turn_1","itemId":"msg_1","delta":text}})
        reply({"method":"item/completed","params":{"threadId":"thr_1",
            "item":{"id":"msg_1","type":"agentMessage","text":"Hello world"}}})
        reply({"method":"thread/tokenUsage/updated","params":{"threadId":"thr_1",
            "tokenUsage":{"last":{"inputTokens":100,"cachedInputTokens":30,"outputTokens":12}}}})
        reply({"method":"turn/completed","params":{"threadId":"thr_1",
            "turn":{"status":"completed"}}})
''')
    engine = CodexEngine()
    engine.network_access = True
    engine.writable_roots = ["EXTERNAL_FOLDER"]
    monkeypatch.setattr(engine, "_launcher", lambda: [sys.executable, "-u", str(script)])
    monkeypatch.setattr(engine, "_mcp_args", lambda *a, **kw: [])
    seen = []
    result = engine.run_stream("system", "prompt", model=model, verbosity="full",
                               cwd=str(tmp_path), allow_tools=True,
                               on_event=seen.append, timeout=10)
    assert result.ok, result.error
    assert result.output == "Hello world"
    assert result.model == "gpt-6-sol"
    assert [e["text"] for e in seen if e["kind"] == "text"] == ["Hello", " world"]
    assert result.usage.input == 70 and result.usage.cache_read == 30


def test_app_server_cancellation_stops_the_turn(tmp_path, monkeypatch):
    script = _fake_server(tmp_path, '''
def reply(value): print(json.dumps(value), flush=True)
for line in sys.stdin:
    msg=json.loads(line)
    if msg.get("method")=="initialize": reply({"id":1,"result":{}})
    elif msg.get("method")=="thread/start":
        reply({"id":2,"result":{"thread":{"id":"thr_1"}}})
    elif msg.get("method")=="turn/start":
        reply({"id":3,"result":{"turn":{"id":"turn_1"}}})
        reply({"method":"item/agentMessage/delta","params":{
            "threadId":"thr_1","turnId":"turn_1","itemId":"msg_1","delta":"Partial"}})
        time.sleep(60)
''')
    engine = CodexEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: [sys.executable, "-u", str(script)])
    monkeypatch.setattr(engine, "_mcp_args", lambda *a, **kw: [])
    handles = []
    def on_event(event):
        if event["kind"] == "text":
            handles[0].kill()
    result = engine.run_stream("system", "prompt", cwd=str(tmp_path), allow_tools=True,
                               on_event=on_event, on_proc=handles.append, timeout=10)
    assert not result.ok and result.cancelled
    assert "Partial" in result.output


def test_app_stream_does_not_repeat_completed_message():
    from armada.engine.codex import _AppStream
    seen = []
    state = _AppStream(seen.append)
    state.accept({"method": "item/agentMessage/delta", "params": {"itemId": "1", "delta": "Hi"}})
    state.accept({"method": "item/completed", "params": {
        "item": {"id": "1", "type": "agentMessage", "text": "Hi"}}})
    assert [x["text"] for x in seen if x["kind"] == "text"] == ["Hi"]
    assert state.output == "Hi"
