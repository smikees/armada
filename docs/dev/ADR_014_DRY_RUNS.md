# ADR 014: Draft jobs and inspector tools

Status: implemented, 2026-10-08. Maintainer chose draft-only behavior with explicit
dry-run commands for scripts.

Dry runs are independent asynchronous invocations with a captured job definition,
an explicit available model, no fallback, no retry series and no production job
thread. Each run is stored in the realm's `.armada/dry-runs/<agent>/<job>/<run>/`
tree. Keeping this operational data inside the realm avoids modifying shared
project output folders and keeps realm lifecycle and run identity consistent.
Seven-day retention is copied into each run; housekeeping skips live owned markers
and deletes the entire validated, expired tree. Token accounting has `kind:dry_run`
and `task:dryrun:<job>` so production job reports/scheduling are unaffected.

## Execution boundary

Redirecting a working directory cannot prevent shell commands or MCP publishing.
Model dry runs therefore expose only ARMADA's invocation-scoped MCP broker:
read existing files in approved input roots, list input files, write UTF-8 drafts
inside the run's output folder. Ambient connectors, shell, hooks, plugins and
network/write tools are excluded by each adapter's managed-turn configuration.
Production job prompts remain intact in the snapshot; the dry-run system context
replaces delivery steps with drafts and records missing inputs. The production
result contract's destinations/output paths are not used for a test. Captured
tool results are saved in the test tree, including their audit/require_capture.

This deliberately uses saved inputs instead of permitting guessed “read-only”
external tool names. An MCP annotation or a name beginning `get_` cannot prove
that an arbitrary connector has no side effects. Live connector replay/proxying
and sandboxed general-purpose script execution are future extensions, not implied
by the model test boundary.

An arbitrary command job is different: only the owner's explicit dry-run command
may execute, fingerprinted with its definition/environment in machine-local
owner configuration. Scripts must honor their declared draft-only behavior.
No operating-system containment or egress restriction is claimed for this trusted
script path. Inspectors cannot register or alter these authorizations.

## Inspectors

Portable `agent.json:is_inspector` expresses intent. Effective authority also
requires the owner-approved machine-local entry, checked on every broker call.
Inspector turns expose only list jobs/models/artifacts, read recorded artifacts,
start/read dry runs and write their own review files. Recorded output paths must
remain inside the producer's realm/workspace/approved job roots. Generic foreign
file reads/writes, production launch/settings endpoints and owner API credentials
are absent. Cross-realm job identities and traversal/reparse points are refused.
The broker has an ephemeral bearer credential, binds only loopback, and exists
only for its parent turn. The stdio MCP bridge has no owner HTTP credential.

Two dry runs per realm and four launches per inspector turn bound concurrent
cost. RunSession owns admission, activity and process cancellation. A durable
stop request also reaches a worker in another ARMADA process. The UI reads saved
run state independently from production output, survives navigation, and retains
the selected historical test while polling. Host writes use atomic utilities.

## Provider evidence

Claude uses subscription authentication with `--setting-sources ""`, disabled
skills/hooks, no built-in tools and strict explicit MCP configuration. `--bare`
cannot reuse subscription login; `--safe-mode` also removes explicit MCP tools,
so neither is used for these turns. See the official
[CLI reference](https://code.claude.com/docs/en/cli-reference) and
[headless documentation](https://code.claude.com/docs/en/headless).
Codex disables shell/exec/web/apps/plugins/hooks, disables ambient MCP servers
through its effective inventory, and uses a read-only sandbox with just the scoped
stdio server. Credentials are inherited through `env_vars`, not config argv.
See the official [configuration reference](https://developers.openai.com/codex/config-reference/).
Gemini uses its custom agent's explicit MCP server, no native file/web/command
tools, and scoped project permissions; the managed server name and input schemas
are included in context because its generic MCP tool otherwise guesses server names.
All three installed CLIs were exercised against synthetic files: each made real
draft tool calls, returned the expected text, refused a production write and left
the production fixture byte-for-byte unchanged. No business job was run.

## Validation

Synthetic tests cover model selection, disabled jobs, production isolation,
atomic writes, paths/Windows aliases, inspector self-authorization/revocation,
artifact reads, command authorization, Stop, retention and stdio transport.
The native Jobs probe covers actual browser control behavior, history/model
selection, navigation recovery, Stop and saving inspector settings.
