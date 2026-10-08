"""Invocation-scoped MCP tools for draft jobs and read-only inspectors.

This broker deliberately has no shell, network, generic production write, or owner HTTP action.
Provider adapters expose only this MCP server during managed turns.
"""
from __future__ import annotations

import base64
import copy
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading

from . import inspection, util, workspace

MAX_BYTES = 1024 * 1024


def _tool(name, description, properties=None, required=(), *, read_only=True):
    return {"name": name, "description": description, "inputSchema": {"type": "object",
        "properties": properties or {}, "required": list(required), "additionalProperties": False},
        "annotations": {"readOnlyHint": read_only, "destructiveHint": False, "openWorldHint": False}}


def _string(description):
    return {"type": "string", "description": description}


class ManagedTools:
    def __init__(self, root, agent, *, output=None, job=None, inspector=False):
        self.root, self.agent = Path(root).resolve(), util.safe_seg(agent, "agent")
        self.inspector, self.job = inspector, job
        self.output = Path(output or self.root / "agents" / self.agent / "artifacts").absolute()
        inspection.checked_path(self.output, [self.root])
        self.read_roots = [self.root]
        if workspace.root(root):
            self.read_roots.append(Path(workspace.root(root)).resolve())
        if job:
            from .job_access import grant_for
            self.read_roots.extend(Path(p) for p in grant_for(root, agent, job).roots)
        self.server = self.thread = self.temporary = None
        self.token = secrets.token_urlsafe(32)
        self.tests_started = 0
        self.closed = False
        self.lock = threading.RLock()

    def tools(self):
        tools = [_tool("write_draft", "Write a UTF-8 file in your draft output folder only. Relative paths are preferred.",
            {"path": _string("Path inside the draft folder"), "content": _string("Exact UTF-8 text")},
            ("path", "content"), read_only=False)]
        if self.inspector:
            tools += [_tool("list_jobs", "List every job in this realm, including disabled jobs."),
                _tool("list_models", "List currently available models for dry runs."),
                _tool("list_artifacts", "List recorded output artifacts from all agents in this realm. Read only."),
                _tool("read_artifact", "Read an artifact by its ID from list_artifacts. Never edits it.",
                      {"id": _string("Artifact ID")}, ("id",)),
                _tool("start_dry_run", "Start a draft-only test of any realm job. Never changes its model or schedule.",
                      {"agent": _string("Job owner agent ID"), "job": _string("Job ID"),
                       "model": _string("Explicit model ID from list_models; omit for command jobs")},
                      ("agent", "job"), read_only=False),
                _tool("get_dry_run", "Read dry-run state, final answer and output artifacts; poll while running.",
                      {"agent": _string("Job owner agent ID"), "job": _string("Job ID"),
                       "run_id": _string("Dry-run ID")}, ("agent", "job", "run_id")),
                _tool("read_dry_run_file", "Read a selected draft file from a dry run. Read only.",
                      {"agent": _string("Job owner agent ID"), "job": _string("Job ID"),
                       "run_id": _string("Dry-run ID"), "path": _string("Relative name from get_dry_run files")},
                      ("agent", "job", "run_id", "path"))]
        else:
            tools += [_tool("read_input", "Read an existing file from the realm/workspace or approved job inputs. Read only.",
                        {"path": _string("Absolute input file path")}, ("path",)),
                _tool("list_input_files", "List files directly inside a realm/workspace input folder. Read only.",
                      {"path": _string("Absolute folder path")}, ("path",))]
        return tools

    def _authorize(self):
        if self.closed:
            raise ValueError("This turn's managed tools have expired.")
        from . import realmops
        realmops.assert_active(self.root)
        if self.inspector and not inspection.enabled(self.root, self.agent):
            raise ValueError("Inspector access was disabled. Ask the user to enable Is inspector in Configure → Advanced.")

    def call(self, name, arguments):
        self._authorize()
        schema = next((t["inputSchema"] for t in self.tools() if t["name"] == name), None)
        if schema is None or not isinstance(arguments, dict) or set(arguments) - set(schema["properties"]):
            raise ValueError("Unknown managed tool or arguments.")
        if any(k not in arguments for k in schema["required"]) or any(not isinstance(v, str) for v in arguments.values()):
            raise ValueError("Supply the required string arguments.")
        if name == "write_draft":
            raw = Path(arguments["path"])
            path = inspection.checked_path(raw if raw.is_absolute() else self.output / raw, [self.output])
            # Control files belong to the host, not the model.
            if path.name == "final-answer.md":
                raise ValueError("final-answer.md is reserved for the final response. Choose another draft name.")
            if len(arguments["content"].encode("utf-8")) > MAX_BYTES:
                raise ValueError("A draft file must be at most 1 MiB.")
            path.parent.mkdir(parents=True, exist_ok=True)
            inspection.checked_path(path, [self.output])
            util.write_text_atomic(path, arguments["content"])
            return {"path": str(path), "bytes": path.stat().st_size}
        if name == "read_input":
            path = inspection.checked_path(arguments["path"], self.read_roots, must_exist=True)
            return self._read(path)
        if name == "list_input_files":
            path = inspection.checked_path(arguments["path"], self.read_roots, must_exist=True)
            return [{"name": p.name, "kind": "folder" if p.is_dir() else "file"}
                    for p in sorted(path.iterdir()) if not p.is_symlink() and not getattr(p, "is_junction", lambda: False)()][:500]
        if name == "list_jobs":
            jobs = []
            for jp in sorted((self.root / "agents").glob("*/jobs/*.json")):
                inspection.checked_path(jp, [self.root], must_exist=True)
                job = util.read_json_state(jp)
                jobs.append({"agent": jp.parent.parent.name, "job": jp.stem, "name": job.get("name") or jp.stem,
                    "kind": job.get("kind", "agent"), "enabled": job.get("enabled", True),
                    "model": job.get("model"), "prompt": job.get("prompt", ""),
                    "dry_run_command_configured": bool(job.get("dry_run_command"))})
            return jobs
        if name == "list_models":
            from .dry_runs import models
            return models(self.root)
        if name == "list_artifacts":
            return inspection.artifacts(self.root)
        if name == "read_artifact":
            item = next((a for a in inspection.artifacts(self.root) if a["id"] == arguments["id"]), None)
            if item is None:
                raise ValueError("No recorded artifact with this ID in this realm.")
            return self._read(Path(item["path"]))
        if name == "start_dry_run":
            from . import dry_runs
            with self.lock:
                if self.tests_started >= 4:
                    raise ValueError("Four dry runs have been started in this turn. Review them before starting more.")
                result = dry_runs.start(self.root, arguments["agent"], arguments["job"],
                    arguments.get("model", ""), requested_by=self.agent)
                self.tests_started += 1
                return result
        if name == "get_dry_run":
            from . import dry_runs
            folder = dry_runs.directory(self.root, arguments["agent"], arguments["job"], arguments["run_id"])
            info = dry_runs.read(self.root, arguments["agent"], arguments["job"], arguments["run_id"])
            files = dry_runs.output_files(folder)
            answer = next((f for f in files if f["name"] == "final-answer.md"), None)
            return {"run": info, "files": files, "final_answer": self._read(Path(answer["path"])) if answer else None}
        if name == "read_dry_run_file":
            from . import dry_runs
            dry_runs.read(self.root, arguments["agent"], arguments["job"], arguments["run_id"])
            folder = dry_runs.directory(self.root, arguments["agent"], arguments["job"], arguments["run_id"]) / "output"
            path = inspection.checked_path(folder / arguments["path"], [folder], must_exist=True)
            return self._read(path)
        raise ValueError("Unsupported tool.")

    @staticmethod
    def _read(path):
        with path.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("File exceeds 1 MiB. Review a smaller exported artifact.")
        try:
            return {"path": str(path), "content": data.decode("utf-8-sig"), "encoding": "utf-8"}
        except UnicodeDecodeError:
            return {"path": str(path), "content": base64.b64encode(data).decode(), "encoding": "base64"}

    def __enter__(self):
        self._authorize()
        broker = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Credentials and file contents are never logged.
            def do_POST(self):
                if self.path != "/tools" or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + broker.token):
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2 * MAX_BYTES:
                        raise ValueError("Request is too large or empty.")
                    request = json.loads(self.rfile.read(length))
                    broker._authorize()
                    if request["method"] == "tools/list":
                        result = {"tools": broker.tools()}
                    elif request["method"] == "tools/call":
                        params = request["params"]
                        value = broker.call(params["name"], params.get("arguments") or {})
                        result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
                    else:
                        raise ValueError("Unsupported method.")
                except Exception as exc:  # silent-ok: return MCP errors without logging private tool inputs
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
                data = json.dumps(result, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temporary = tempfile.TemporaryDirectory(prefix="armada-managed-")
        # Python's package import does not depend on the job's working directory.
        self.server_config = {"command": sys.executable, "args": [str(Path(__file__).with_name("managed_mcp.py"))],
            "env": {"ARMADA_TOOL_ENDPOINT": f"http://127.0.0.1:{self.server.server_port}/tools",
                    "ARMADA_TOOL_TOKEN": self.token, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}}
        self.config_path = Path(self.temporary.name) / "mcp.json"
        self.config_path.write_text(json.dumps({"mcpServers": {"armada_managed": self.server_config}}), encoding="utf-8")
        return self

    def configure(self, engine):
        if getattr(engine, "name", "") not in ("claude", "codex", "gemini", "mock"):
            raise ValueError("This provider does not support ARMADA managed tools.")
        configured = copy.copy(engine)
        configured.managed_tools = self
        configured.allowed_mcp_ids = frozenset()
        configured.writable_roots = ()
        configured.network_access = False
        return configured

    def __exit__(self, *args):
        self.closed = True
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
        if self.temporary:
            self.temporary.cleanup()


def claude_args(engine):
    tools = engine.managed_tools
    if not engine._direct():
        raise ValueError("Managed tools require Claude's native or Node launcher.")
    return ["--setting-sources", "", "--disable-slash-commands", "--tools", "", "--strict-mcp-config", "--mcp-config", str(tools.config_path),
        "--allowedTools", "mcp__armada_managed__*", "--permission-mode", "dontAsk",
        "--settings", json.dumps({"disableAllHooks": True, "enabledPlugins": {}})]


def codex_args(engine, *, cwd=None):
    # Disable every ambient MCP server using the existing effective-inventory check.
    args = engine._mcp_args(False, (), cwd=cwd)
    spec = engine.managed_tools.server_config
    for key, value in {"command": spec["command"], "args": spec["args"], "env_vars": list(spec["env"])}.items():
        # Inline TOML tables are required for environment maps; JSON objects are not TOML.
        value = ("{" + ", ".join(json.dumps(k) + "=" + json.dumps(v) for k, v in value.items()) + "}"
                 if isinstance(value, dict) else json.dumps(value))
        args += ["-c", "mcp_servers.armada_managed." + key + "=" + value]
    args += ["-c", "mcp_servers.armada_managed.enabled=true"]
    engine._turn_mcp_ids = ("armada_managed",)
    return args
