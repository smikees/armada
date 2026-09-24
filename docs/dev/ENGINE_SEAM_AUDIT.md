# Engine seam audit — what a second engine would cost

*Phase 2, step 2.6 — ADR-001's homework. Written 2026-09-24 against v0.99.39.*

ADR-001 decided Claude is the only engine for v1 and asked for one thing before launch: a list of
every place the code assumes Claude rather than "an engine", so that the cost of a second one is a
priced list instead of a guess. This is that list. **Nothing here has been fixed**; where a finding
suggests a cheap way to keep the bill from growing, that is marked as guidance for new code, not
as work done.

References are `file.py:function` rather than line numbers, so they survive edits.

---

## The verdict in one paragraph

The seam itself is sound but narrow: `engine/base.py:EngineAdapter` (`doctor`, `run`,
`run_stream`) with `RunResult` and `Usage`, and `engine/__init__.py:get_engine` as the only factory.
Behind it, `engine/claude.py` keeps its CLI plumbing to itself — launcher resolution, argv limits,
the JSON and stream-JSON parsing, `modelUsage` accounting — and normalises the stream into
engine-neutral event kinds. The trouble is everything *around* the seam. **Engine choice is never
actually made** (every call site hard-codes `"claude"`; the realm's `provider` setting is
display-only), **five modules call the Claude CLI directly**, and the words the rest of the app
thinks in — tool names, MCP server ids, SKILL.md skills, plugins, effort levels, cache counters,
model families, the 5-hour/7-day limit windows — are Claude Code's. The seam carries the *turn*;
it doesn't carry the *vocabulary*.

**Rough bill for a second engine that speaks MCP** (the realistic case — OpenAI's Codex CLI is the
one named in the plan): **5–7 weeks** of Sonnet-class work under the suite, of which the capability
model is about half. An engine without MCP would lose connectors and extensions outright; that
isn't a cost, it's a product decision.

| # | Area | Kind | Size | Blocks a 2nd engine? |
|---|---|---|---|---|
| A | Engine selection is not wired | seam gap | S | yes — nothing can pick it |
| B | Direct Claude CLI calls outside the seam | seam bypass | M | partly |
| C | Run-call parameters are Claude-shaped | contract | M | yes |
| D | Stream/tool vocabulary is Claude Code's | contract | M | yes (silently) |
| E | Usage accounting is Anthropic's four counters | data model | S–M | no — degrades |
| F | Subscription limits (5h / 7d) | feature | M | no — hides |
| G | Model catalogue, ids, windows, prices | data + UI | M–L | yes |
| H | Capability model (MCP, skills, plugins) | domain | **L** | yes |
| I | Sign-in and onboarding | feature | S–M | yes |
| J | Prompt assembly assumptions | behaviour | S | no |
| K | Tests encode Claude's contract | tests | S–M | no |

Sizes: **S** ≤ 1 day · **M** 2–5 days · **L** 2+ weeks.

---

## A. Engine selection is not wired — S

The realm stores an engine choice three ways, and none of them reaches a run:

- `realm.json` → `default_engine` (written by `setup.py:scaffold`), `provider`, and a newer
  multi-select `providers` (written by `routes/realm.py:_save_realm_settings`, rendered as
  "AI providers" in `webui/pages.py:render_settings`).
- `reader.py:read_native` turns `default_engine` into the *display* string
  `"Claude (subscription)"`; nothing else reads any of the three.

Every place that actually runs a turn picks its engine by literal:

- `routes/agents.py:_chat_stream` → `engine="claude"` (every chat turn in the app).
- `scheduler.py:tick` / `run_daemon` default `engine="claude"`, fed by `cli.py`'s
  `--engine` default `"claude"` (every scheduled job). `SCHEDULER.vbs` passes `--engine claude`.
- `runner.py:run_job_prompt`, `run_inbox`, `process_message_now`, `dispatch_inboxes` default
  `"claude"` (agent-to-agent work).
- `telegram.py:handle` / `dispatch` / `listen` / `start_listener` default `"claude"`.
- `catalogue/realm.py:review_url` default `"claude"` (bring-a-link review).
- `preflight.py:engine_check` / `run` / `apply_hold`, `doctor.py:run` default `"claude"`;
  `routes/settings.py` calls `get_engine("claude").doctor()` for the Settings engine panel.
- `routes/jobs.py:_run` takes `engine` from the request body (default `"mock"`) — the one call
  site where the engine is a parameter, and it's the Run-a-job button.

**What a second engine needs:** one resolver — `engine_for(realm_root, agent)` reading agent →
realm → default — and every literal above replaced with it. Mechanical. Decide first whether the
unit is the realm (simple) or the agent (a realm with a Claude coordinator and a Codex minister),
because the agent case pulls in G (per-agent model lists) and H (per-agent capability transport).

