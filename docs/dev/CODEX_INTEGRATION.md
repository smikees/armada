# Codex integration and repository orientation

Implemented against Codex CLI 0.158.0-alpha.2.1 on Windows, September 26, 2026.
This follows Mihai's request to let every agent choose models across connected providers,
superseding the earlier Claude-only decision in ADR-001.

## How Armada works

The code checkout is `Development/MATCAP`; its origin is `smikees/armada`. The sibling
`MATCAP-private` holds release/signing resources and an old history bundle, not runtime agents.
The machine's realm registry and last-opened realm live in `~/.armada/`. Agents, jobs, memories,
grants and threads live in the registered realm folders. Keep those separate from app code.

`reader.py` reconstructs the realm from Markdown/JSON. `webui/` renders it; `routes/` handles
actions. `runner.py` assembles agent identity, memories, capability context and conversation,
then calls an adapter in `engine/`. It records turns, artifacts, capability use and usage back
into the realm. `scheduler.py` runs jobs independently of the desktop window. `inbox.py` and
`telegram.py` eventually reach the same runner. Realm updates use file locks and atomic writes.

## Selection and execution

- `engine/selection.py` resolves an explicit CLI override, then the job's model, agent's model,
  realm's model, and finally legacy provider/default-engine fields. Existing Claude labels remain
  valid. OpenAI model IDs and `codex:default` select Codex. No migration of agent files is needed.
- App-wide connections control model choices after the first connection status check; legacy
  realms retain their provider list until then. Disconnecting hides choices and blocks new calls
  without changing saved agent/job models. See [Provider onboarding](PROVIDER_ONBOARDING.md).
- `models.options` combines Claude's catalogue with Codex's local `models_cache.json`. Hidden
  Codex models are omitted. `codex:default` remains available before that cache exists. No network
  request or subprocess runs to render Codex options. Context windows use the same local metadata.
- `engine/codex.py` invokes `codex exec --json` once per turn. It sends the assembled context and
  history through stdin so long Windows prompts cannot exceed argv limits. Armada owns history;
  exec is ephemeral. No Codex session resume IDs are stored in realm files.
- JSONL items become Armada text, thinking, tool and tool-result events. File changes are mapped
  to the existing artifact-capture contract; shell-created files also use the existing filesystem
  scan. Cached input tokens are subtracted from input before being recorded separately.
- Streamed text and activity are checkpointed per turn in the thread directory before being
  emitted. A return visit renders the checkpoint while the turn is active. Completion saves the
  canonical answer and removes the checkpoint; engine errors retain partial text and close the
  turn. Run markers are cleared before title generation and carry the owning server PID so a
  crashed server cannot leave a fresh marker claiming work is still running.
- The scheduler and UI use `auto`; `--engine mock`, `--engine claude` and `--engine codex` remain
  explicit overrides. `armada run` retains its offline mock default for backward compatibility;
  use `--engine auto` for an agent's configured model.

On this development machine the app and scheduler run from the source checkout. The existing
Windows `ARMADA Scheduler` sign-in entry now calls its `SCHEDULER.vbs`; the older Cabinet
resilience launcher also uses `auto`. The installed release has not been rebuilt. The installer
template is updated so future installations also preserve each agent's provider choice.

## Authentication and capabilities

Settings checks both CLI logins asynchronously. Codex uses `codex login status` and its own
browser sign-in through `codex login`, launched without a console. Armada never reads, copies or writes Codex credentials.
The CLI may use a ChatGPT subscription or an API login; any billing follows that CLI login.

Tool turns use Codex's workspace-write sandbox with the agent directory, realm and configured
workspace available for writes, and approval policy `never`. They do not bypass the sandbox.
The effective MCP inventory is read in the turn's working directory; servers absent from the
agent's Armada grants are disabled for the invocation. Inventory failure fails the turn closed.
Codex MCP servers must already be configured in Codex with matching Armada capability IDs.
MCP IDs that need disabling must use letters, numbers, underscores or hyphens (CLI dotted-key
override limitation). Already disabled, desktop-managed servers are left alone.

Launch 2.15 removes memory snapshot restoration for both adapters. Codex's current realm-wide
write root does **not** isolate another agent's memory. Its runner records protected-memory
changes with unknown attribution and preserves current files, including after failure or
cancellation. Claude additionally receives absolute `Edit` denial rules for protected memory
roots. Neither memory boundary contains arbitrary shell/MCP writes. See
[Memory boundaries](MEMORY_BOUNDARIES.md) for coverage, audit records and the limits of the current
adapter versus Codex's optional named permission profiles.

Launch 2.12 adds a strict execution-policy reader for both providers. Missing/unreadable JSON,
duplicate keys, malformed toolkit entries and non-boolean permission flags block tool turns.
Legacy string grant IDs remain valid. Unknown grants confer no access; realm disablement wins.
Permissions are refreshed immediately before the provider call, after context assembly. A
coordinator still receives only enabled catalogue entries, not every server on the machine.
Chat, streaming chat, scheduled jobs and inbox prompts persist admission failures in both their
thread and run report; an inventory failure also produces a failed result rather than a fallback.

