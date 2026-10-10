"""Codex CLI turns, using the owner's login and Armada's existing context and history.

One fresh exec per turn avoids keeping a second, divergent conversation in Codex. JSONL events
are translated to Armada's existing stream contract. No credential file is read or copied.
"""
from __future__ import annotations
from ..background import process_options

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .base import EngineAdapter, RunResult, Usage
from .process import supervise, supervise_rpc, safe_emit

log = logging.getLogger(__name__)
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_DISABLED_FEATURES = ("apps", "plugins", "hooks", "multi_agent", "browser_use", "computer_use")


def _feature_args():
    return [arg for feature in _DISABLED_FEATURES for arg in ("-c", f"features.{feature}=false")] + [
        "-c", "features.mcp_oauth_refresh_coordination=true"]


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def cached_models() -> list[dict]:
    """Read only the CLI's public model metadata; never fetch during a page render."""
    try:
        data = json.loads((codex_home() / "models_cache.json").read_text(encoding="utf-8"))
        return [m for m in data.get("models", [])
                if isinstance(m, dict) and m.get("slug") and m.get("visibility", "list") == "list"]
    except (OSError, ValueError, AttributeError):
        log.debug("Codex model cache unavailable", exc_info=True)
        return []


def model_id(value: str) -> str:
    value = str(value or "").strip()
    if value.lower() in ("codex:default", "openai:default"):
        return ""
    if value.startswith(("codex:", "openai:")):
        return value.split(":", 1)[1]
    for m in cached_models():
        if value.lower() in (m["slug"].lower(), str(m.get("display_name", "")).lower()):
            return m["slug"]
    return value.lower().replace(" ", "-")


def _verbosity_args(model: str, level: str | None) -> list[str]:
    """Map Armada's four writing styles to Codex's three native verbosity levels.

    Codex's override is model-dependent. The current GPT families support it; a default or
    unfamiliar model keeps its own preset and Armada's prompt still expresses the preference.
    """
    mid = model_id(model)
    if not mid.startswith("gpt-") or not level:
        return []
    native = {"terse": "low", "brief": "low", "standard": "medium", "full": "high"}.get(level)
    return ["-c", "model_verbosity=" + json.dumps(native)] if native else []


from .contracts import ProviderCapabilities, RunRequest, validate_request

