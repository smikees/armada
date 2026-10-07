"""Opt-in real CLI verification with a local synthetic MCP server; never used by pytest."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from armada import tool_capture, util
from armada.engine import claude, codex, gemini
from armada.engine.process import supervise as stream_process, supervise_rpc as rpc_process


def verify(provider, output):
    """Exercise the installed CLI, capture writes, and a later same-run file read."""
    folder = output / (provider + "-" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    workspace = folder / "workspace"
    workspace.mkdir()
    util.write_json_atomic(folder / "realm.json", {"name": "Synthetic capture verification", "workspace": str(workspace)})
    sid = "capture_Interactive_Brokers_fixture"
    server = str(ROOT / "tools/capture_fixture_server.py")
    job = {"capture_tools": ["mcp__*Interactive_Brokers*__get_*"], "capture_dir": "raw/{run}", "require_capture": True}
    cap = tool_capture.ToolCapture(folder, job, "read-check", uuid.uuid4().hex, provider, True, "fixture")
    assert cap.directory, cap.errors
    transcript = folder / "cli.jsonl"
    prompt = ("Use MCP server " + sid + ". Call get_positions, get_balances and get_cash once each with empty arguments. "
              "Do not use any other connector. These tools return only synthetic data. ")
    script = workspace / "verify_capture.py"
    script.write_text("import os,json,pathlib,hashlib,time\n"
        "p=pathlib.Path(os.environ['ARMADA_RAW_DIR'])\n"
        "for _ in range(100):\n"
        " try:\n"
        "  rows=list(map(json.loads,(p/'manifest.jsonl').read_text(encoding='utf-8').splitlines()))\n"
        "  if len(rows)==3: break\n"
        " except FileNotFoundError: pass\n"
        " time.sleep(.1)\n"
        "assert len(rows)==3\n"
        "for r in rows: assert hashlib.sha256((p/r['file']).read_bytes()).hexdigest()==r['sha256']\n"
        "(p/'same-run-ok.txt').write_text('3 matching hashes')\n"
        "print('3 matching hashes')\n", encoding="utf-8")
    if provider.startswith("codex"):
        prompt += ("After those three calls, call the same server's verify_capture tool once with empty arguments. "
                   "It runs the local hash-check script. Do not run a native shell. Then reply done.")
    elif provider == "claude":
        prompt += ("After those calls, run this exact Python script using your shell tool: "
                   + json.dumps(sys.executable) + " " + json.dumps(str(script)) + ". Then reply done.")
    else:
        prompt += ("After those calls, use your native file tool to read " + str(cap.directory / "manifest.jsonl")
                   + ". Verify it has three entries. Then reply done.")
    originals = {}
    module = claude if provider == "claude" else gemini if provider == "gemini" else codex

    def supervise(args, **kwargs):
        callback = kwargs["on_line"]
        def line(raw):
            with transcript.open("a", encoding="utf-8", newline="") as handle:
                handle.write(raw.rstrip("\r\n") + "\n")
            callback(raw)
        return stream_process(args, **{**kwargs, "on_line": line})

    def rpc(args, **kwargs):
        callback = kwargs["on_message"]
        def message(event, send):
            with transcript.open("a", encoding="utf-8", newline="") as handle:
                handle.write(event.source.rstrip("\r\n") + "\n")
            return callback(event, send)
        return rpc_process(args, **{**kwargs, "on_message": message})

    if provider == "claude":
        engine = claude.ClaudeEngine()
        config = folder / "mcp.json"
        config.write_text(json.dumps({"mcpServers": {sid: {"command":sys.executable,"args":[server]}}}), encoding="utf-8")
        engine._mcp_args = lambda *a: ["--strict-mcp-config","--mcp-config",str(config),
                                      "--setting-sources","","--no-session-persistence"]
    elif provider.startswith("codex"):
        engine = codex.CodexEngine()
        original_args = engine._mcp_args
        def mcp_args(*a, **kw):
            args = original_args(*a, **kw)
            engine._turn_mcp_ids = (sid,)
            return args + ["-c",f"mcp_servers.{sid}.command="+json.dumps(sys.executable),
                "-c",f"mcp_servers.{sid}.args="+json.dumps([server]),
                "-c",f"mcp_servers.{sid}.env_vars="+json.dumps(["ARMADA_RAW_DIR","ARMADA_CAPTURE_PROBE_SCRIPT"])]
        engine._mcp_args = mcp_args
        engine.app_server_streaming = provider == "codex-app"
        engine.writable_roots = (str(workspace),)
    else:
        engine = gemini.GeminiEngine()
        engine._connectors = lambda *a: [{"name":sid,"command":sys.executable,"args":[server]}]
        engine.writable_roots = (str(workspace),)

    for name, fn in (("supervise", supervise), ("supervise_rpc", rpc)):
        if hasattr(module, name):
            originals[name] = getattr(module, name)
            setattr(module, name, fn)
    try:
        result = engine.run_stream("Perform only the synthetic verification requested.", prompt,
            cwd=str(workspace), allow_tools=True, timeout=180, on_event=cap.on_event,
            env={"ARMADA_RAW_DIR": str(cap.directory), "ARMADA_CAPTURE_PROBE_SCRIPT": str(script)})
    finally:
        for name, fn in originals.items():
            setattr(module, name, fn)
        cap.finish()
    info = cap.report()
    assert result.ok, result.error
    assert info["count"] == 3 and info["status"] == "complete", info
    for record in cap.records:
        data = (cap.directory / record["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["sha256"]
        assert data == record["payload"].encode("utf-8")
    if provider != "gemini":
        assert (cap.directory / "same-run-ok.txt").read_text() == "3 matching hashes"
    info.update(engine=provider, same_run_read=("MCP fixture subprocess" if provider.startswith("codex")
        else "native shell script" if provider == "claude" else "native file tool"))
    (folder / "verification.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info))
    return folder


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["claude","codex-app","codex-exec","gemini"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.engine, args.output.resolve())
