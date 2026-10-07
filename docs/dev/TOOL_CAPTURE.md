# Tool capture verification

Verified 2026-10-07 against installed CLIs, using a synthetic local MCP server.

| CLI | Version | Observed completion |
|---|---|---|
| Claude Code | 2.1.289 | `user.message.content[].tool_result` and sibling `tool_use_result` |
| Codex exec | 0.162.0-alpha.2 | `item.completed` / `mcp_tool_call`; `result.structured_content` |
| Codex app-server | 0.162.0-alpha.2 | `item/completed` / `mcpToolCall`; `result.structuredContent` |
| Antigravity | 1.2.16 | `step_update.tool_info.output`; `call_mcp_tool` parameters `ServerName`, `ToolName`, `Arguments`; `DONE` and `ERROR` states |

Primary references checked:
[Claude CLI](https://code.claude.com/docs/en/cli-reference),
[Claude headless stream](https://code.claude.com/docs/en/headless),
[Codex noninteractive JSON](https://developers.openai.com/codex/noninteractive),
[Codex app-server items](https://developers.openai.com/codex/app-server),
[Antigravity headless tool stream](https://antigravity.google/docs/cli/headless).

The fixture returns three read tools with text and structured data. Claude selects
its structured result and exposes a different text representation; Antigravity
exposes the text and omits the original structured object. The capture boundary
is the CLI response received by ARMADA, not the earlier MCP wire response.

`tests/fixtures/tool_capture` contains only observed synthetic tool events.
`SourceEvent` retains the original JSON line; extraction slices its JSON value
literally and decodes only string wrappers. The coordinator captures before UI
formatting and removes the raw source from observers and prompt history.

`tools/verify_tool_capture.py` is an opt-in live check using the selected provider's
saved sign-in and quota. It launches only the synthetic server, requests its three
reads and a later same-run file check, and saves streams and verification evidence
in the chosen output directory. It does not edit connector settings or use a broker.

```powershell
.venv-codex\Scripts\python tools/verify_tool_capture.py --engine claude --output D:\Work\tmp\capture-verification
```

Other engine values: `codex-app`, `codex-exec` and `gemini`. Claude runs a later
native shell script which reads `ARMADA_RAW_DIR` and verifies all three hashes.
The Codex native shell probe hit the host's Windows sandbox startup error
(`helper_unknown_error: setup refresh had errors`). Codex's verifier therefore
uses a fourth, nonmatching fixture tool to run that same local script in an MCP
subprocess. This verifies capture availability and inherited environment inside
the same CLI run; native Codex shell acceptance remains blocked by the host.
Gemini reads the manifest through a native file tool because ARMADA does not grant
it shell execution.

The manifest commits after the payload under a shared folder lock. Run IDs and
folder-wide sequences keep the requested default shared path safe across retries.
Retention uses a realm-local `capture-index`, including deleted jobs and changed
templates. It never recursively deletes folders. Missing results and write failures
become incomplete audits; required capture changes the final status after execution.
Consumers should poll briefly because a CLI can start its next tool before ARMADA
consumes the preceding result event.

## Verification results

- Pinned isolated baseline: 3,204 passed, 5 skipped.
- Final pinned isolated gate: 3,261 passed, 6 skipped (455.48 seconds).
- Capture and logging contracts run separately: 65 passed.
- Python imports, changed JavaScript syntax and whitespace diff checks passed.
- Golden review: only the Jobs search entry and the new changelog entry changed.
- Real Claude, Codex app-server, Codex exec and Gemini captures each produced
  exactly three payload files and three manifest rows. Hashes matched the original
  received payloads. Nonmatching verification calls produced no capture files.
- Claude verified hashes with a later native shell script; both Codex transports
  verified them in a later local fixture subprocess; Gemini read the manifest with
  a later native file tool. The native Codex shell limitation is described above.

These checks were completed against source version 0.99.88 before publication. No real
broker account data was used. Release artifacts and publication evidence are recorded in
[the 0.99.88 verification report](RELEASE_0_99_88.md).