class CodexEngine(EngineAdapter):
    name = "codex"
    capabilities = ProviderCapabilities(streaming=True, cancellation=True, tool_denials=True, raw_tool_results=True)

    def __init__(self, binary="codex"):
        self.binary = binary
        self.allowed_mcp_ids = frozenset()
        self.writable_roots = []
        self.network_access = False
        self.app_server_streaming = True
        self._turn_mcp_ids = ()

    def _launcher(self):
        if getattr(self, "_runtime_launcher", None):
            return self._runtime_launcher
        if self.binary == "codex":
            local = os.environ.get("LOCALAPPDATA")
            install_dir = os.environ.get("CODEX_INSTALL_DIR")
            native = (Path(install_dir) / "codex.exe" if install_dir else
                      Path(local) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe" if local else None)
            if native and native.is_file():
                return [str(native)]
            # Desktop Codex installs its CLI under a versioned bin directory. Prefer
            # that native binary over an older npm shim already present on PATH.
            candidates = list((Path(local) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe")) if local else []
            if candidates:
                return [str(max(candidates, key=lambda p: p.stat().st_mtime))]
        exe = shutil.which(self.binary)
        if not exe and self.binary == "codex":
            # The desktop installer does not require a global npm install or a fresh PATH.
            local = os.environ.get("LOCALAPPDATA")
            installed = Path(local) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe" if local else None
            if installed and installed.is_file():
                return [str(installed)]
            native = Path.home() / ".local" / "bin" / ("codex.exe" if os.name == "nt" else "codex")
            exe = str(native) if native.is_file() else None
        if not exe:
            return None
        if str(exe).lower().endswith((".cmd", ".bat", ".ps1")):
            # Bypass npm's shell shim: prompts and config strings must never become shell code.
            entry = Path(exe).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            node = shutil.which("node")
            return [node, str(entry)] if node and entry.is_file() else None
        return [exe]

    def _standalone_launcher(self):
        """An already installed CLI, never a download or a change to owner settings."""
        exe = shutil.which("codex")
        if not exe:
            return None
        if not str(exe).lower().endswith((".cmd", ".bat", ".ps1")):
            return [exe]
        package = Path(exe).parent / "node_modules" / "@openai" / "codex"
        # npm's platform dependency contains the independently installed native CLI.
        native = sorted(package.glob("node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"))
        if native:
            return [str(native[0])]
        entry = package / "bin" / "codex.js"
        node = shutil.which("node")
        return [node, str(entry)] if node and entry.is_file() else None

    def _execution_probe(self, request, on_proc=None):
        """Verify sandbox execution through the CLI's command/exec RPC; no model turn.

        Fields verified against generated v2/CommandExecParams and real Windows runs
        on CLI 0.157.1 and 0.162.0-alpha.2. Windows rejects outputBytesCap overrides.
        """
        launcher = self._launcher()
        if not launcher:
            return {"ok": False, "reason": "Codex CLI not found. Install Codex CLI and run codex login."}
        responses = []
        models = set()
        wanted_model = model_id(request.model or "")
        marker = "ARMADA_SANDBOX_READY"
        cwd = str(Path(request.cwd or Path.cwd()).resolve())
        shell = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) /
                    "System32/WindowsPowerShell/v1.0/powershell.exe")

        def start(send):
            send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "armada-readiness", "version": "1.0"}}})

        def accept(message, send):
            if message.get("id") == 1 and "result" in message:
                send({"method": "initialized", "params": {}})
                send({"id": 2, "method": "command/exec", "params": {
                    "command": [shell, "-NoProfile", "-Command", "Write-Output " + marker],
                    "cwd": cwd, "timeoutMs": 10000,
                    "sandboxPolicy": {"type": "workspaceWrite",
                        "writableRoots": list(map(str, self.writable_roots)),
                        "networkAccess": bool(self.network_access)}}})
            elif message.get("id") == 2 and "result" in message:
                responses.append(message)
                command = message["result"]
                if wanted_model and command.get("exitCode") == 0 and command.get("stdout", "").strip() == marker:
                    send({"id": 3, "method": "model/list", "params": {"limit": 100, "includeHidden": True}})
                    return False
                return True
            elif message.get("id") == 3 and "result" in message:
                page = message["result"]
                for row in page.get("data", []):
                    models.add(row.get("model") or row.get("id"))
                cursor = page.get("nextCursor")
                if cursor and wanted_model not in models:
                    send({"id": 3, "method": "model/list", "params": {
                        "limit": 100, "includeHidden": True, "cursor": cursor}})
                    return False
                if wanted_model not in models:
                    responses.append({"error": {"message": f"Codex model {wanted_model} is unavailable in this CLI/account. Choose an available model or repair/update Codex."}})
                return True
            elif message.get("id") in (1, 2, 3) and "error" in message:
                responses.append(message)
                return True
            elif "id" in message and "method" in message:
                # A readiness probe cannot approve tools or account changes.
                send({"id": message["id"], "error": {"code": -32601, "message": "Readiness probe only"}})
            return False

        try:
            args = launcher + ["app-server"] + _feature_args()
            args += self._mcp_args(True, request.disallowed_tools, cwd=cwd) + ["-c", "notify=[]"]
            proc = supervise_rpc(args, start=start, on_message=accept, timeout=20,
                                 cwd=cwd, env=request.env or None, on_proc=on_proc)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return {"ok": False, "reason": str(exc)}
        if proc.cancelled:
            return {"ok": False, "cancelled": True, "reason": "Run stopped by the owner."}
        response = responses[-1] if responses else {}
        result = (responses[0].get("result") if responses else None) or {}
        ok = not proc.error and result.get("exitCode") == 0 and result.get("stdout", "").strip() == marker
        ok = ok and not response.get("error")
        reason = proc.error or (response.get("error") or {}).get("message") or (
            "Codex sandbox could not execute the readiness command." if not ok else "")
        return {"ok": ok, "reason": reason}

    def execute(self, request, *, on_event=None, on_proc=None):
        from . import startup
        validate_request(self.name, self.capabilities, request)
        self._runtime_launcher = None
        readiness = None
        if os.name == "nt" and request.allow_tools:
            safe_emit(on_event, {"kind": "status", "text": "Checking Codex execution readiness…"})
            primary = self._launcher()
            readiness = self._execution_probe(request, on_proc)
            reason = readiness.get("reason", "")
            sandbox_failure = any(x in reason.lower() for x in (
                "windows sandbox", "helper_unknown_error", "setup refresh"))
            if not readiness["ok"] and not readiness.get("cancelled") and self.binary == "codex" and sandbox_failure:
                alternate = self._standalone_launcher()
                if alternate and alternate != primary:
                    self._runtime_launcher = alternate
                    second = self._execution_probe(request, on_proc)
                    if second["ok"]:
                        readiness = {"ok": True, "fallback": True, "launcher": alternate,
                                     "primary_launcher": primary, "primary_error": reason}
                        safe_emit(on_event, {"kind": "status", "text":
                            "Desktop Codex sandbox unavailable; using the verified installed standalone Codex CLI."})
                    else:
                        readiness = {**second, "primary_error": reason, "launcher": alternate}
            if not readiness["ok"]:
                reason = readiness["reason"]
                if not readiness.get("cancelled"):
                    reason = "Codex execution environment unavailable: " + reason + (
                        " No job tools were run. Repair/update Codex or select an available model in Edit job.")
                code = "provider_model" if "is unavailable in this CLI/account" in reason else "execution_environment"
                result = startup.failed(reason, code=code, model=request.model or "",
                                        cancelled=bool(readiness.get("cancelled")))
                result.raw["runtime_readiness"] = readiness
                safe_emit(on_event, {"kind": "error", "error": reason})
                return result
        result = super().execute(request, on_event=on_event, on_proc=on_proc)
        if readiness is not None:
            result.raw["runtime_readiness"] = readiness
        return result

    def _probe(self, args, cwd=None):
        launcher = self._launcher()
        if not launcher:
            raise FileNotFoundError("Codex CLI not found. Install Codex CLI and run `codex login`.")
        return subprocess.run(launcher + args, capture_output=True, text=True, timeout=25,
                              encoding="utf-8", errors="replace", **process_options(), cwd=cwd)

    def auth_status(self):
        try:
            result = self._probe(["login", "status"])
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "logged_in": False, "method": "", "reason": str(exc)[:250]}
        detail = (result.stdout + result.stderr).strip()
        logged = result.returncode == 0 and "logged in" in detail.lower() and "not logged in" not in detail.lower()
        known = logged or "not logged in" in detail.lower()
        return {"ok": known, "logged_in": logged,
                "method": "ChatGPT" if "chatgpt" in detail.lower() else "Codex login",
                "reason": "" if logged else "signed-out" if known else "probe-failed"}

    def doctor(self):
        try:
            version = self._probe(["--version"])
            if version.returncode:
                return False, "Codex CLI could not start."
            state = self.auth_status()
            return bool(state["logged_in"]), ((version.stdout.strip() + " · " + state["method"])
                                               if state["logged_in"] else state["reason"])
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)[:250]

    def start_login(self):
        launcher = self._launcher()
        if not launcher:
            return {"ok": False, "error": "Install Codex CLI first, then run `codex login`."}
        try:
            subprocess.Popen(launcher + ["login"], creationflags=0x10 if os.name == "nt" else 0)
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:250]}

    def _mcp_args(self, allow_tools, denied, cwd=None):
        # Enumerate the effective config through the CLI so project-level servers are covered too.
        # Never log the payload: MCP configuration may contain credentials.
        result = self._probe(_feature_args() + ["mcp", "list", "--json"], cwd=cwd)
        if result.returncode:
            raise ValueError("Could not inspect Codex MCP configuration; refusing to run without capability gating.")
        try:
            servers = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid Codex MCP inventory; refusing a tool turn.") from exc
        if not isinstance(servers, list):
            raise ValueError("Unexpected Codex MCP inventory.")
        if allow_tools and getattr(self, 'connector_requirements', None):
            from ..connector_registry import verify_registrations
            verify_registrations(self.connector_requirements, {
                s.get('name'): (s.get('transport') or {}).get('url', '') for s in servers
                if isinstance(s, dict) and s.get('enabled', True) and isinstance(s.get('transport'), dict)})
        args = []
        denied = {str(p).removeprefix("mcp__").removesuffix("__*") for p in (denied or [])}
        seen = set()
        granted = set()
        for server in servers:
            if (not isinstance(server, dict) or not isinstance(server.get("name"), str)
                    or not server["name"] or server["name"] in seen
                    or ("enabled" in server and type(server["enabled"]) is not bool)):
                raise ValueError("Invalid Codex MCP inventory; refusing a tool turn.")
            seen.add(server["name"])
            if server["name"] in (self.allowed_mcp_ids or ()) and server["name"] not in denied and allow_tools:
                granted.add(server["name"])
            if not server.get("enabled", True):
                continue
            sid = server.get("name", "")
            if sid in granted and sid in getattr(self, 'connector_requirements', {}):
                # The owner granted this connector in ARMADA. Translate that grant only
                # for this invocation, keeping shell approvals and other servers unchanged.
                # Codex's explicit per-tool policies still override this server default.
                args += ['-c', f'mcp_servers.{sid}.default_tools_approval_mode="approve"']
            if sid and (not allow_tools or sid in denied or
                        sid not in (self.allowed_mcp_ids or ())):
                if not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
                    raise ValueError(f"Rename Codex MCP server {sid!r} using letters, numbers, _ or - so Armada can gate it.")
                args += ["-c", f"mcp_servers.{sid}.enabled=false"]
        self._turn_mcp_ids = tuple(sorted(granted))
        return args

    def _args(self, model, allow_tools, effort, denied, cwd=None, verbosity=None):
        args = ["exec", "--json", "--color", "never", "--skip-git-repo-check", "--ephemeral",
                "--sandbox", "workspace-write" if allow_tools and not getattr(self, "managed_tools", None) else "read-only",
                "-c", 'approval_policy="never"']
        # App/desktop tools and plugin servers do not share Armada's MCP grants. Keep these off
        # until they have an explicit transport; a Claude plugin grant is not a Codex app grant.
        args += _feature_args()
        if not allow_tools or getattr(self, "managed_tools", None):
            for feature in ("shell_tool", "unified_exec", "image_generation", "view_image", "code_mode"):
                args += ["-c", f"features.{feature}=false"]
            args += ["-c", 'web_search="disabled"']
        else:
            for root in self.writable_roots:
                args += ["--add-dir", str(root)]
            if self.network_access:
                args += ["-c", "sandbox_workspace_write.network_access=true"]
        if model_id(model):
            args += ["--model", model_id(model)]
        if effort:
            levels = next((m.get("supported_reasoning_levels", []) for m in cached_models()
                           if m["slug"] == model_id(model)), [])
            supported = [x["effort"] for x in levels if isinstance(x, dict) and x.get("effort")]
            if supported and effort not in supported:
                raise ValueError(f"{model_id(model)} does not support effort {effort!r}. "
                                 f"Choose one of: {', '.join(supported)}.")
            args += ["-c", "model_reasoning_effort=" + json.dumps(effort)]
        args += _verbosity_args(model, verbosity)
        if getattr(self, "managed_tools", None):
            from ..managed_tools import codex_args
            args += codex_args(self, cwd=cwd)
        else:
            args += self._mcp_args(allow_tools, denied, cwd=cwd)
        return args + ["-"]

    def run(self, system, prompt, model=None, cwd=None, allow_tools=False, timeout=300,
            effort=None, fallback_model=None, max_budget_usd=None, disallowed_tools=None, only_tools=None,
            verbosity=None, env=None):
        return self.run_stream(system, prompt, model=model, cwd=cwd, allow_tools=allow_tools,
                               timeout=timeout, effort=effort, fallback_model=fallback_model,
                               max_budget_usd=max_budget_usd, disallowed_tools=disallowed_tools,
                               only_tools=only_tools, verbosity=verbosity, env=env)

    def run_stream(self, system, prompt, model=None, cwd=None, allow_tools=False, timeout=300,
                   on_event=None, on_proc=None, effort=None, fallback_model=None,
                   max_budget_usd=None, disallowed_tools=None, only_tools=None, verbosity=None, env=None):
        if getattr(self, "managed_tools", None):
            env = {**(env or {}), **self.managed_tools.server_config["env"]}
        emit = lambda event: safe_emit(on_event, event)
        try:
            validate_request(self.name, self.capabilities, RunRequest(system, prompt,
                fallback_model=fallback_model, max_budget_usd=max_budget_usd,
                disallowed_tools=tuple(disallowed_tools or ()),
                only_tools=tuple(only_tools) if only_tools is not None else None))
        except ValueError as exc:
            return RunResult(ok=False, error=str(exc))
        launcher = self._launcher()
        if not launcher:
            return RunResult(ok=False, error="Codex CLI not found. Install it and run `codex login`.")
        if allow_tools and self.allowed_mcp_ids:
            discovery = ("Granted MCP tools may be deferred from the initial tool list. "
                         "Use Codex tool search if available, or call exposed tools directly, before concluding a "
                         "connection is unavailable. Search for a concrete read operation, "
                         "then call the returned tool. An empty MCP resources list does not "
                         "mean there are no tools. Report an actual search or call failure.")
            if any("Interactive_Brokers_IBKR" in sid for sid in self.allowed_mcp_ids):
                discovery += (" For IBKR account reads, search for 'IBKR get_account_positions' "
                              "or the relevant get_account_* read tool. Do not use order-creation "
                              "or order-deletion tools.")
            system += "\n\n" + discovery
            prompt = ("# Required MCP tool discovery\n" + discovery +
                      "\n\n# Agent request\n" + prompt)
        native_apps = bool(allow_tools and getattr(self, 'allowed_app_ids', ()) and not getattr(self, 'managed_tools', None))
        if native_apps and not self.app_server_streaming:
            return RunResult(ok=False, error='Native Codex connectors require app-server support. Update Codex CLI.')
        if (on_event is not None or (allow_tools and self.allowed_mcp_ids) or native_apps) and self.app_server_streaming:
            return self._run_app_stream(launcher, system, prompt, model, cwd, allow_tools,
                                        timeout, on_event, on_proc, effort, disallowed_tools, verbosity, env)
        # No-tool helper turns run outside the realm so project instructions cannot introduce
        # local hooks or capabilities. Model/context selection remains Armada's responsibility.
        temp = tempfile.TemporaryDirectory(prefix="armada-codex-") if not allow_tools else None
        run_cwd = temp.name if temp else cwd
        state = _Stream(emit, model_id(model) or "codex:default", cwd)
        result = None
        try:
            args = self._args(model, allow_tools, effort, disallowed_tools, cwd=run_cwd,
                              verbosity=verbosity)
            def accept(line):
                from .raw_results import loads_event
                event = loads_event(line)
                if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                    raise ValueError("Malformed Codex stream event")
                state.accept(event)
            if env and env.get("ARMADA_RAW_DIR"):
                args = ["-c", "shell_environment_policy.set.ARMADA_RAW_DIR=" + json.dumps(env["ARMADA_RAW_DIR"])] + args
            process = supervise(launcher + args, prompt="# Armada agent instructions and memory\n" + system +
                                "\n\n# Conversation and current request\n" + prompt, on_line=accept,
                                timeout=timeout, cwd=run_cwd, env={**os.environ, **(env or {})}, on_proc=on_proc)
            error = process.error or state.error
            if not state.completed and not error:
                error = "Codex ended before completing the turn."
            if error:
                emit({"kind": "error", "error": error})
            result = RunResult(ok=state.completed and not error, output="\n".join(state.texts),
                             error=error, usage=state.usage, model=state.model, cancelled=process.cancelled,
                             timed_out=getattr(process, "timed_out", False))
            return result
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            log.debug("Codex turn failed", exc_info=True)
            emit({"kind": "error", "error": str(exc)})
            result = RunResult(ok=False, output="\n".join(state.texts), error=str(exc))
            return result
        finally:
            if temp:
                try:
                    temp.cleanup()
                except OSError as exc:
                    log.exception("Codex temporary directory cleanup failed")
                    if result is not None:
                        result.ok = False
                        result.error = result.error or f"Codex temporary directory cleanup failed: {exc}"

    def _run_app_stream(self, launcher, system, prompt, model, cwd, allow_tools,
                        timeout, on_event, on_proc, effort, disallowed_tools, verbosity=None, env=None):
        """Stream actual Codex text deltas while keeping each Armada turn isolated and ephemeral."""
        emit = lambda event: safe_emit(on_event, event)
        temp = tempfile.TemporaryDirectory(prefix="armada-codex-") if not allow_tools else None
        run_cwd = temp.name if temp else cwd
        result = None
        from contextlib import ExitStack
        startup = ExitStack()
        try:
            args = _feature_args() + _verbosity_args(model, verbosity)
            native_apps = frozenset(getattr(self, 'allowed_app_ids', ())) if allow_tools and not getattr(self, 'managed_tools', None) else frozenset()
            if native_apps:
                from ..codex_apps import scoped_args
                args += scoped_args(native_apps, cwd=run_cwd)
            if env and env.get("ARMADA_RAW_DIR"):
                args += ["-c", "shell_environment_policy.set.ARMADA_RAW_DIR=" + json.dumps(env["ARMADA_RAW_DIR"])]
            if not allow_tools or getattr(self, "managed_tools", None):
                for feature in ("shell_tool", "unified_exec", "image_generation", "view_image", "code_mode"):
                    args += ["-c", f"features.{feature}=false"]
                args += ["-c", 'web_search="disabled"']
            if getattr(self, "managed_tools", None):
                from ..managed_tools import codex_args
                args += codex_args(self, cwd=run_cwd)
            else:
                args += self._mcp_args(allow_tools, disallowed_tools, cwd=run_cwd)
            state = _AppStream(emit, model_id(model) or "codex:default", cwd)
            readiness = []
            pending_servers = list(self._turn_mcp_ids)
            if pending_servers:
                from .mcp_runtime import startup_lock
                startup.enter_context(startup_lock())
            full_prompt = ("# Armada agent instructions and memory\n" + system +
                           "\n\n# Conversation and current request\n" + prompt)
            def start(send):
                send({"id": 1, "method": "initialize", "params": {"clientInfo": {
                    "name": "armada", "title": "Armada", "version": "1.0"},
                    **({'capabilities': {'experimentalApi': True}} if native_apps else {})}})
            def begin_turn(send):
                from .mcp_runtime import prompt as readiness_prompt
                params = {"threadId": state.thread_id, "input": [{"type": "text", "text": full_prompt +
                          (readiness_prompt(readiness) if readiness else "")}], "approvalPolicy": "never",
                          "sandboxPolicy": {"type": "workspaceWrite", "writableRoots": [str(p) for p in self.writable_roots],
                                            "networkAccess": bool(self.network_access)} if allow_tools and not getattr(self, "managed_tools", None) else {"type": "readOnly"}}
                if effort:
                    params["effort"] = effort
                params['input'].extend({'type': 'mention', 'name': sid, 'path': 'app://' + sid}
                                       for sid in sorted(native_apps))
                send({"id": 3, "method": "turn/start", "params": params})
            def check_next(send):
                if pending_servers:
                    sid = pending_servers[0]
                    emit({"kind": "tool", "id": "mcp-startup-" + sid, "name": "Connector startup: " + sid, "input": {}})
                    send({"id": 4, "method": "mcpServerStatus/list", "params": {
                        "threadId": state.thread_id, "serverName": sid, "detail": "toolsAndAuthOnly"}})
                else:
                    startup.close()
                    if native_apps:
                        send({'id': 5, 'method': 'app/installed', 'params': {
                            'threadId': state.thread_id, 'forceRefresh': True}})
                    else:
                        begin_turn(send)
            def accept(message, send):
                if "id" in message and "method" in message:
                    # The thread is configured for no approvals. Fail closed if a server request
                    # still arrives, rather than silently granting a shell/MCP action.
                    send({"id": message["id"], "error": {"code": -32601,
                          "message": "Armada does not grant interactive tool approvals."}})
                    return False
                rid = message.get("id")
                if rid == 5:
                    from ..codex_apps import verify_snapshot
                    if message.get('error'):
                        raise ValueError('Codex could not verify native connector permissions. Update Codex CLI and recheck.')
                    verify_snapshot(message.get('result', {}), native_apps)
                    begin_turn(send)
                    return False
                if rid == 4:
                    from .mcp_runtime import status as connector_status
                    sid = pending_servers.pop(0)
                    row = connector_status(sid, message)
                    readiness.append(row)
                    if sid in getattr(self, 'connector_requirements', {}) and row['state'] != 'ready':
                        raise ValueError(f"Required connector {sid} is unavailable: {row['error']}")
                    emit({"kind": "tool_result", "id": "mcp-startup-" + sid,
                          "content": (f"Ready: {len(row['tool_names'])} callable tools" if row["state"] == "ready" else row["error"]),
                          "is_error": row["state"] != "ready"})
                    check_next(send)
                    return False
                if rid in (1, 2, 3):
                    if "error" in message:
                        error = message["error"]
                        raise ValueError(str(error.get("message", error) if isinstance(error, dict) else error))
                    if rid == 1:
                        send({"method": "initialized", "params": {}})
                        params = {"cwd": run_cwd, "approvalPolicy": "never",
                                  "sandbox": "workspace-write" if allow_tools and not getattr(self, "managed_tools", None) else "read-only",
                                  "ephemeral": True, "serviceName": "armada"}
                        if model_id(model):
                            params["model"] = model_id(model)
                        send({"id": 2, "method": "thread/start", "params": params})
                    elif rid == 2:
                        started = message.get("result", {})
                        thread = started.get("thread", {})
                        tid = thread.get("id")
                        if not isinstance(tid, str) or not tid:
                            raise ValueError("Codex did not return a thread id")
                        state.thread_id = tid
                        # thread/start reports the resolved model, including when the CLI
                        # chose its default. Persist that identity with the run's token usage.
                        resolved = started.get("model")
                        if isinstance(resolved, str) and resolved.strip():
                            state.model = resolved.strip()
                        check_next(send)
                    return False
                return state.accept(message)
            process = supervise_rpc(launcher + ["app-server"] + args, start=start,
                                    on_message=accept, timeout=timeout, cwd=run_cwd, env={**os.environ, **(env or {})},
                                    on_proc=on_proc)
            error = process.error or state.error
            if not state.completed and not error:
                error = "Codex ended before completing the turn."
            if error:
                emit({"kind": "error", "error": error})
            result = RunResult(ok=state.completed and not error, output=state.output,
                               error=error, usage=state.usage, model=state.model,
                               raw={"connector_runtime": readiness},
                               cancelled=process.cancelled, timed_out=getattr(process, "timed_out", False))
            return result
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            log.debug("Codex app-server turn failed", exc_info=True)
            emit({"kind": "error", "error": str(exc)})
            result = RunResult(ok=False, error=str(exc))
            return result
        finally:
            startup.close()
            if temp:
                try:
                    temp.cleanup()
                except OSError as exc:
                    log.exception("Codex temporary directory cleanup failed")
                    if result is not None:
                        result.ok = False
                        result.error = result.error or f"Codex temporary directory cleanup failed: {exc}"


