"""Claude engine adapter — drives Claude Code in headless/print mode on the user's
Pro/Max subscription (SPEC §9, §17). Subscription-priced: we run with a CLEAN env that
strips ANTHROPIC_API_KEY, so `claude -p` bills the logged-in plan, not the metered API.

Invocation (Claude Code 2.1.x): `claude -p "<prompt>" --output-format json
[--tools default | --tools ""] [--model M] [--system-prompt "<system>"]`.
Tool turns (allow_tools) load the FULL harness — real MCP servers, skills and plugins — so
agents can actually use their capabilities; no-tool turns add --safe-mode (skips that harness,
keeping subscription/OAuth auth) plus --tools "" to strip tool SCHEMAS from context (a token win).

Windows launcher: npm installs `claude.cmd`, whose real entry (per package.json "bin") is
a NATIVE `bin/claude.exe` (confirmed on 2.1.260). We run that .exe DIRECTLY (a .js entry
would be run via `node`), so empty-string args like `--tools ""` survive — going through
the `cmd /c` shim eats them. Falls back to the cmd shim + a non-empty deny-list if the
native/js entry can't be resolved.
"""
from __future__ import annotations
from ..background import process_options
import json, os, re, shutil, subprocess, tempfile, time
from typing import Optional, Callable
from .base import EngineAdapter, RunResult, Usage
from .mcp import server_id as _mcp_server_id
from .mcp import connected_names
from .process import supervise, safe_emit
import logging
from ..util import swallowed
log = logging.getLogger(__name__)

_DENY = "Bash Read Edit Write Glob Grep WebFetch WebSearch Task NotebookEdit BashOutput KillShell"


def _verbosity_system(system, level):
    """Honor the shared writing-style setting without duplicating an assembled prompt section."""
    if not level:
        return system
    from ..verbosity import prompt_block
    block = prompt_block(level)
    return system if block in system else system + "\n\n" + block


