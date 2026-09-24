# `armada/engine/claude.py`

Claude engine adapter — drives Claude Code in headless/print mode on the user's
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

### `_drop_system_file(path: str)`

—

### `_system_args(system: str)`

(args, path_to_clean_up) for one system prompt.

### `_advanced_args(fallback_model: Optional[str], max_budget_usd: Optional[float])`

Optional per-run guardrail flags (verified present in Claude Code 2.1.x --help): --fallback-model <m> switch model if the primary is overloaded/unavailable --max-budget-usd <n> hard spend ceiling for the run (only honoured with --print, which we use) Empty/None values contribute nothing, so a run without them behaves exactly as before.

### `_mu_tokens(v)`

Total tokens recorded for one modelUsage entry (handles the CLI's camel/snake key spellings).

### `_usage_from_event(ev: dict)`

Total tokens for a run, preferring `modelUsage` over the `usage` block.

### `_concrete_model(reported, model_usage, fallback: str='')`

Concrete versioned model id for logging (so usage shows 'Opus 4.8', not bare 'Opus'). The CLI's `model` field is sometimes just the family alias we passed ('opus'); `modelUsage` is keyed by the real versioned ids. Claude Code may ALSO use a small background model (e.g. Haiku for titles), so pick the modelUsage entry that did the most work — not just the first key — to get the real model.

### class `ClaudeEngine`

—

- `ClaudeEngine.__init__(self, binary: str='claude')` — —
- `ClaudeEngine._direct_launcher(self, exe: str)` — Resolve Claude Code's real entry, preferring a JS/CJS entry run via `node`.
- `ClaudeEngine._launcher(self)` — —
- `ClaudeEngine._direct(self)` — True when we invoke Claude directly (native or node) — empty-string args survive. False only for the cmd-shim fallback, which eats empty args.
- `ClaudeEngine._env(self)` — —
- `ClaudeEngine.doctor(self)` — —
- `ClaudeEngine.run(self, system: str, prompt: str, model: Optional[str]=None, cwd: Optional[str]=None, allow_tools: bool=False, timeout: int=DEFAULT_TIMEOUT, effort: Optional[str]=None, fallback_model: Optional[str]=None, max_budget_usd: Optional[float]=None, disallowed_tools: Optional[list]=None)` — —
- `ClaudeEngine.run_stream(self, system: str, prompt: str, model: Optional[str]=None, cwd: Optional[str]=None, allow_tools: bool=False, timeout: int=600, on_event: Optional[Callable[[dict], None]]=None, on_proc: Optional[Callable]=None, effort: Optional[str]=None, fallback_model: Optional[str]=None, max_budget_usd: Optional[float]=None, disallowed_tools: Optional[list]=None)` — Run a turn in streaming mode, calling on_event(dict) for each intermediate step (thinking / tool use / tool result / text) as Claude Code emits them (stream-json NDJSON). Returns the final RunResult. Falls back to a single 'result' event on any parse gap.
