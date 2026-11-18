# Thread work timing, copy controls and live input

18 November 2026, v0.99.162. Agent conversations share these behaviors in the main
view, widgets and detached windows.

Work admission writes `work_started_at` on the original user record after capacity
admission. Completion writes `duration_s` from a monotonic clock on its assistant
record. Queued time is excluded. Repeated starts preserve the original timestamp;
legacy records stay valid and do not acquire guessed durations. Browser clocks
update locally; they do not write every second or change snapshot revisions.

Thread navigation opens at the newest message. Global page-state restoration
ignores stored transcript scroll positions, including older saved entries. While
the page stays open, canonical transcript updates retain a reader's position.
The circular down-arrow above the composer appears when the reader leaves the
bottom. Code blocks get a copy button; existing turn copy controls copy complete
responses. Clipboard success is awaited, with a selection-preserving fallback and
an explicit error if neither method works. Copying uses text, not rendered HTML.

## Provider research and implementation

Codex keeps its existing native `turn/steer` transport, bound to the exact active
thread and expected turn. It appends input without a new owner run or permission
overrides. See [OpenAI's app-server reference](https://learn.chatgpt.com/docs/app-server).

Claude supports streaming user input while a session runs. Armada sends native
user messages with `priority: now` and a human origin, letting Claude Code decide
whether to background tools or interrupt and continue. The CLI must be at least
2.1.286. Transport replays do not prove incorporation: receipts wait for a reply
frame naming the submitted UUID. Intermediate results do not end the owner run
while input remains unanswered. Native idle handles messages dropped by hooks.
See [streaming input](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode),
[message priority and UUID semantics](https://code.claude.com/docs/en/agent-sdk/typescript#sdkusermessage),
and [CLI replay acknowledgement](https://code.claude.com/docs/en/cli-reference).

Antigravity print-mode stdin documents sequential turns; its newer ACP interface
explicitly documents steering by another `session/prompt` during a running turn.
Owner conversations on CLI 1.5.0+ use that interface when its grants can be preserved.
Background work and older versions retain print mode. Configurations with per-tool
connector filters or partial native-write denials also retain print mode: ACP cannot
express those filters. A direct adapter without an authenticated agent context
retains print mode if native writes would be needed.

ACP receives the selected connectors through native session setup. It does not
honor the project write fence, as a synthetic outside-write test demonstrated.
Armada therefore removes native write tools and supplies its invocation-local
PolicyTools writer, checking approved roots, current owner policy and Stop on each
call. Writes feed the normal output record. Read permissions remain unchanged.
Host filesystem/terminal RPCs are disabled. Permission requests authorize only
one call to an explicitly selected MCP server, never native writes, unknown
servers or permanent grants. The existing checked brokers enforce their own
per-call restrictions. No extra owner grant is created. Model selection
uses the native session configuration. Native completion and usage fields feed
the existing result/accounting path. See [Google's ACP guide](https://antigravity.google/docs/ide/extensions/acp),
[print-mode input](https://antigravity.google/docs/cli/headless/), and
[ACP prompt lifecycle](https://agentclientprotocol.com/protocol/v1/prompt-turn).

The original realm-bound steering admission, durable receipts, request deduplication,
limits, Stop and no-replay rules apply to every provider. No message is redirected
to another provider, a later Armada run, or a session with changed permissions.
Native providers decide their own turn-boundary behavior; transport acceptance
does not promise that an instruction has already been carried out.

## Evidence

Synthetic subprocess tests cover delivery, terminal ordering, permission refusals,
exact session identity, accounting and unavailable runtimes. Native main/detached
checks cover clocks, saved totals, copying, latest-message entry, jumping down,
reading position, shared receipts, questions, Stop and drafts.

Native Claude Code 2.1.319 protocol experiments incorporated the synthetic follow-up.
A later production-adapter retest encountered the account's five-hour limit and
correctly retained an uncertain receipt. Antigravity CLI 1.5.11 passed both its
protocol experiment and the production-adapter follow-up test with token usage.
The native selected-connector echo and guarded-writer checks passed: an approved
write succeeded, an outside write was refused and audited, and no forbidden file
was created. Synthetic tests cover Stop expiry and policy changes during a run.
These are harmless temporary tasks; no business data or provider credentials
are present in the committed evidence. See the release record for final gates.