*Guidance for new code now:* take `engine` as a parameter and pass it down; don't add another
`"claude"` literal.

## B. Direct Claude CLI calls outside the seam — M

Five modules import `ClaudeEngine` (or its launcher) directly instead of going through
`get_engine`. Each is doing something the `EngineAdapter` contract has no word for:

| Where | What it does | Why it's outside the seam |
|---|---|---|
| `routes/_shared.py:_llm_title` | titles a new thread with `ClaudeEngine().run(model="haiku")` | wants "a small cheap model" — no such concept in the contract |
| `auth.py` (`_status_live`, `start_login`) | `claude auth status --json`, `claude auth login` in a console | sign-in isn't part of the contract (`doctor()` only reports) |
| `capscan.py` (`list_plugins`, `list_mcp`, `update`) | `claude plugin list/update`, `claude mcp list` | capability inventory isn't part of the contract (see H) |
| `sysjobs.py:_job_usage_keepalive` | `claude -p "Reply with exactly: ok" --max-turns 1` to make Claude Code refresh its own OAuth token | exists only because of how Claude Code's token refresh works (see F) |
| `sysjobs.py:_expiry` | reads `~/.claude/.credentials.json` → `claudeAiOauth.expiresAt` | same |

`threads.py:Thread.compact_if_needed` is the counter-example: it takes the engine as a parameter.

**What a second engine needs:** extend the contract rather than special-case each caller —
`EngineAdapter.cheap_model()` for titles, `EngineAdapter.auth_status()` / `start_login()` for
sign-in (the Settings panel and the Phase 6 wizard both want it), and move capability inventory
behind an optional `EngineAdapter.capabilities()` (H). The keepalive and expiry read are
Claude-only upkeep and should become the Claude adapter's business (an optional
`maintenance()` hook the system jobs call per engine).

*Guidance for new code now:* the wizard (Phase 6) will want sign-in; add it to the contract then
rather than as a sixth direct import.

## C. Run-call parameters are Claude-shaped — M

`EngineAdapter.run` / `run_stream` take `effort`, `fallback_model`, `max_budget_usd`,
`disallowed_tools`, `allow_tools` and `cwd`. The *signature* is generic; the *values* are Claude
Code's:

- **effort** — `low | medium | high | xhigh | max` (`runner.py:_EFFORT_LEVELS`,
  `webui/agentcommon.py:_EFFORTS`, `models.py:_EFFORT_MULT`), passed as `--effort`; the docstring
  on `runner.py:_resolve_effort` says outright that effort *is* the thinking level "in current
  Claude models". Another engine's reasoning knob (if it has one) has different steps.
  *Aside, found along the way and not engine-related:* the UI's `_EFFORTS` offers four levels and
  the runner accepts five (`xhigh` is missing from the dropdown).
- **fallback_model / max_budget_usd** — map 1:1 to `--fallback-model` / `--max-budget-usd`
  (`engine/claude.py:_advanced_args`); the base class already says adapters that can't honour
  them may ignore them, which is the right contract.
- **disallowed_tools** — built by `runner.py:_disallowed_tools` as Claude Code tool names plus
  `mcp__<id>` patterns; this is how capability grants are *enforced* (see H). Meaningless to an
  engine with different tool names.
- **allow_tools** — means "load Claude Code's full harness (MCP servers, skills, plugins)" versus
  `--safe-mode --tools ""`. `verbosity.py`'s design (and its docstring) depends on knowing that
  `--safe-mode` disables Claude Code output styles.

**What a second engine needs:** keep the signature; move the *vocabularies* into the adapter —
`adapter.effort_levels()`, `adapter.deny_patterns(capabilities)` — so `runner.py` asks rather than
builds.

## D. Stream and tool vocabulary is Claude Code's — M

`engine/claude.py:ClaudeEngine.run_stream` does the right thing structurally: it normalises the
CLI's stream-JSON into `{"kind": start | thinking | text | tool | tool_result | error | …}`. But
the payload of a `tool` event is Claude Code's tool call verbatim, and several consumers key on it:

- `runner.py:_OUT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}` and
  `_TurnCapture.on_event` reading `file_path` / `notebook_path` — this is how a turn's
  **artefacts** are found *and* how the **publish boundary** (writes outside the realm's shared
  folder) is detected. With another engine's names these silently stop matching: no artefacts
  recorded, no boundary warnings, no error.
