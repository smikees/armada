# Memory boundaries (launch 2.15)

The former runner snapshotted realm memory and other agents' memories, then restored old bytes
and removed new files at completion. It could not identify the writer, so it undid concurrent
agent work, owner edits and system-memory refreshes. Both snapshot/restore helpers are removed.
No completion, exception or cancellation path restores or deletes protected memory.

## Provider restrictions

Agents may write their own `agents/<id>/memory` folder. Shared memory changes should be proposed
to the owner and made through the relevant source of truth. The prompt describes this agreement
without claiming a sandbox.

| Provider | Current invocation | Limit |
|---|---|---|
| Claude | At launch, the runner adds absolute `Edit(//.../memory)` and `Edit(//.../memory/**)` rules for realm memory and every existing other agent directory, including missing memory folders. Literal glob characters are escaped; logical and resolved roots are included. Windows drive paths use `//d/...`. Failure to construct the rules blocks execution. | Applies to built-in file editors. Arbitrary shell scripts and MCP calls are not contained. Agents created or directories moved after launch, hard links and other aliases are not fully covered. UNC roots require a mapped drive. |
| Codex | Existing `workspace-write` invocation with the agent, realm and workspace as writable roots; bounded memory observation at completion. | The current adapter has no per-memory write isolation. Restricted MCP grants are separate from filesystem restrictions. |

Claude consults `Edit(path)` for its built-in editors, including Write and NotebookEdit;
`Write(path)` rules are accepted but ignored. Denial rules take precedence over allow rules.
Some recognized Bash file operations honor file rules, but arbitrary Python/Node scripts can
bypass them. Reference: [Claude Read and Edit permissions](https://code.claude.com/docs/en/permissions#read-and-edit).

Codex supports named permission profiles with narrower read-only paths, but those profiles are
beta and a loaded legacy `sandbox_mode` or `--sandbox` can override `default_permissions`.
The installed `codex exec` 0.158.0-alpha.2.1 has no explicit `--permission-profile` selector.
Armada does not claim to apply such a policy by passing an override that may be ignored, or
discard the user's MCP configuration to force it. Future integration must verify the effective
policy on each supported platform. Even those filesystem profiles govern sandboxed commands,
not MCP tools. Reference: [Codex permissions](https://learn.chatgpt.com/docs/permissions).

## Observations and durability

`memory_boundary.MemoryAudit` hashes protected files before/after tool-enabled chat, streaming
chat, jobs and inbox prompts. It stores no memory contents. `_TurnCapture.finish()` runs in
`finally`, including engine exceptions and cancellation. It never writes guarded memories.
The audit identifies additions, removals and modifications, always with `writer: unknown`.
An explicit file-tool event is stored separately as a **write attempt**, never proof of success.
Protected memory paths and audit files are excluded from output artifacts.

The normal run report has a `memory_boundary` field. Any observed change, attempt or incomplete
scan also produces `agents/<id>/runs/memory-audits/<audit-id>.json` and an expandable thread event.
This separate evidence survives an engine exception even if no normal run report is produced.
Records contain relative paths, provider, timestamps and coverage information; hashes and
original contents are not persisted. Repeated finalization does not duplicate the event. Audit
write failures are logged and do not replace the engine result or attempt a memory repair.

Each scan is bounded to 4,000 filesystem entries and 64 MiB of file data; details are capped at
100 paths per category. Symlinks/junctions are recorded but not traversed, with an explicit
coverage issue. Unreadable paths and size limits are reported. Partial scans do not label an
unobserved file as added/deleted; overlapping readable files can still be compared.

These are observations, not transactions or proof of isolation. A concurrent writer can change
a file while it is being hashed; a write reverted before the final scan is invisible. A killed
Armada process may never finalize its audit. External tools need their own access controls if
hard isolation is required. Deterministic command jobs, no-tool helpers and system upkeep do not
use this agent-turn audit. Recovery remains an explicit owner action, never automatic rollback.

## Verification

`tests/test_memory_boundary.py` holds agent A inside a fake provider while agent B runs, the owner
edits shared memory and system upkeep refreshes its digest. All four runner entry points and
both provider names are checked for success, failure, stop, engine exception and cancellation.
Every writer's exact resulting bytes survive, including new files and deliberate deletions.
Other checks cover reported attempts versus actual changes, own-memory exemption, missing/new
memory directories, incomplete scans, junction coverage, bounded scans, durable evidence,
artifact exclusion and escaped paths in the observation card. Claude argv tests verify the
denial rules reach the CLI alongside existing MCP restrictions; they do not spend model quota
or claim an end-to-end provider sandbox test.