class _Stream:
    """Normalize completed items once; a started/updated item is never an extra reply."""
    def __init__(self, emit, model="", cwd=None):
        self.emit, self.model, self.cwd = emit, model, cwd
        self.texts, self.seen = [], set()
        self.usage, self.error, self.completed = Usage(), "", False

    def accept(self, event):
        kind = event.get("type")
        if self.completed and kind not in ("error", "turn.failed"):
            raise ValueError("Codex emitted an event after its terminal result")
        if kind == "thread.started":
            self.emit({"kind": "start"})
        elif kind == "turn.completed":
            usage = event.get("usage", {})
            if not isinstance(usage, dict):
                raise ValueError("Invalid Codex terminal usage")
            total, cached = int(usage.get("input_tokens") or 0), int(usage.get("cached_input_tokens") or 0)
            self.usage = Usage(input=max(0, total - cached) if "input_tokens" in usage else None, cache_read=cached,
                               output=int(usage["output_tokens"]) if "output_tokens" in usage else None)
            self.completed = True
        elif kind in ("error", "turn.failed"):
            error = event.get("error") or event.get("message") or "Codex turn failed"
            self.error = str(error.get("message", error) if isinstance(error, dict) else error)
        elif kind in ("item.started", "item.completed"):
            item = event.get("item")
            if not isinstance(item, dict):
                raise ValueError("Invalid Codex item")
            iid, itype = item.get("id", ""), item.get("type")
            completed = kind == "item.completed"
            if completed and iid and iid in self.seen:
                return
            if completed:
                self.seen.add(iid)
            if itype == "agent_message" and completed:
                text = item.get("text", "")
                if not isinstance(text, str):
                    raise ValueError("Invalid Codex message text")
                self.texts.append(text)
                self.emit({"kind": "text", "text": text})
            elif itype == "reasoning" and completed:
                self.emit({"kind": "thinking", "text": item.get("text", "")})
            elif itype == "file_change" and completed:
                if item.get("status") != "failed":
                    for index, change in enumerate(item.get("changes") or []):
                        path = change.get("path", "")
                        if path and not Path(path).is_absolute() and self.cwd:
                            path = str(Path(self.cwd) / path)
                        self.emit({"kind": "tool", "name": "Edit", "id": f"{iid}:{index}",
                                   "input": {"file_path": path}, "category": "file_change"})
            elif itype in ("command_execution", "mcp_tool_call", "web_search"):
                name, inp = {"command_execution": ("Bash", {"command": item.get("command", "")}),
                             "mcp_tool_call": (f"mcp__{item.get('server', '')}__{item.get('tool', '')}", item.get("arguments") or {}),
                             "web_search": ("WebSearch", {"query": item.get("query", "")})}[itype]
                if not completed:
                    self.emit({"kind": "tool", "name": name, "id": iid, "input": inp})
                else:
                    from .raw_results import result_source
                    field = "result" if itype == "mcp_tool_call" and item.get("result") is not None else (
                        "error" if itype == "mcp_tool_call" else "aggregated_output")
                    self.emit({"kind": "tool_result", "id": iid, "name": name, "input": inp,
                               "raw_result": result_source(event, ("item", field)),
                               "content": str(item.get("aggregated_output") or item.get("result") or "")[:4000],
                               "is_error": item.get("status") == "failed" or bool(item.get("exit_code")) or bool(item.get("error")) or (isinstance(item.get("result"), dict) and bool(item["result"].get("isError")))})