Claude tool turns require version 2.1.263 or newer and a direct native/Node launcher. The adapter
reads `mcp list` in the agent directory, rejects unrecognized output, and passes per-invocation
`deniedMcpServers` settings plus tool denials for every ungranted server. Empty grants also deny
`mcp__*`. Server commands, URLs and credentials are not copied into the realm or error reports.
Reference: [Claude MCP policy](https://code.claude.com/docs/en/managed-mcp) and
[tool denials](https://code.claude.com/docs/en/permissions#tool-name-wildcards).
The installed CLI was checked without a model call: three configured servers became zero under
the empty-grant settings. Policy is applied at each invocation; changing a grant does not cancel
an already-running process. These controls gate MCP tools, not arbitrary shell/network access
or changes made by another process to the provider configuration during launch.

Codex apps, plugins, hooks, computer/browser control and automatic subagents are disabled for
these turns because they have no Armada grant mapping. Claude plugin installations and Claude
MCP configuration are not automatically copied. Existing skill files remain plain files the
agent can read when granted; native skill visibility is advisory, as on the Claude adapter.

No-tool helper turns disable shell execution, image tools, web search and all MCP servers and
run in an empty temporary directory under the read-only sandbox. Operations requiring an exact
sealed tool allowlist fail explicitly on Codex. As of September 28, setup supports either or both
providers and Alexander uses the shared no-tool execution contract. Automatic Alexander selects
Opus 5.5/Medium with Claude connected, otherwise GPT-6 Sol/Medium; App → Advanced overrides this.

Codex has no equivalent of Claude's hard dollar budget: a configured budget is rejected rather
than silently ignored. Codex automatic fallback and cross-provider fallback settings are rejected
explicitly. Codex API-equivalent cost is unavailable (stored as JSON null); actual token counts
are recorded. See [execution contracts](EXECUTION_CONTRACTS.md).

Armada's four writing-style levels are always expressed in the agent prompt. For an explicit
GPT model, the Codex adapter also sets `model_verbosity` per invocation: Terse/Brief → low,
Standard → medium, Detailed → high. A `codex:default` or unfamiliar model keeps its own
native preset, while the prompt-level preference still applies. This setting controls reply
length; effort controls reasoning work and can consume substantially more reasoning tokens.
The model marks and configuration gauge use a provider-local, log-scaled *estimate* based on
published API model tiers and judgmental effort/verbosity multipliers. They are not actual
token counts, subscription charges, or quotas. The current Astra/Sol/Luna weights are based
on OpenAI's September 2026 standard API list prices; legacy Terra and 5.5 weights are
estimates. The two providers share gradient colors but keep separate ranges so adding Codex
does not silently recolor existing Claude badges.

`codex_usage.py` reads account-wide quota through the authenticated CLI app-server's documented
`account/rateLimits/read` request. It starts no model turn and does not read credentials. Requests
have a deadline and one-minute shared cache. The Overview header shows Codex on the left and
Claude on the right under Subscription limits, with an icon above each group's Week and Session
rows in the existing 62px space.
Windows are matched by duration, since primary can be weekly; multi-bucket responses keep their
bucket selector. Missing or stale readings use gray bars without percentage/reset text, with the reason and last
reading available on hover. Reference: [app-server](https://developers.openai.com/codex/app-server/).
Each period label aligns with its bar; provider icons retain accessible names.
Claude sign-out uses a dismissible floating notice, shown once per server session. The auth-status
response carries a random session ID, and the browser remembers which session it has already shown.
Polling, navigation and realm switches do not repeat it; sign-in stays available in Settings.

## Verification

Inbox dispatch and both Telegram paths use [recipient-provider admission](PROVIDER_UPKEEP.md).
Codex recipients continue when Claude is signed out; unavailable inbox recipients retain pending
tasks. Claude usage keepalive alone declares a fixed Claude authentication requirement.

Both providers now use the shared [CLI turn lifecycle](PROCESS_LIFECYCLE.md) for model turns.
Cancellation owns the ordinary child-process tree; successful output requires a terminal provider
event and zero exit. Errors and stopped turns preserve partial output in the conversation.

`tests/test_codex_engine.py` covers provider precedence, mixed catalogues, MCP gating, stream
normalization, cached-token accounting, long Unicode prompts, stderr draining, silent timeouts,
failed compaction preserving history, and agent/job routing through the runner.

`python tools/smoke_codex.py` is an opt-in live check using real Codex tokens. It creates an isolated
realm under the checkout, injects a verification word in the agent's soul, asks the agent to write
one artifact, and records the streamed turn and usage with notifications muted. Its directory
inherits normal workspace permissions, like a real realm, so both the owner and Windows Codex
sandbox account can access the artifact. It never reads or changes the live agents.

Protocol references: [non-interactive mode](https://developers.openai.com/codex/noninteractive/)
and [configuration](https://developers.openai.com/codex/config-reference/), plus the installed
CLI's `exec --help`, `features list`, `login --help` and local model catalogue.
# Live MCP startup and OAuth reuse

Armada uses the same gated Codex app-server path for agent jobs and thread turns.
After `thread/start`, it awaits `mcpServerStatus/list` for each granted configured
server before starting the model turn. This verifies callable tools and records exact
startup/authentication failures. Stored `mcp list` OAuth metadata alone is not proof
of an active connection. Capabilities performs the same live check asynchronously;
page rendering stays independent of network probes.

Armada enables Codex's `mcp_oauth_refresh_coordination` and serializes connector
startup across its app, scheduler and status probes with a machine-local kernel lock.
The lock is released before model work; a crashed process releases ownership. OAuth
remains in Codex's credential store. No realm carries a credential copy. Genuine
provider revocation/rejected refresh tokens require sign-in; ordinary expiry should
use refresh rather than ask users to authorize every turn.

Startup evidence accompanies the individual run. Failed connector initialization
is visible separately from the original answer and does not by itself turn a
completed qualified report into a failed execution. Direct shell HTTP remains
subject to separately approved network grants; MCP broker transport is not dependent
on granting general network access to an agent's shell.
