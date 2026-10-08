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
    def __init__(self, root, agent, *, output=None, job=None, inspector=False, snapshot=None,
                 script_grant=None, cancelled=None):
        self.root, self.agent = Path(root).resolve(), util.safe_seg(agent, "agent")
        self.inspector, self.job = inspector, job
        self.snapshot, self.script_grant = snapshot, script_grant
        self.cancelled = cancelled or (lambda: False)
        self.script_calls = 0
        self.script_lock = threading.Lock()
        self.script_process = None
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
                       "model": _string("Explicit model ID from list_models; omit for command jobs"),
                       "effort": _string("Optional effort override: auto, low, medium, high, xhigh, max")},
                      ("agent", "job"), read_only=False),
                _tool("get_dry_run", "Read dry-run state, final answer and output artifacts; poll while running.",
                      {"agent": _string("Job owner agent ID"), "job": _string("Job ID"),
                       "run_id": _string("Dry-run ID")}, ("agent", "job", "run_id")),
                _tool("read_dry_run_file", "Read a selected draft file from a dry run. Read only.",
                      {"agent": _string("Job owner agent ID"), "job": _string("Job ID"),
                       "run_id": _string("Dry-run ID"), "path": _string("Relative name from get_dry_run files")},
                      ("agent", "job", "run_id", "path"))]
            tools += [_tool('start_dry_run_pair', 'Run two models against one frozen copy of a job’s file inputs. A/B identity stays hidden until scores are committed.',
                {'agent': _string('Job owner agent ID'), 'job': _string('Job ID'),
                 'model_a': _string('Available model ID'), 'model_b': _string('Available model ID'),
                 'effort_a': _string('Optional effort override'), 'effort_b': _string('Optional effort override')},
                ('agent', 'job', 'model_a', 'model_b'), read_only=False),
                _tool('get_dry_run_pair', 'Read anonymous A/B status and outputs. Model mapping appears only after scores are committed.',
                    {'pair_id': _string('Pair ID')}, ('pair_id',)),
                _tool('read_pair_file', 'Read a finished anonymous A/B artifact.',
                    {'pair_id': _string('Pair ID'), 'label': _string('A or B'), 'path': _string('Relative artifact name')},
                    ('pair_id', 'label', 'path')),
                _tool('record_scores', 'Commit immutable scores from 0 to 100 for both finished candidates; reveals their model mapping.',
                    {'pair_id': _string('Pair ID'), 'score_a': {'type': 'number'}, 'score_b': {'type': 'number'},
                     'notes': _string('Rubric and review notes')}, ('pair_id', 'score_a', 'score_b'), read_only=False),
                _tool('export_dry_run_pair', 'Export a finished anonymised A/B ZIP to your own review artifacts for another agent to score blind.',
                    {'pair_id': _string('Pair ID')}, ('pair_id',), read_only=False)]
        else:
            tools += [_tool("read_input", "Read an existing file from the realm/workspace or approved job inputs. Read only.",
                        {"path": _string("Absolute input file path")}, ("path",)),
                _tool("list_input_files", "List files directly inside a realm/workspace input folder. Read only.",
                      {"path": _string("Absolute folder path")}, ("path",))]
            if self.script_grant:
                tools += [_tool("run_skill", "Execute an owner-approved Python or Node.js skill script in draft isolation. No shell, network or production writes.",
                    {"script": {"type": "string", "enum": self.script_grant['scripts']},
                     "arguments": {"type": "array", "items": {"type": "string"}, "maxItems": 32}},
                    ("script",), read_only=False)]
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
        if any(k not in arguments for k in schema["required"]):
            raise ValueError("Supply the required arguments.")
        for key, value in arguments.items():
            kind = schema['properties'][key]['type']
            if (kind == 'string' and not isinstance(value, str)) or (kind == 'array' and
                    (not isinstance(value, list) or any(not isinstance(v, str) for v in value))) or (
                    kind == 'number' and (type(value) not in (int, float) or not 0 <= value <= 100)):
                raise ValueError('Arguments do not match the managed tool schema.')
        if name == 'run_skill':
            from .draft_skills import execute
            with self.script_lock:
                self._authorize()
                return execute(self, arguments['script'], arguments.get('arguments', []))
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
            from . import draft_inputs
            path = draft_inputs.map_path(self.snapshot, arguments['path']) if self.snapshot else inspection.checked_path(arguments["path"], self.read_roots, must_exist=True)
            if not self.snapshot and not draft_inputs.permitted(path):
                raise ValueError('Host control and credential files are not draft inputs.')
            return self._read(path)
        if name == "list_input_files":
            from . import draft_inputs
            path = draft_inputs.map_path(self.snapshot, arguments['path']) if self.snapshot else inspection.checked_path(arguments["path"], self.read_roots, must_exist=True)
            if not self.snapshot and not draft_inputs.permitted(path):
                raise ValueError('Host control and credential folders are not draft inputs.')
            return [{"name": p.name, "kind": "folder" if p.is_dir() else "file"}
                    for p in sorted(path.iterdir()) if not p.is_symlink() and not getattr(p, "is_junction", lambda: False)()][:500]
        if name == "list_jobs":
            from . import runner
            from .engine.selection import engine_for
            jobs = []
            for jp in sorted((self.root / "agents").glob("*/jobs/*.json")):
                inspection.checked_path(jp, [self.root], must_exist=True)
                job = util.read_json_state(jp)
                agent_id = jp.parent.parent.name
                agent = util.read_json_state(inspection.checked_path(jp.parent.parent / "agent.json", [self.root], must_exist=True))
                default_model = runner._resolve_model(self.root, agent)
                effective_model = runner._cli_model(job["model"], self.root) if job.get("model") else default_model
                effective_effort = runner._resolve_effort(self.root, {**agent, **({"effort": job["effort"]} if job.get("effort") else {})})
                jobs.append({"agent": jp.parent.parent.name, "job": jp.stem, "name": job.get("name") or jp.stem,
                    "kind": job.get("kind", "agent"), "enabled": job.get("enabled", True),
                    "model": effective_model or engine_for(self.root, agent, job) + ":default",
                    "provider": engine_for(self.root, agent, job), "effort": effective_effort or "auto",
                    "agent_default_model": default_model or engine_for(self.root, agent) + ":default",
                    "agent_default_effort": runner._resolve_effort(self.root, agent) or "auto",
                    "configured_model": job.get("model"), "configured_effort": job.get("effort"),
                    "schedule": job.get("cron") or job.get("schedule") or "manual", "inspector": job.get("inspector") is True,
                    "prompt": job.get("prompt", ""),
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
            from .draft_inputs import permitted
            if not permitted(item['path']):
                raise ValueError('Host control files are not recorded artifacts.')
            return self._read(Path(item["path"]))
        if name == "start_dry_run":
            from . import dry_runs
            with self.lock:
                if self.tests_started >= 4:
                    raise ValueError("Four dry runs have been started in this turn. Review them before starting more.")
                result = dry_runs.start(self.root, arguments["agent"], arguments["job"],
                    arguments.get("model", ""), requested_by=self.agent, effort=arguments.get("effort"))
                self.tests_started += 1
                return result
        if name == 'start_dry_run_pair':
            from . import dry_run_pairs
            with self.lock:
                if self.tests_started > 2:
                    raise ValueError('This pair would exceed four dry runs in this turn.')
                result = dry_run_pairs.start(self.root, arguments['agent'], arguments['job'], arguments['model_a'],
                    arguments['model_b'], requested_by=self.agent, effort_a=arguments.get('effort_a'), effort_b=arguments.get('effort_b'))
                self.tests_started += 2
                return result
        if name in ('get_dry_run_pair', 'record_scores', 'export_dry_run_pair', 'read_pair_file'):
            from . import dry_run_pairs
            if name == 'get_dry_run_pair':
                return dry_run_pairs.read(self.root, arguments['pair_id'])
            if name == 'record_scores':
                return dry_run_pairs.record_scores(self.root, arguments['pair_id'], arguments['score_a'], arguments['score_b'], arguments.get('notes', ''))
            if name == 'export_dry_run_pair':
                return dry_run_pairs.export(self.root, arguments['pair_id'], self.output)
            return self._read(dry_run_pairs.read_file(self.root, arguments['pair_id'], arguments['label'], arguments['path']))
        if name == "get_dry_run":
            from . import dry_runs, dry_run_pairs
            if dry_run_pairs.paired_run(self.root, arguments['run_id']):
                raise ValueError('Use get_dry_run_pair for a paired candidate. Its identity and diagnostics are private.')
            folder = dry_runs.directory(self.root, arguments["agent"], arguments["job"], arguments["run_id"])
            info = dry_runs.read(self.root, arguments["agent"], arguments["job"], arguments["run_id"])
            files = dry_runs.output_files(folder)
            answer = next((f for f in files if f["name"] == "final-answer.md"), None)
            return {"run": info, "files": files, "final_answer": self._read(Path(answer["path"])) if answer else None}
        if name == "read_dry_run_file":
            from . import dry_runs, dry_run_pairs
            if dry_run_pairs.paired_run(self.root, arguments['run_id']):
                raise ValueError('Use read_pair_file for anonymous paired artifacts.')
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
        if self.script_process and self.script_process.poll() is None:
            self.script_process.kill()
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
    args += ["-c", "mcp_servers.armada_managed.enabled=true", "-c", "mcp_servers.armada_managed.tool_timeout_sec=180"]
    engine._turn_mcp_ids = ("armada_managed",)
    return args