- `runner.py:_WEB_TOOLS` (`websearch`, `webfetch` — "Claude's built-in web research"),
  `_match_capabilities` and `_record_used_capabilities` parsing `mcp__<server>__<tool>` — how the
  thread's "capabilities used" rail and auto-discovery of connectors work (the latter writes
  `"scope": "MCP server (Claude)"` into the realm).
- `webui/static/js/chat.js:mcToolLabel` — human labels for `WebFetch`, `Glob`, `Grep`, `Task`, …
- Thread history (`agents/<id>/threads/*/messages.jsonl`) stores these events as-is, so
  existing realms carry Claude tool names in their data — a second engine's renderer has to keep
  reading them.

**What a second engine needs:** a small neutral tool taxonomy the adapter maps into
(`write_file{path}`, `web_fetch{url}`, `mcp{server, tool}`, `other{name}`) alongside the raw name,
so `runner.py` and `chat.js` key on the taxonomy. This is the finding most likely to fail
*quietly*, so it should be first in any second-engine work after A.

## E. Usage accounting is Anthropic's four counters — S–M

`engine/base.py:Usage` is `input / output / cache_read / cache_write / cost_usd` — exactly
Anthropic's accounting, including the cache-*creation* counter whose absence once made a
2,954-token turn report 6. `api_equiv_usd` is the CLI's own `total_cost_usd`. Downstream:

- run reports (`runs/<id>.jsonl` → `tokens`), the Usage widget, the Overview KPIs (Tokens,
  API-eq), `reader.py`'s 30-day totals, the "subscription quota — not a $ charge" wording.
- `models.py:_PRICES` keyed by Claude family (`haiku/sonnet/opus/fable`) and `_EFFORT_MULT`,
  which drive the model-icon consumption gradient.
- `webui/consumption.py:_MODEL_CLR` / `_MODEL_FAMILY_BASE` — colours per Claude family, with an
  "Unknown" fallback.

A second engine's usage fits the shape badly but not fatally (no cache-write counter → 0; its own
cost figure or none). Run records already carry an `engine` field (chat usage entries and job
run reports both write it in `runner.py`); nothing reads it yet. **What it needs:** consumers that
group by it, per-engine price tables, and a UI that doesn't sum two engines' "API-equivalent"
dollars as if they meant the same thing.

## F. Subscription limits — M

`usage_api.py` reads Claude Code's OAuth token from `~/.claude/.credentials.json` and calls
Anthropic's *undocumented* usage endpoint on `api.anthropic.com` with an `anthropic-beta` header
to show the 5-hour session and 7-day weekly utilisation. It caches the last reading per realm.
The `usage-keepalive` system job and `sysjobs.py:_expiry` exist solely to keep that token fresh
(B). The whole header limits widget, `/api/usage-limits`, and `webui/static/js/usage.js` assume
this one plan model.

**What a second engine needs:** nothing, to *run* — this degrades to "no limits shown". To show
limits, a per-engine `limits()` provider returning a list of named windows rather than the fixed
session/weekly pair. Worth keeping out of the contract until a second engine actually has such an
endpoint.

## G. Model catalogue, ids, context windows, prices — M–L

- `models.py` fetches `api.anthropic.com/v1/models` with the Claude Code OAuth token, an
  `anthropic-version` header and a `claude-code/…` user agent; `_SEED` is a list of Claude model
  ids; the cache is `<realm>/.armada/models.json`, one list per realm, not per engine.
- `runner.py:_cli_model` maps display labels ("Claude Opus 4.8") to CLI ids or the family aliases
  `opus / sonnet / haiku`; `_resolve_model` / `_resolve_fallback_model` go through it.
- `model.py:context_window_tokens` — "fable" or "sonnet 5" → 1M, everything else → 200K — drives
  thread compaction (`compaction_threshold_chars`).
- Realm/agent config stores models as Claude display labels (`default_model: "Claude Opus 4.8"`);
  UI chips and marks (`webui/agentbits.py:_pretty_model`, `_model_mark`, `_model_chip`) and the
  consumption colours (E) are family-based.

**What a second engine needs:** namespaced model ids (`engine:model`) in config, a catalogue per
engine behind the adapter (`adapter.models()`), context windows from the catalogue instead of a
string match, and a migration for existing realms' bare labels — which is exactly what 2.8's
`realmformat` step registry now exists for.

## H. The capability model — L (the long pole)

ARMADA's four capability kinds are Claude Code's four extension mechanisms, and the app's
enforcement story depends on one of them:

- **Kinds.** `capabilities.py:KINDS = (connectors, extensions, skills, plugins)`;
  `MCP_KINDS = (connectors, extensions, plugins)`.