class _AppStream:
    """Translate Codex app-server notifications into Armada's durable turn events."""
    def __init__(self, emit, model="", cwd=None):
        self.emit, self.model, self.cwd = emit, model, cwd
        self.thread_id = ""
        self.deltas, self.messages, self.reasoning = {}, [], {}
        self.usage, self.error, self.completed = Usage(), "", False

    @property
    def output(self):
        return "\n\n".join(self.messages) if self.messages else "\n\n".join(self.deltas.values())

    def accept(self, message):
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(method, str) or not isinstance(params, dict):
            return False
        tid = params.get("threadId")
        if tid and self.thread_id and tid != self.thread_id:
            return False
        if method == "item/agentMessage/delta":
            iid, delta = params.get("itemId"), params.get("delta")
            if not isinstance(iid, str) or not isinstance(delta, str):
                raise ValueError("Malformed Codex message delta")
            if iid not in self.deltas and self.deltas:
                self.emit({"kind": "text", "text": "\n\n"})
            self.deltas[iid] = self.deltas.get(iid, "") + delta
            self.emit({"kind": "text", "text": delta})
        elif method == "item/reasoning/summaryTextDelta":
            iid, delta = params.get("itemId"), params.get("delta")
            if isinstance(iid, str) and isinstance(delta, str):
                self.reasoning[iid] = self.reasoning.get(iid, "") + delta
        elif method in ("item/started", "item/completed"):
            item = params.get("item")
            if not isinstance(item, dict):
                raise ValueError("Malformed Codex item")
            iid, itype = item.get("id", ""), item.get("type")
            completed = method == "item/completed"
            if itype == "agentMessage" and completed:
                text = item.get("text", "")
                if not isinstance(text, str):
                    raise ValueError("Malformed Codex agent message")
                if iid not in self.deltas and text:
                    if self.messages:
                        self.emit({"kind": "text", "text": "\n\n"})
                    self.emit({"kind": "text", "text": text})
                self.messages.append(text)
            elif itype == "reasoning" and completed:
                summary = self.reasoning.pop(iid, "") or item.get("summary") or ""
                if isinstance(summary, list):
                    summary = "\n".join(str(x.get("text", "")) for x in summary if isinstance(x, dict))
                if summary:
                    self.emit({"kind": "thinking", "text": str(summary)})
            elif itype in ("commandExecution", "mcpToolCall", "webSearch"):
                name, inp = {
                    "commandExecution": ("Bash", {"command": item.get("command", "")}),
                    "mcpToolCall": (f"mcp__{item.get('server', '')}__{item.get('tool', '')}",
                                    item.get("arguments") or {}),
                    "webSearch": ("WebSearch", {"query": item.get("query", "")}),
                }[itype]
                if not completed:
                    self.emit({"kind": "tool", "name": name, "id": iid, "input": inp})
                else:
                    from .raw_results import result_source
                    field = "result" if itype == "mcpToolCall" and item.get("result") is not None else (
                        "error" if itype == "mcpToolCall" else "aggregatedOutput")
                    self.emit({"kind": "tool_result", "id": iid, "name": name, "input": inp,
                               "raw_result": result_source(message, ("params", "item", field)),
                               "content": str(item.get("aggregatedOutput") or item.get("result") or
                                              item.get("error") or "")[:4000],
                               "is_error": item.get("status") == "failed" or bool(item.get("exitCode")) or bool(item.get("error")) or (isinstance(item.get("result"), dict) and bool(item["result"].get("isError")))})
            elif itype == "fileChange" and completed and item.get("status") != "failed":
                for index, change in enumerate(item.get("changes") or []):
                    if not isinstance(change, dict):
                        continue
                    path = change.get("path", "")
                    if path and not Path(path).is_absolute() and self.cwd:
                        path = str(Path(self.cwd) / path)
                    self.emit({"kind": "tool", "name": "Edit", "id": f"{iid}:{index}",
                               "input": {"file_path": path}, "category": "file_change"})
        elif method == "thread/tokenUsage/updated":
            last = (params.get("tokenUsage") or {}).get("last") or {}
            if isinstance(last, dict):
                total, cached = int(last.get("inputTokens") or 0), int(last.get("cachedInputTokens") or 0)
                self.usage = Usage(input=max(0, total - cached), cache_read=cached,
                                   output=int(last.get("outputTokens") or 0))
        elif method == "error":
            detail = params.get("error") or params.get("message") or "Codex turn failed"
            self.error = str(detail.get("message", detail) if isinstance(detail, dict) else detail)
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            status = turn.get("status")
            if status != "completed":
                detail = turn.get("error") or status or "Codex turn failed"
                self.error = str(detail.get("message", detail) if isinstance(detail, dict) else detail)
            self.completed = True
            return True
        return False
