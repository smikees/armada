# Recent ARMADA changes — 8 October 2026

[0.99.94 is published](https://github.com/smikees/armada/releases/tag/v0.99.94) and staged in the running 0.99.93 app.
Apply it through the normal Restart to update action.

This expands the recent changelog, focusing on dry runs and inspectors in
0.99.93, the conversation and job-reliability fixes that preceded them, and the
dry-run UI refinement in 0.99.94.

## Dry runs and model comparisons — 0.99.93

A dry run is a separate asynchronous invocation of a saved job. The user selects
an available model for that test; ARMADA does not rewrite the production model,
schedule, enabled state or output destinations. Disabled jobs can be tested.
Unsaved editor changes are excluded, so a prompt must be saved before testing it.
There is no automatic model fallback or retry series. Tests consume provider
quota and record token usage separately, without entering the production job
history/calendar or consuming a scheduled execution slot.

Each test has a unique realm-local directory:

```
.armada/dry-runs/<agent>/<job>/<run-id>/
    job.json           saved job definition
    run.json           identity, model, requester, status, usage and retention
    transcript.json    conversation and final answer
    output/            draft artifacts and final-answer.md
    raw/               optional captured tool results
```

`{dry_run_dir}` exposes the temporary directory to the prompt. Execution also
receives `ARMADA_DRY_RUN=1`, `ARMADA_DRY_RUN_DIR` and `ARMADA_RUN_ID`. Seven-day
retention is the default; Job settings allow 1–365 days. Retention is copied into
each run, so later setting changes do not silently change an earlier test's
expiry. Housekeeping removes the whole validated terminal run tree and skips
active owned executions. The realm allows two simultaneous tests.

Start, Stop, model selection and historical output are available in Jobs and
Edit job. Navigation does not cancel a test. Stop uses the normal RunSession
coordinator and a durable stop request, including when another ARMADA process
owns the worker. Interrupted runs are detected from their ownership/liveness
records. Windows metadata reads and writes share a lock; transient access-denied
races receive a bounded retry, while corrupt state and persistent failures still
surface.

## Draft-only execution boundary

Model tests read saved input files and previously captured connector responses.
They cannot refresh live connectors, invoke unrestricted shell tools or use
sending/publication tools. ARMADA supplies invocation-scoped MCP tools to list
and read approved inputs and write drafts only inside the test's output folder.
Production prompts are preserved in the snapshot; test context replaces delivery
steps with drafts and requires missing inputs/skipped steps to remain visible.
This compares draft quality; it does not replay the complete production toolchain.

The implementation uses a temporary stdio MCP bridge to a loopback-only broker
with an ephemeral credential. The bridge receives no owner HTTP credential.
Paths are checked against permitted roots, rejecting traversal, Windows device
aliases and linked/reparse-point escapes. Draft files are written atomically.

Provider adapters configure the boundary explicitly:

- Claude retains subscription authentication while disabling ambient settings,
  skills/hooks and built-in tools, and uses strict explicit MCP configuration.
- Codex uses its read-only sandbox, disables ambient MCP servers, shell/web/apps/
  plugins/hooks, and enables only the scoped ARMADA server. Broker credentials
  are inherited through the environment rather than embedded in command arguments.
- Gemini/Antigravity uses a custom agent with the explicit MCP server and no
  native file/web/command tools. Its context includes the server name and input
  schemas to avoid incorrect discovery guesses.

Command jobs require an explicitly saved `dry_run_command`. A machine-local
approval fingerprints the job definition, production command, working directory,
environment and test command; changing that definition requires approval through
Save again. The script starts in the temporary output directory and receives the
dry-run environment/placeholders. It is a trusted script that must honor its
draft-only contract: ARMADA does not claim operating-system containment or an
egress restriction for arbitrary scripts.

## Inspector agents — 0.99.93

Configure → Advanced → Is inspector enables an agent to compare recorded
production outputs with model tests. The portable `is_inspector` flag alone
does not grant authority: the owner must also save a machine-local grant. Every
tool call checks that grant, so revocation takes effect during a conversation.
An agent cannot grant itself inspector access by editing its own configuration.

Inspectors can list realm jobs and available models, launch any realm job in
dry-run mode, review test status/output, and read other agents' recorded output
artifacts. Recorded raw captures and output-evidence files are included when
their locations pass the producer's permitted-root checks. This is not generic
access to every file, private memory or configuration in another agent's folder.

Inspectors write their own review artifacts under `agents/<inspector>/artifacts/`.
They cannot edit other agents' outputs, start production jobs, change production
models/settings or authorize command tests. Four launches per inspector turn
bound testing costs. Inspector tools are excluded from context compaction, so
compaction cannot launch another test. The owner decides whether to apply a
recommended production model change.

## Exact tool-result capture — 0.99.88

Jobs can opt into full-name glob matching through `capture_tools`. A matching
completion writes its payload and a `manifest.jsonl` entry immediately, before
the UI's shortened preview. The manifest records tool/arguments, timing, job/run
identity, error state, file size and SHA-256. A payload is atomically completed
before the manifest advertises it. Shared folders allocate increasing sequences
so concurrent calls and retries cannot overwrite earlier captures.

The exactness boundary is the data exposed by the engine CLI to ARMADA. JSON
payload tokens preserve whitespace, key order and numeric spelling; text is
decoded once into UTF-8 without trimming or newline conversion. A `.json` payload
can contain arbitrary text, identified by its manifest encoding. ARMADA cannot
recover vendor-side truncation or transformations before that boundary.

Claude uses `tool_use_result` when available, otherwise result-block `content`;
Codex uses a completed MCP item's `result`/`error`; Gemini uses
`tool_info.output`/`error`. `{raw_dir}` and `ARMADA_RAW_DIR` let later steps read
the completed files without the model retyping broker numbers. Capture is local
and does not grant additional tool permissions. Paths stay inside the configured
workspace. Failures leave execution running but mark the audit incomplete;
`require_capture` makes the terminal result fail. Default capture retention is
30 days. Dry-run captures remain in the temporary test tree.

## Shared detached conversations — 0.99.92

Previously the sending page rendered its own optimistic/SSE transcript while
other views polled persisted content. Hidden views could stop polling, and Stop
relied on a cached run ID. These paths could show different Markdown, tool
activity or completion state and leave a detached Stop ineffective.

The main thread page, widget and detached window now use one canonical
conversation snapshot. SSE and realm/thread-scoped BroadcastChannel events
invalidate that snapshot; bounded polling covers disconnects and hidden windows.
Stop resolves the active turn from realm, agent and thread on the server, rather
than trusting a stale window run ID. Cancellation failures remain visible and
retryable, and losing a transport does not incorrectly declare the engine idle.
Unsent drafts and expanded tool details remain local interface state. Native
checks compare the exact live/terminal transcript HTML across both views and
exercise Stop, disconnect and close/reopen during an active turn.

## Job admission, calendar and realm lifecycle — 0.99.91

The apparent failed-but-published daily jobs involved two execution pipelines:
ARMADA attempts failed at Codex sandbox startup, while still-enabled Claude
routines produced the successful outputs. The approved operational recovery
paused every Claude routine; ARMADA became the selected scheduler. Historical
failed ARMADA reports were preserved and no business delivery was rerun.

ARMADA now verifies actual sandbox execution and explicit-model availability
before admitting Codex work. An automatically discovered desktop CLI may use an
already installed standalone CLI only after the same policy checks pass.
Explicit CLI paths and model choices remain explicit. Typed startup failures
show their cause and do not burn business-job retries. Claude connector inventory
has a bounded 90-second startup budget. Calendar retries are grouped into one
series with final outcome and attempt count, while original attempt reports remain.
Research observations and expected unknown dates have dedicated evidence fields,
without weakening the audit rules for missing required evidence or risk gates.

Realm deletion previously collided with the scheduler's kernel lease. Deletion
now requests cooperative idle-lease release before moving the folder to the
Recycle Bin. Archived, removed and missing realms also release their leases;
listeners stop and late polling cannot recreate a deleted folder. A failed
release preserves the folder and reports an actionable error.

## Dry-run interface consistency — 0.99.94

The section is now named **Dry run history**, with the same 14-pixel chevron,
heading font/weight, spacing, indentation and divider as Prompt, Output and Run
history. The test-model and history pickers reuse the existing compact output
select styling. Body text matches production output's 13-pixel scale. The
duplicate top-row Dry run button and its unused JavaScript handler are removed;
Start dry run remains inside the expanded section. Execution behavior is unchanged.

The native Jobs probe passed 16 checks at each of 1280 and 660 pixels, including
computed-style/icon/alignment consistency, model selection, disabled jobs, Stop,
independent history, navigation recovery and saving inspector authority. The
targeted tests passed 78 checks; snapshot/reference verification passed 179.
Light/desktop and dark/narrow renders were reviewed. The enforced publisher also passed 3,372 isolated tests (5 skipped), exact-source
Windows CI, 5 launcher recovery checks, 16 native window sessions and 63 packaged
upgrade checks. Public signatures, hashes and all 331 packaged source files were
verified. Publication evidence is recorded in the release verification document.

## Further technical detail

- [Draft execution and inspector architecture](ADR_014_DRY_RUNS.md)
- [0.99.93 verification and provider evidence](RELEASE_0_99_93.md)
- [Detached conversation verification](RELEASE_0_99_92.md)
- [Job incident and operational recovery](INCIDENT_2026_10_08_JOBS.md)
- [0.99.94 verification](RELEASE_0_99_94.md)

The updater verifies Ed25519-signed manifests and package hashes. Maintenance
Windows installers remain unsigned under the existing beta distribution;
trusted publisher signing and clean-Sandbox GUI acceptance are still outstanding.