def _recover_auth_cache(verified_names, probe_started):
    """Remove old negative health markers only after a granted server's live success.

    This is CLI health metadata, not OAuth storage. Preserve other servers and any
    failure written since the live probe began. Unknown formats remain untouched.
    """
    from pathlib import Path
    import math
    # Do not guess a vendor cache location when the owner uses a custom config.
    if not verified_names or os.environ.get('CLAUDE_CONFIG_DIR'):
        return frozenset()
    path = Path.home() / '.claude/mcp-needs-auth-cache.json'
    temporary = ''
    try:
        if path.stat().st_size > 1024 * 1024:
            return frozenset()
        original = path.read_bytes()
        data = json.loads(original.decode('utf-8-sig'))
        if not isinstance(data, dict):
            return frozenset()
        removable = set()
        for name in verified_names:
            entry = data.get(name)
            if not isinstance(entry, dict) or not set(entry).issubset({'timestamp', 'id'}):
                continue
            timestamp = entry.get('timestamp')
            if (type(timestamp) in (int, float) and math.isfinite(timestamp)
                    and 0 <= timestamp <= probe_started * 1000):
                removable.add(name)
        if not removable:
            return frozenset()
        for name in removable:
            data.pop(name)
        fd, temporary = tempfile.mkstemp(prefix='armada-mcp-health-', suffix='.tmp', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != original:
            return frozenset()  # Another CLI wrote newer state; leave it alone.
        os.replace(temporary, path)
        return frozenset(removable)
    except (OSError, ValueError):
        log.debug('Could not reconcile Claude MCP health cache; leaving existing state intact.')
        return frozenset()
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError:
                log.debug('Could not remove temporary MCP health cache file.')


def _mcp_inventory(text: str) -> list[str]:
    """Parse the CLI's human inventory strictly; unknown output is never an empty inventory.

    Keep only names. Commands/URLs can contain credentials and must not reach logs or reports.
    """
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    names, empty = [], False
    for line in text.splitlines():
        line = line.strip()
        if not line or line in ("Checking MCP server health...", "Checking MCP server health…"):
            continue
        if line.startswith("No MCP servers configured"):
            empty = True
            continue
        name, sep, detail = line.partition(": ")
        if not sep or " - " not in detail or not name or any(ord(c) < 32 for c in name):
            raise ValueError("Could not validate Claude MCP inventory; inspect `claude mcp list` before running tools.")
        if name in names or empty:
            raise ValueError("Ambiguous Claude MCP inventory; refusing a tool turn.")
        names.append(name)
    if (not names and not empty) or (names and empty):
        raise ValueError("Incomplete Claude MCP inventory; refusing a tool turn.")
    return names

def _sealed_tool_args(tools: list) -> list:
    """A turn that may use exactly `tools` and nothing else (THREAT_MODEL T4, launch plan 5.8b).

    --safe-mode loads none of the owner's customisations — no MCP servers, skills, plugins, hooks or
    CLAUDE.md — so a connector that can send, pay or write is not even present. --tools limits the
    built-ins to the list; --allowedTools pre-approves those so the turn doesn't stall on a prompt;
    and --permission-prompts none refuses anything else that would ask. Deliberately NOT
    --dangerously-skip-permissions: nothing here should be able to approve its way past the list.
    Verified against Claude Code 2.1.263's --help.
    """
    names = [str(t) for t in tools if t]
    return ["--safe-mode", "--tools", ",".join(names),
            "--allowedTools", *names, "--permission-prompts", "none"]


# Windows caps a whole command line at 32,767 characters, and an agent's assembled context — covenant,
# soul, mandate, tenets, memories, capability preamble — passes that mark once a realm is real: eight
# ministers here run 21K–34K, and the first one over the line failed every turn with
# "[WinError 206] The filename or extension is too long", which says nothing about what went wrong.
# Above this many characters the system prompt goes to a file and travels as --system-prompt-file.
# Below it, it stays on argv exactly as before, so the short internal turns (thread summaries, agent
# naming) keep the path that has always worked, whatever Claude Code version is installed.
_SYSTEM_ARGV_MAX = 12000


def _drop_system_file(path: str) -> None:
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass


def _system_args(system: str):
    """(args, path_to_clean_up) for one system prompt.

    The file is written UTF-8 with no BOM in the OS temp dir and deleted by the caller's finally,
    so a crashed turn leaves at most one stale file where the OS already sweeps."""
    if not system:
        return [], ""
    if len(system) <= _SYSTEM_ARGV_MAX:
        return ["--system-prompt", system], ""
    path = ""
    try:
        fd, path = tempfile.mkstemp(prefix="armada-sys-", suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(system)
    except Exception:  # noqa - fall back to argv rather than lose the turn outright
        swallowed(log, '_system_args: failed; falling back')
        _drop_system_file(path)
        return ["--system-prompt", system], ""
    return ["--system-prompt-file", path], path
# On Windows, spawn the CLI without a console window (otherwise a black 'claude' window flashes up
# over the app every turn). 0x08000000 = CREATE_NO_WINDOW.
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_ALIASES = ("opus", "sonnet", "haiku", "fable")


def _advanced_args(fallback_model: Optional[str], max_budget_usd: Optional[float]) -> list[str]:
    """Optional per-run guardrail flags (verified present in Claude Code 2.1.x --help):
      --fallback-model <m>   switch model if the primary is overloaded/unavailable
      --max-budget-usd <n>   hard spend ceiling for the run (only honoured with --print, which we use)
    Empty/None values contribute nothing, so a run without them behaves exactly as before."""
    out: list[str] = []
    fb = (fallback_model or "").strip()
    if fb:
        out += ["--fallback-model", fb]
    try:
        b = float(max_budget_usd) if max_budget_usd is not None else 0.0
    except (TypeError, ValueError):
        b = 0.0
    if b > 0:
        out += ["--max-budget-usd", (f"{b:.4f}".rstrip("0").rstrip("."))]
    return out


def _mu_tokens(v) -> int:
    """Total tokens recorded for one modelUsage entry (handles the CLI's camel/snake key spellings)."""
    if not isinstance(v, dict):
        return 0
    return sum(int(v.get(k, 0) or 0) for k in
               ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens",
                "input_tokens", "output_tokens", "cache_read_input_tokens"))


def _usage_from_event(ev: dict) -> Usage:
    """Total tokens for a run, preferring `modelUsage` over the `usage` block.

    Two things the `usage` block leaves out, both found by dumping a real result event rather than
    trusting the field names:

    * **A run can use more than one model.** Claude Code calls a small background model (Haiku, for
      titles and similar) alongside the one you asked for. `usage` describes the main model only,
      so those tokens were invisible — 897 of 2,954 in the run that exposed this.
    * **Cache *creation*.** A fresh context is written to cache, not read from it, so on the first
      turn of a thread the entire prompt appears under `cache_creation_input_tokens` and nowhere
      else. Counting only input/output/cache_read reported 6 tokens for that same 2,954-token run.

    `modelUsage` is keyed by concrete model id and carries all four counters for each, so it is the
    whole run. The `usage` block is the fallback for when it is absent.
    """
    mu = ev.get("modelUsage")
    cost = float(ev["total_cost_usd"]) if ev.get("total_cost_usd") is not None else None
    if isinstance(mu, dict) and mu:
        inp = out = cr = cw = 0
        for v in mu.values():
            if not isinstance(v, dict):
                inp = out = None
                continue
            inp = inp + int(v["inputTokens"]) if inp is not None and v.get("inputTokens") is not None else None
            out = out + int(v["outputTokens"]) if out is not None and v.get("outputTokens") is not None else None
            cr += int(v.get("cacheReadInputTokens", 0) or 0)
            cw += int(v.get("cacheCreationInputTokens", 0) or 0)
        return Usage(input=inp, output=out, cache_read=cr, cache_write=cw, cost_usd=cost)
    u = ev.get("usage", {}) or {}
    return Usage(input=int(u["input_tokens"]) if u.get("input_tokens") is not None else None,
                 output=int(u["output_tokens"]) if u.get("output_tokens") is not None else None,
                 cache_read=int(u.get("cache_read_input_tokens", 0) or 0),
                 cache_write=int(u.get("cache_creation_input_tokens", 0) or 0),
                 cost_usd=cost)


def _concrete_model(reported, model_usage, fallback: str = "") -> str:
    """Concrete versioned model id for logging (so usage shows 'Opus 4.8', not bare 'Opus'). The CLI's
    `model` field is sometimes just the family alias we passed ('opus'); `modelUsage` is keyed by the
    real versioned ids. Claude Code may ALSO use a small background model (e.g. Haiku for titles), so
    pick the modelUsage entry that did the most work — not just the first key — to get the real model."""
    r = (reported or "").strip()
    if r and r.lower() not in _ALIASES:
        return r
    if isinstance(model_usage, dict) and model_usage:
        return max(model_usage.items(), key=lambda kv: _mu_tokens(kv[1]))[0]
    return r or (fallback or "")


from .contracts import ProviderCapabilities, RunRequest, validate_request

class ClaudeEngine(EngineAdapter):
    name = "claude"
    capabilities = ProviderCapabilities(streaming=True, cancellation=True, budget=True, fallback=True, sealed_tools=True, tool_denials=True, raw_tool_results=True)

    def __init__(self, binary: str = "claude"):
        self.binary = binary
        self._cached: Optional[list[str]] = None
        self.allowed_mcp_ids = frozenset()

    def _mcp_args(self, denied, cwd=None):
        """Deny every effective server absent from this agent's validated grants."""
        if not self._direct():
            raise ValueError("Capability gating requires Claude's native or Node launcher; reinstall Claude Code to repair its launcher.")
        kwargs = dict(capture_output=True, text=True, timeout=25, cwd=cwd, env=self._env(),
                      encoding="utf-8", errors="replace", **process_options())
        version = subprocess.run(self._launcher() + ["--version"], **kwargs)
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version.stdout.strip())
        if version.returncode or not match or tuple(map(int, match.groups())) < (2, 1, 263):
            raise ValueError("Capability gating requires Claude Code 2.1.263 or newer.")
        probe_started = time.time()
        result = subprocess.run(self._launcher() + ["mcp", "list"], **kwargs)
        if result.returncode or result.stderr.strip():
            raise ValueError("Could not inspect Claude MCP configuration; refusing to run without capability gating.")
        names = _mcp_inventory(result.stdout)
        allowed = set(self.allowed_mcp_ids or ())
        patterns = set(denied or ())
        blocked = []
        identities = {}
        for name in names:
            sid = _mcp_server_id(name)
            if sid in identities:
                raise ValueError("Ambiguous Claude MCP server identities; rename the colliding servers.")
            identities[sid] = name
            if (name not in allowed and sid not in allowed) or f"mcp__{sid}" in patterns or f"mcp__{name}" in patterns:
                blocked.append({"serverName": name})
                patterns.add(f"mcp__{sid}")
        if not allowed:
            patterns.add("mcp__*")
        admitted = set(names) - {row['serverName'] for row in blocked}
        _recover_auth_cache(connected_names(result.stdout) & admitted, probe_started)
        args = ["--settings", json.dumps({"deniedMcpServers": blocked})]
        if patterns:
            args += ["--disallowedTools", *sorted(patterns)]
        return args

    # --- launcher resolution ---
    def _direct_launcher(self, exe: str) -> Optional[list[str]]:
        """Resolve Claude Code's real entry, preferring a JS/CJS entry run via `node`.

        npm installs a tiny `bin/claude.exe` STUB (~500 B) that just re-launches node on the
        package's JS wrapper — running that stub directly fails with WinError 216. So we prefer
        `node <wrapper.cjs>` (works across versions; empty-string args like `--tools ""` survive),
        and only run a `.exe` directly if it's a real native binary (not the stub)."""
        try:
            pkg = os.path.join(os.path.dirname(exe), "node_modules", "@anthropic-ai", "claude-code")
            node = shutil.which("node")
            js: list[str] = []
            pj = os.path.join(pkg, "package.json")
            if os.path.exists(pj):
                b = json.loads(open(pj, encoding="utf-8").read()).get("bin")
                rel = b.get("claude") if isinstance(b, dict) else (b if isinstance(b, str) else None)
                if rel and rel.lower().endswith((".js", ".cjs", ".mjs")):
                    js.append(os.path.normpath(os.path.join(pkg, rel)))
            js += [os.path.join(pkg, n) for n in ("cli-wrapper.cjs", "cli.js", "cli.mjs", "cli.cjs")]
            if node:
                for c in js:
                    if os.path.exists(c):
                        return [node, c]                    # JS entry via node (preferred)
            # A real native binary (tens of MB), not the ~500 B npm stub.
            for c in (os.path.join(pkg, "bin", "claude.exe"),):
                if os.path.exists(c) and os.path.getsize(c) > 100_000:
                    return [c]
            return None
        except Exception:  # noqa
            log.debug('_direct_launcher: failed; returning a fallback', exc_info=True)
            return None

    @staticmethod
    def _known_install() -> Optional[str]:
        """Claude Code's native install location, for when it isn't on this process's PATH.

        The native installer puts `claude.exe` in ~/.local/bin and adds that to the *user* PATH —
        which a process started before the install (ARMADA's window, during the setup wizard's
        "Install Claude Code") never sees. Without this, installing from the wizard would say
        "not installed" until ARMADA restarted."""
        for c in (os.path.join(os.path.expanduser("~"), ".local", "bin",
                               "claude.exe" if os.name == "nt" else "claude"),):
            if os.path.isfile(c):
                return c
        return None

    def _launcher(self) -> Optional[list[str]]:
        if self._cached is not None:
            return self._cached or None
        exe = (self._known_install() if self.binary == "claude" else None) or shutil.which(self.binary)
        if not exe:
            self._cached = []
            return None
        if os.name != "nt":
            self._cached = [exe]
            return self._cached
        direct = self._direct_launcher(exe)
        if direct:
            self._cached = direct
            return direct
        # The native installer's claude.exe is the real program (tens of MB), not npm's ~500 B stub:
        # run it directly, so empty-string arguments survive (they don't through cmd /c).
        try:
            if exe.lower().endswith(".exe") and os.path.getsize(exe) > 1_000_000:
                self._cached = [exe]
                return self._cached
        except OSError:
            pass
        shim = exe if exe.lower().endswith((".cmd", ".bat")) else (shutil.which(self.binary + ".cmd") or exe)
        self._cached = ["cmd", "/c", shim]
        return self._cached

    def _direct(self) -> bool:
        """True when we invoke Claude directly (native or node) — empty-string args survive.
        False only for the cmd-shim fallback, which eats empty args."""
        lp = self._launcher() or []
        return bool(lp) and lp[0].lower() != "cmd"

    def _env(self) -> dict:
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)                 # keep OAuth/subscription auth, not metered API
        # Force UTF-8 so scripts the agent runs via its Bash tool (Windows children default to cp1252)
        # don't crash printing Unicode (─, ⚡, €). Inherited by claude's tool subprocesses.
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        return env

    def doctor(self) -> tuple[bool, str]:
        lp = self._launcher()
        if not lp:
            return False, ("Claude Code not found on PATH. Install it (needs Node.js) and run "
                           "`claude login` on your Pro/Max plan.")
        try:
            v = subprocess.run(lp + ["--version"], capture_output=True, text=True, timeout=25,
                               env=self._env(), encoding="utf-8", errors="replace",
                               **process_options())
            if v.returncode != 0:
                return False, f"`claude --version` failed: {(v.stderr or v.stdout).strip()[:200]}"
            ver = (v.stdout or v.stderr).strip().splitlines()[0] if (v.stdout or v.stderr) else "?"
            mode = "direct (lean --tools '' works)" if self._direct() else "cmd-shim (deny-list fallback)"
            return True, f"{ver} · launcher: {mode}. Ensure `claude login` is done on your plan."
        except Exception as e:  # noqa
            swallowed(log, 'doctor: failed; returning a fallback')
            return False, f"Claude Code present but not runnable: {e}"

    # 300s was too short for the work these jobs actually do. A scheduled brief that searches the
    # web, reads a few files and writes a report is routinely past five minutes, and the failure
    # was indistinguishable from a broken job — the agent had done most of the work and lost it.
    # 20 minutes is generous enough that hitting it means something is genuinely stuck; a job can
    # set its own `timeout` when it knows better.
    DEFAULT_TIMEOUT = 1200

    def run(self, system: str, prompt: str, model: Optional[str] = None,
            cwd: Optional[str] = None, allow_tools: bool = False, timeout: int = DEFAULT_TIMEOUT,
            effort: Optional[str] = None, fallback_model: Optional[str] = None,
            max_budget_usd: Optional[float] = None, disallowed_tools: Optional[list] = None,
            only_tools: Optional[list] = None, verbosity: Optional[str] = None, env=None) -> RunResult:
        if model == 'claude:default':
            model = None
        try:
            validate_request(self.name, self.capabilities, RunRequest(system, prompt,
                fallback_model=fallback_model, max_budget_usd=max_budget_usd,
                disallowed_tools=tuple(disallowed_tools or ()),
                only_tools=tuple(only_tools) if only_tools is not None else None))
        except ValueError as exc:
            return RunResult(ok=False, error=str(exc))
        lp = self._launcher()
        if not lp:
            return RunResult(ok=False, error="claude binary not found (install Claude Code)")
        try:
            mcp_args = self._mcp_args(disallowed_tools, cwd) if allow_tools and only_tools is None else []
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return RunResult(ok=False, error=str(exc))
        # The prompt goes on STDIN, not argv: a long thread as a command-line arg overflows Windows'
        # ~32K command-line limit (WinError 206). `claude -p` with no positional prompt reads stdin.
        args = ["-p", "--output-format", "json"]
        if model:
            args += ["--model", model]
        if effort:
            # Effort = adaptive-reasoning level (low/medium/high/xhigh/max) — the CLI's control for
            # "how much the model thinks". Higher = deeper reasoning; 'low' ~= minimal thinking.
            args += ["--effort", effort]
        args += _advanced_args(fallback_model, max_budget_usd)
        # --system-prompt REPLACES Claude Code's default (agentic *coder*) prompt entirely, so the
        # model sees ONLY ARMADA's assembled context — no coder framing that makes it try to explore
        # files. This is the memory-management thesis: ARMADA owns the whole context. (--append-…
        # only adds to the coder prompt, which caused hallucinated tool-call transcripts.) A large
        # one travels by file; see _system_args.
        sys_args, sys_file = _system_args(_verbosity_system(system, verbosity))
        args += sys_args
        if only_tools is not None:
            args += _sealed_tool_args(only_tools)
        elif allow_tools:
            # NO --safe-mode: load the real MCP servers / skills / plugins so the agent can actually
            # use its capabilities (Telegram, filesystem, skills, …), not just be told they exist.
            args += ["--tools", "default", "--dangerously-skip-permissions"]
            args += mcp_args
        elif self._direct():
            args += ["--safe-mode", "--tools", ""]     # no-tool turn: skip the harness + strip schemas (lean)
        else:
            args += ["--safe-mode", "--disallowedTools", _DENY, "--permission-prompts", "none"]
        chunks = []
        size = 0
        def collect(line):
            nonlocal size
            size += len(line)
            if size > 16 * 1024 * 1024:
                raise ValueError("Claude result exceeded the 16 MiB limit")
            chunks.append(line)
        try:
            process = supervise(lp + args, prompt=prompt, on_line=collect, timeout=timeout,
                                cwd=cwd, env={**self._env(), **(env or {})})
        finally:
            _drop_system_file(sys_file)
        raw = "".join(chunks)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("type") != "result":
                raise ValueError("missing terminal result")
            usage = _usage_from_event(data)
            model_used = _concrete_model(data.get("model"), data.get("modelUsage"), model)
            error = process.error or _result_error(data)
        except (ValueError, TypeError, AttributeError) as exc:
            return RunResult(ok=False, output=raw.strip(), model=model or "",
                             error=process.error or f"Invalid Claude result: {exc}",
                             cancelled=process.cancelled, timed_out=getattr(process, "timed_out", False))
        return RunResult(ok=not error, output=str(data.get("result", "")).strip(),
                         usage=usage, model=model_used, error=error, raw=data,
                         cancelled=process.cancelled, timed_out=getattr(process, "timed_out", False))

    def run_stream(self, system: str, prompt: str, model: Optional[str] = None,
                   cwd: Optional[str] = None, allow_tools: bool = False, timeout: int = 600,
                   on_event: Optional[Callable[[dict], None]] = None,
                   on_proc: Optional[Callable] = None, effort: Optional[str] = None,
                   fallback_model: Optional[str] = None,
                   max_budget_usd: Optional[float] = None, disallowed_tools: Optional[list] = None,
                   only_tools: Optional[list] = None, verbosity: Optional[str] = None, env=None) -> RunResult:
        """Run a turn in streaming mode, calling on_event(dict) for each intermediate step
        (thinking / tool use / tool result / text) as Claude Code emits them (stream-json NDJSON).
        Returns the final RunResult; malformed or missing terminal output fails the turn."""
        if model == 'claude:default':
            model = None
        def emit(event):
            safe_emit(on_event, event)
        try:
            validate_request(self.name, self.capabilities, RunRequest(system, prompt,
                fallback_model=fallback_model, max_budget_usd=max_budget_usd,
                disallowed_tools=tuple(disallowed_tools or ()),
                only_tools=tuple(only_tools) if only_tools is not None else None))
        except ValueError as exc:
            return RunResult(ok=False, error=str(exc))
        lp = self._launcher()
        if not lp:
            emit({"kind": "error", "error": "claude binary not found"})
            return RunResult(ok=False, error="claude binary not found")
        try:
            mcp_args = self._mcp_args(disallowed_tools, cwd) if allow_tools and only_tools is None else []
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            emit({"kind": "error", "error": str(exc)})
            return RunResult(ok=False, error=str(exc))
        # prompt via STDIN (see run(): keeps a long thread off the command line — WinError 206)
        args = ["-p", "--output-format", "stream-json", "--verbose",
                "--include-partial-messages"]
        if model:
            args += ["--model", model]
        if effort:
            args += ["--effort", effort]     # adaptive-reasoning level (see run())
        args += _advanced_args(fallback_model, max_budget_usd)
        sys_args, sys_file = _system_args(_verbosity_system(system, verbosity))  # large context travels by file
        args += sys_args
        if only_tools is not None:
            args += _sealed_tool_args(only_tools)
        elif allow_tools:
            # NO --safe-mode: real MCP/skills/plugins load so the agent can actually use its capabilities.
            args += ["--tools", "default", "--dangerously-skip-permissions"]
            args += mcp_args
        elif self._direct():
            args += ["--safe-mode", "--tools", ""]     # no-tool turn: lean, no harness
        else:
            args += ["--safe-mode", "--disallowedTools", _DENY, "--permission-prompts", "none"]
        state = _ClaudeStream(emit, model or "")
        def accept(line):
            from .raw_results import loads_event
            event = loads_event(line)
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError("Malformed Claude stream event")
            state.accept(event)
        try:
            process = supervise(lp + args, prompt=prompt, on_line=accept, timeout=timeout,
                                cwd=cwd, env={**self._env(), **(env or {})}, on_proc=on_proc)
        finally:
            _drop_system_file(sys_file)
        error = process.error or state.error
        if not state.completed and not error:
            error = "Claude ended before completing the turn."
        if error:
            emit({"kind": "error", "error": error})
        return RunResult(ok=state.completed and not error, output=state.output or "".join(state.texts).strip(),
                         error=error, model=state.model, usage=state.usage, cancelled=process.cancelled,
                         timed_out=getattr(process, "timed_out", False))