- **Enforcement.** Ungranted MCP-backed capabilities are withheld by denying their `mcp__<id>`
  tools at the engine (`runner.py:_disallowed_tools` → `--disallowedTools`). The module
  docstring of `capabilities.py` is candid that skills and plugins have no per-call handle, so
  their grants are advisory. On an engine without MCP-style tool naming there is *no* enforcement
  at all.
- **Discovery and inventory.** `capscan.py` (`claude plugin list`, `claude mcp list`,
  `claude plugin update`); `routes/caps.py:_read_claude_mcp` reading `~/.claude.json` (global and
  per-project `mcpServers`) and `.mcp.json`; `runner.py:_record_used_capabilities` auto-listing
  MCP servers seen in a turn.
- **Catalogue sources** (`catalogue/sources.py`): Claude Code plugin marketplaces read from their
  clones under `~/.claude/plugins/marketplaces`; `anthropics/skills`; the MCP registry (the one
  engine-neutral source); "your own" skills as `SKILL.md` folders.
- **Skills** are `SKILL.md` folders Claude Code loads; `sysskills.py` bundles ARMADA's own
  (capability-review, skill-registry) in that format, and the capability-review skill tells the
  reviewing agent that `~/.claude.json → mcpServers` is ground truth.
- **Plugins** are Claude Code plugins, full stop.

**What a second engine needs, if it speaks MCP:** connectors and extensions carry over — but
ARMADA must *write* that engine's MCP config (it only reads Claude's today), and grant enforcement
needs that engine's equivalent of a tool deny-list (C). Skills need a decision: inject `SKILL.md`
bodies into the system prompt for engines that don't load them (cheap, loses lazy loading), or
don't offer skills there. Plugins don't exist elsewhere; the catalogue's Claude-marketplace
source becomes per-engine. The capability-review protocol (Phase 1's core feature) is
engine-agnostic prose and survives.

**If it doesn't speak MCP:** connectors and extensions are unavailable on that engine, and the
Capabilities page must say so per agent. That's a product decision for D.2, not an estimate.

*Guidance for new code now:* keep "is this MCP-backed" asked through `capabilities.MCP_KINDS`
rather than re-deriving it, and keep new capability kinds out until this is decided.

## I. Sign-in and onboarding — S–M

- `auth.py` — detect lapsed sign-in and start `claude auth login` in its own console; ARMADA
  never sees a credential. Surfaced in the header when auth lapses.
- Settings → App → Engine panel: `Anthropic — Claude` (live `doctor()`), `OpenAI — Codex`
  hard-coded "Coming soon" (`webui/pages.py:render_settings`).
- ADR-001's consequence for the Phase 6 wizard: check for the Claude CLI and a subscription and
  say plainly ARMADA needs Claude.

**What a second engine needs:** the contract additions in B, the Settings panel driven from
`engines()` instead of literals, and the wizard's engine step. The credential-boundary principle
(never touch another app's credentials) must carry over.

## J. Prompt assembly — S

ARMADA builds the *whole* system prompt itself (`--system-prompt`, not `--append-system-prompt`),
which is what makes the context portable: covenant, soul, mandate, tenets, memories, the tool
preamble (`runner.py:_tool_preamble`) are plain text any engine can take. Claude-specific
residue:

- Large system prompts move to a temp file (`engine/claude.py:_system_args`,
  `_SYSTEM_ARGV_MAX`, `--system-prompt-file`) because of Windows' argv limit — adapter-local,
  correct place.
- Prompt caching: nothing in the code depends on it — no cache-control markers, no ordering
  rule enforced for cache hits. Another engine would change cost, not behaviour.
- `verbosity.py` — see C; relies on ARMADA owning the system prompt, which is engine-neutral.

## K. Tests — S–M

`engine/mock.py:MockEngine` mirrors the Claude contract (same run signature, same `Usage`
fields). Tests that exercise capture, publish boundary, capability usage and chat rendering feed
Claude tool names (`Write`, `mcp__…`). A second engine adds a contract test that runs both
adapters' normalised events through the same consumers — the natural home for D's taxonomy.

---

## Order of work, when D.2 comes

1. **A** — the resolver. Nothing else can be exercised without it.
2. **D** — the tool taxonomy, because its failures are silent.
3. **C** and **B** — move the vocabularies and the stray CLI calls behind the adapter.
4. **G** — per-engine catalogue and namespaced model ids, with a `realmformat` migration.
5. **H** — the capability transport per engine; the product call on non-MCP engines.
6. **E**, **I**, **F**, **K** — accounting, onboarding, limits and contract tests.

Until then, the three rules for new code from this audit: pass `engine` down instead of writing
`"claude"`; don't import `engine.claude` outside `engine/` (five modules already do — don't make
it six); and don't add another consumer of raw Claude tool names outside `runner.py`'s capture.
