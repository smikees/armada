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
import json, os, shutil, subprocess, tempfile, threading, time
from typing import Optional, Callable
from .base import EngineAdapter, RunResult, Usage
import logging
from ..util import swallowed
log = logging.getLogger(__name__)

_DENY = "Bash Read Edit Write Glob Grep WebFetch WebSearch Task NotebookEdit BashOutput KillShell"

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
    cost = float(ev.get("total_cost_usd", 0.0) or 0.0)
    if isinstance(mu, dict) and mu:
        inp = out = cr = cw = 0
        for v in mu.values():
            if not isinstance(v, dict):
                continue
            inp += int(v.get("inputTokens", 0) or 0)
            out += int(v.get("outputTokens", 0) or 0)
            cr += int(v.get("cacheReadInputTokens", 0) or 0)
            cw += int(v.get("cacheCreationInputTokens", 0) or 0)
        return Usage(input=inp, output=out, cache_read=cr, cache_write=cw, cost_usd=cost)
    u = ev.get("usage", {}) or {}
    return Usage(input=int(u.get("input_tokens", 0) or 0),
                 output=int(u.get("output_tokens", 0) or 0),
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


class ClaudeEngine(EngineAdapter):
    name = "claude"

    def __init__(self, binary: str = "claude"):
        self.binary = binary
        self._cached: Optional[list[str]] = None

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

    def _launcher(self) -> Optional[list[str]]:
        if self._cached is not None:
            return self._cached or None
        exe = shutil.which(self.binary)
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
                               creationflags=_NO_WINDOW)
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
            only_tools: Optional[list] = None) -> RunResult:
        lp = self._launcher()
        if not lp:
            return RunResult(ok=False, error="claude binary not found (install Claude Code)")
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
        sys_args, sys_file = _system_args(system)
        args += sys_args
        if only_tools is not None:
            args += _sealed_tool_args(only_tools)
        elif allow_tools:
            # NO --safe-mode: load the real MCP servers / skills / plugins so the agent can actually
            # use its capabilities (Telegram, filesystem, skills, …), not just be told they exist.
            args += ["--tools", "default", "--dangerously-skip-permissions"]
            if disallowed_tools:     # ARMADA-disabled capabilities are blocked at the tool level
                args += ["--disallowedTools"] + [str(t) for t in disallowed_tools if t]
        elif self._direct():
            args += ["--safe-mode", "--tools", ""]     # no-tool turn: skip the harness + strip schemas (lean)
        else:
            args += ["--safe-mode", "--disallowedTools", _DENY, "--permission-prompts", "none"]
        try:
            p = subprocess.run(lp + args, input=prompt, capture_output=True, text=True, timeout=timeout,
                               cwd=cwd, env=self._env(), encoding="utf-8", errors="replace",
                               creationflags=_NO_WINDOW)
        except subprocess.TimeoutExpired:
            return RunResult(ok=False, error=f"claude timed out after {timeout}s")
        except Exception as e:  # noqa
            swallowed(log, 'run: failed; error returned to the caller')
            return RunResult(ok=False, error=f"claude failed to launch: {e}")
        finally:
            _drop_system_file(sys_file)
        if p.returncode != 0:
            msg = (p.stderr or "").strip()
            if not msg and p.stdout:
                try:
                    d = json.loads(p.stdout)
                    msg = str(d.get("error") or d.get("result")
                              or f"exit {p.returncode}; stop_reason={d.get('stop_reason')}; usage zeroed")
                except json.JSONDecodeError:
                    msg = p.stdout.strip()
            return RunResult(ok=False, error=(msg or f"claude exit {p.returncode}")[:400])
        try:
            data = json.loads(p.stdout)
        except json.JSONDecodeError:
            return RunResult(ok=True, output=p.stdout.strip(), model=model or "", raw={"unparsed": True})
        usage = _usage_from_event(data)          # same accounting as the streamed path
        model_used = _concrete_model(data.get("model"), data.get("modelUsage"), model)
        return RunResult(ok=not data.get("is_error", False),
                         output=str(data.get("result", "")).strip(),
                         usage=usage, model=model_used,
                         error=str(data.get("error", "")), raw=data)

    def run_stream(self, system: str, prompt: str, model: Optional[str] = None,
                   cwd: Optional[str] = None, allow_tools: bool = False, timeout: int = 600,
                   on_event: Optional[Callable[[dict], None]] = None,
                   on_proc: Optional[Callable] = None, effort: Optional[str] = None,
                   fallback_model: Optional[str] = None,
                   max_budget_usd: Optional[float] = None, disallowed_tools: Optional[list] = None) -> RunResult:
        """Run a turn in streaming mode, calling on_event(dict) for each intermediate step
        (thinking / tool use / tool result / text) as Claude Code emits them (stream-json NDJSON).
        Returns the final RunResult. Falls back to a single 'result' event on any parse gap."""
        def emit(o):
            if on_event:
                try:
                    on_event(o)
                except Exception:  # noqa - a dropped SSE client must not kill the run
                    log.debug('emit: failed; ignored', exc_info=True)
        lp = self._launcher()
        if not lp:
            emit({"kind": "error", "error": "claude binary not found"})
            return RunResult(ok=False, error="claude binary not found")
        # prompt via STDIN (see run(): keeps a long thread off the command line — WinError 206)
        args = ["-p", "--output-format", "stream-json", "--verbose"]
        if model:
            args += ["--model", model]
        if effort:
            args += ["--effort", effort]     # adaptive-reasoning level (see run())
        args += _advanced_args(fallback_model, max_budget_usd)
        sys_args, sys_file = _system_args(system)     # large context travels by file, not argv
        args += sys_args
        if allow_tools:
            # NO --safe-mode: real MCP/skills/plugins load so the agent can actually use its capabilities.
            args += ["--tools", "default", "--dangerously-skip-permissions"]
            if disallowed_tools:     # ARMADA-disabled capabilities blocked at the tool level
                args += ["--disallowedTools"] + [str(t) for t in disallowed_tools if t]
        elif self._direct():
            args += ["--safe-mode", "--tools", ""]     # no-tool turn: lean, no harness
        else:
            args += ["--safe-mode", "--disallowedTools", _DENY, "--permission-prompts", "none"]
        try:
            proc = subprocess.Popen(lp + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=cwd, env=self._env(), text=True,
                                    encoding="utf-8", errors="replace", bufsize=1,
                                    creationflags=_NO_WINDOW)
        except Exception as e:  # noqa
            swallowed(log, 'run_stream: failed; falling back')
            _drop_system_file(sys_file)
            emit({"kind": "error", "error": f"claude failed to launch: {e}"})
            return RunResult(ok=False, error=str(e))
        # feed the prompt on a background thread so a very large prompt can't deadlock against stdout
        def _feed():
            try:
                proc.stdin.write(prompt)
                proc.stdin.close()
            except Exception:  # noqa
                log.debug('_feed: failed; ignored', exc_info=True)
        threading.Thread(target=_feed, daemon=True).start()
        if on_proc:
            try:
                on_proc(proc)                              # let the caller register it (for stop/kill)
            except Exception:  # noqa
                swallowed(log, 'run_stream: failed; ignored')
        texts, out, mdl, ok, err = [], "", model or "", True, ""
        usage = Usage()
        start = time.time()
        try:
            for line in proc.stdout:                       # yields as the CLI writes each event
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = ev.get("type")
                if t == "system" and ev.get("subtype") == "init":
                    emit({"kind": "start"})
                elif t == "assistant":
                    for b in (ev.get("message", {}).get("content") or []):
                        bt = b.get("type")
                        if bt == "thinking":
                            emit({"kind": "thinking", "text": (b.get("thinking") or "").strip()[:4000]})
                        elif bt == "text":
                            txt = b.get("text") or ""
                            if txt.strip():
                                texts.append(txt)
                                emit({"kind": "text", "text": txt})
                        elif bt == "tool_use":
                            emit({"kind": "tool", "name": b.get("name", ""),
                                  "input": b.get("input", {}), "id": b.get("id", "")})
                elif t == "user":
                    for b in (ev.get("message", {}).get("content") or []):
                        if b.get("type") == "tool_result":
                            c = b.get("content")
                            if isinstance(c, list):
                                c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
                            emit({"kind": "tool_result", "id": b.get("tool_use_id", ""),
                                  "content": str(c or "").strip()[:4000],
                                  "is_error": bool(b.get("is_error"))})
                elif t == "result":
                    out = str(ev.get("result", "")).strip()
                    usage = _usage_from_event(ev)
                    ok = not ev.get("is_error", False)
                    mdl = _concrete_model(ev.get("model"), ev.get("modelUsage"), mdl)
                if timeout and time.time() - start > timeout:
                    proc.kill()
                    err = f"timed out after {timeout}s"
                    break
            proc.wait(timeout=10)
        except Exception as e:  # noqa
            swallowed(log, 'run_stream: failed; using a default')
            ok, err = False, str(e)
        finally:
            _drop_system_file(sys_file)       # the CLI has read it by the time the process is done
        if not out:
            out = "\n".join(texts).strip()
        if proc.returncode not in (0, None) and not out:
            ok = False
            err = err or ((proc.stderr.read() if proc.stderr else "").strip() or f"claude exit {proc.returncode}")[:400]
        return RunResult(ok=ok, output=out, error=err, model=mdl, usage=usage)