def _result_error(event):
    for field in ("usage", "modelUsage"):
        if field in event and not isinstance(event[field], dict):
            raise ValueError(f"Malformed Claude {field}")
    if "is_error" in event and not isinstance(event["is_error"], bool):
        raise ValueError("Malformed Claude result status")
    if event.get("is_error") or event.get("subtype", "success") != "success":
        return str(event.get("error") or event.get("errors") or event.get("result") or "Claude turn failed")
    if event.get("subtype") != "success" or not isinstance(event.get("result"), str):
        raise ValueError("Malformed Claude terminal success result")
    return ""


class _ClaudeStream:
    """Claude protocol state; success requires a terminal result and a clean process exit."""
    def __init__(self, emit, model):
        self.emit, self.model = emit, model
        self.texts, self.output, self.error = [], "", ""
        self.usage, self.completed = Usage(), False
        self._partial_text = False

    def accept(self, event):
        kind = event["type"]
        if self.completed:
            raise ValueError("Claude emitted an event after its terminal result")
        if kind == "system" and event.get("subtype") == "init":
            self.emit({"kind": "start"})
        elif kind == "stream_event":
            stream = event.get("event")
            if not isinstance(stream, dict):
                raise ValueError("Invalid Claude partial message")
            if stream.get("type") == "content_block_delta":
                delta = stream.get("delta")
                if not isinstance(delta, dict):
                    raise ValueError("Invalid Claude content delta")
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if not isinstance(text, str):
                        raise ValueError("Invalid Claude text delta")
                    if text:
                        self._partial_text = True
                        self.texts.append(text)
                        self.emit({"kind": "text", "text": text})
        elif kind in ("assistant", "user"):
            message = event.get("message")
            if not isinstance(message, dict):
                raise ValueError("Invalid Claude message")
            blocks = message.get("content", [])
            if not isinstance(blocks, list):
                raise ValueError("Invalid Claude message content")
            for block_index, block in enumerate(blocks):
                bt = block.get("type")
                if bt == "thinking":
                    self.emit({"kind": "thinking", "text": (block.get("thinking") or "").strip()})
                elif bt == "text":
                    text = block.get("text") or ""
                    if text.strip() and not (kind == "assistant" and self._partial_text):
                        self.texts.append(text)
                        self.emit({"kind": "text", "text": text})
                elif bt == "tool_use":
                    self.emit({"kind": "tool", "name": block.get("name", ""),
                               "input": block.get("input", {}), "id": block.get("id", "")})
                elif bt == "tool_result":
                    content = block.get("content")
                    if isinstance(content, list):
                        content = "\n".join(x.get("text", "") for x in content if isinstance(x, dict))
                    from .raw_results import result_source
                    # Claude exposes the MCP structured result outside the message content.
                    path = ("tool_use_result",) if "tool_use_result" in event and len(blocks) == 1 else (
                        "message", "content", block_index, "content")
                    self.emit({"kind": "tool_result", "id": block.get("tool_use_id", ""),
                               "raw_result": result_source(event, path),
                               "content": str(content or "").strip()[:4000],
                               "is_error": bool(block.get("is_error"))})
            if kind == "assistant":
                self._partial_text = False
        elif kind == "result":
            self.usage = _usage_from_event(event)
            self.error = self.error or _result_error(event)
            self.model = _concrete_model(event.get("model"), event.get("modelUsage"), self.model)
            self.output = str(event.get("result", "")).strip()
            self.completed = True
        elif kind == "error":
            self.error = str(event.get("error") or event.get("message") or "Claude turn failed")
