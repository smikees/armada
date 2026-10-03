# Agent execution contracts

`runner.chat`, `chat_stream`, `run_job` and `run_job_prompt` remain compatibility entry points.
They route model turns into `execution.TurnCoordinator`. Inbox delivery and Telegram reuse those
entry points. Deterministic command jobs retain their subprocess path; they do not create a model
conversation or inherit provider requirements. System upkeep retains its separate
[result contract](PROVIDER_UPKEEP.md).

## Ownership

`TurnRequest` binds a turn to its frozen `RunContext` (realm identity, agent, thread and run ID).
`RunSession` owns registry admission, process registration, early cancellation, activity markers
and cleanup. HTTP shares that session for SSE; it transports events and optionally names a new
thread after completion, without mutating the conversation through private rendering helpers.
Plain chat and scheduled/delegated model turns acquire their own session.

Context construction and artifact-capture helpers still live in `runner` for compatibility.
The coordinator calls those helpers, but lifecycle decisions live only in `execution`.
The outer scheduled-job wrapper retains job notifications and its job activity indicator;
the coordinator owns the model turn's session and conversation records.

The coordinator validates provider requirements before any compaction model call, assembles
context, starts the durable user turn, captures progress/artifacts, and saves one terminal reply.
Successful empty output gets an explicit completion message. Failed and stopped turns preserve
partial output. Capture cleanup runs after provider exceptions; session cleanup runs even when
persistence fails. A disconnected observer cannot interrupt terminal persistence. Disk errors can
still prevent a record from being saved; unavailable storage cannot offer a persistence guarantee.

Progress checkpoints remain outside conversation history. Transcript and usage report share
run/realm identity. Metadata writes use `thread_metadata`; renderer wrappers remain for older
callers. Broader web UI namespace removal remains D.8.

## Provider boundary

`engine.contracts.RunRequest` is immutable and carries prompt/context, model, timeout, effort,
budget, fallback and tool requirements. `RunEvent` defines normalized events; `CancellationHandle`
describes process registration without exposing `Popen`. `RunResult` and `Usage` are the result
and accounting records.

Adapters declare `ProviderCapabilities`. `EngineAdapter.execute` validates requests and selects
streaming or nonstreaming execution; the coordinator does not discover methods with `hasattr`.
`ExecutionPolicy` binds MCP grants and writable roots to an adapter copy, preventing concurrent
turns from changing shared permissions. Grants are refreshed after context assembly.

| Requirement | Claude | Codex |
|---|---|---|
| Streaming and owned cancellation | Supported | Supported |
| Hard dollar budget | Supported | Explicit rejection |
| Same-provider fallback | Supported | Explicit rejection |
| Cross-provider fallback | Explicit rejection | Explicit rejection |
| Sealed built-in allowlist | Supported | Explicit rejection |
| MCP server restrictions | Supported | Supported |
| Individual tool restrictions | Claude denial syntax | Explicit rejection |

Direct `run`/`run_stream` compatibility calls also reject unsupported settings. Older injected
adapters are accommodated only in `execute_request`: result-shaped objects become `RunResult`,
and optional requirements need declared capabilities. This is a compatibility boundary, not a
second coordinator.

## Accounting

Missing input/output counts and API-equivalent cost are `None`, serialized as JSON `null`.
An observed numeric zero stays zero. Codex supplies tokens but no API-equivalent dollar cost.
Missing cost makes the aggregate cost unavailable instead of presenting an incomplete subtotal
as complete. Existing numeric records remain readable without migration; historical fabricated
zeros cannot be distinguished from observed zeros and are not rewritten. Subscription limits
remain a separate account-wide measurement.

Charts sum reported token counts and expose `unknown_runs` for the selected window. When that
count is nonzero, the UI labels the sum as reported tokens and identifies missing runs; the
30-day total stays unavailable. A run without accounting is not a zero-usage run.

## Verification

`tests/test_execution_contracts.py` applies the same lifecycle matrix to Claude and Codex across
plain chat, streaming, jobs and delegated prompts. It also checks unsupported settings before
launch/compaction, isolated policy binding, partial/empty output, observer/capture failures,
cancellation, accounting and route boundaries. `test_process_lifecycle.py` retains real-process
checks of deadlines and process-tree cleanup.
