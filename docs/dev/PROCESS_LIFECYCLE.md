# CLI turn lifecycle

`engine/process.py` owns model-turn subprocesses for Claude (JSON and streaming) and Codex.
Adapters build arguments and interpret their own JSON protocols; they do not feed, drain, wait
for or kill the model process themselves. Interactive sign-in and provider discovery/auth/MCP
probes retain their separate launch paths and probe timeouts.

## Ownership and deadlines

The supervisor starts its monotonic execution deadline before process creation. Separate workers
feed stdin, read stdout and drain stderr. The control loop checks cancellation and the deadline
every 50 ms, including when the child is silent, floods stderr, closes stdout without exiting, or
has not consumed a large prompt. A zero timeout explicitly disables the execution deadline.
Callbacks must return promptly; arbitrary blocking application callbacks are not preempted.

On Windows, the CLI starts hidden and suspended, is assigned to a Job Object configured with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, then resumes through the documented thread APIs. Assignment
or resume failures fail launch and terminate the suspended child. Closing the job ends ordinary
descendants as well as the CLI, including after a parent exit with inherited pipes still open.
On POSIX, the child starts a new session and cleanup kills its process group. This owns normal CLI
children; it is not a containment boundary against deliberately escaping processes. Windows job
semantics are documented in [Microsoft's Job Objects reference](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
An abrupt host death in the narrow create-suspended/before-assignment interval remains distinct
from an assigned job's kill-on-close guarantee.

`on_proc` receives a `RunProcess` handle with `pid`, `poll()` and compatible `kill()`/`terminate()`
methods. Killing requests cancellation from the owner rather than bypassing the supervisor.
Cancellation before the process callback, recorded by the HTTP run registry, takes effect as soon
as the handle arrives. Once the loop observes cancellation, the returned result is explicitly
`cancelled=True`; timeout and protocol failures are errors, not inferred cancellation.

## Bounded transport and cleanup

The stdout queue holds at most 128 lines, each limited to 1 MiB of decoded text. A turn may produce
at most 32 MiB of nonblank stdout. stderr retains 64 chunks of 4,096 characters, and only the last
4,000 characters enter diagnostics. Oversized output fails explicitly. Claude's single JSON
result collector additionally limits its total to 16 MiB.

Cleanup runs in `finally` for every launch, callback, parse, cancellation and timeout outcome.
It terminates the owned tree, waits at most three seconds for the parent, and gives all pipe
workers a shared three-second join allowance. Pipes and Windows process handles are then closed.
The execution deadline therefore has a bounded cleanup allowance; it is not a promise that all
cleanup fits inside the requested timeout. A failed cleanup step cannot skip the remaining steps,
and tree cleanup is retried. If OS cleanup still fails or pipe workers remain blocked, the result
is an explicit failure rather than a successful turn. A pipe with a blocked worker is not closed
on the main thread, where acquiring the Python I/O lock could itself hang.

Event-observer exceptions are logged and isolated: a disconnected browser must not prevent the
runner from persisting a terminal result. Process-registration callback exceptions fail the run
and trigger owned cleanup. Codex temporary-directory cleanup errors preserve the collected output
and return an error. Claude's temporary system-prompt file is removed after the supervised turn.

## Terminal results and persistence

Desktop app entry points reparent startup through Windows' explicit parent-process attribute,
using Explorer's token/device map/job and a fresh user environment. No inherited handles or
Codex environment are retained. This applies to both `python -m armada app` and the CLI entry
point; Update & Restart uses the same launcher. Failures to establish independence are reported
rather than silently starting an app owned by the caller. The main window hosts a native
loading panel while WebView2 and the server start. Its HTML loader then navigates in place;
the panel is removed after the dashboard paints. No temporary top-level splash is created.
This is an application-wide startup rule, applied before opening any realm. Changing
the active realm cannot change process ownership or the app-wide provider CLI paths.

Job retry series are serialized per job, with a durable journal under
`agents/<agent>/runs/retries/<job>.json`. Only terminal, safely replayable failures enter backoff.
A waiting journal may be resumed; a running/uncertain journal cannot justify automatic replay.
The scheduler retains its realm lease and attempt ledger across the whole series.
Retries preserve the approved prompt fingerprint exactly, and every attempt has a separate
result/receipt identity. The editor validates an integer `retries` from 0 through 3.

Success requires both a zero process exit and a valid terminal provider event. Claude requires
a `result` with a successful subtype and string result. Codex requires `turn.completed` with valid
usage data. Missing, malformed or contradictory terminal output, a provider error, or nonzero exit
fails the turn even when useful text was already produced. Unknown nonterminal event types remain
forward-compatible; invalid JSON and malformed recognized events are errors. Provider parsers keep
partial text on failures. stdout must decode as valid UTF-8; stderr decoding is best-effort. A valid
successful terminal event with no reply text produces an explicit completion record rather than
leaving the conversation unanswered.

`RunResult.cancelled` is additive and defaults to false. The runner persists failed output plus
the reason and a terminal `error` or `stopped` status for streaming chat, plain chat/Telegram and
agent jobs. Captured artifacts and capability use are preserved with that terminal record. Run
reports and chat API responses carry the same status; API responses also expose the error.
Stopped reports use the UI's warning classification while retaining their explicit raw status.

The HTTP route always releases its active-run registry entry. If deletion of an activity marker
fails, it attempts to atomically mark the file `status: finished`; the UI ignores that terminal
marker. An unwritable filesystem can defeat both operations, in which case both failures are
logged and the existing stale-marker cutoff remains the fallback.

## Verification and deployment

`tests/test_process_lifecycle.py` runs the same hostile local Python children through both adapters:
silence, stderr floods, simultaneous large Unicode stdin/stderr, closed stdout, malformed and missing
terminal events, nonzero exits after text/success, output limits, descendant cancellation/timeout,
parent exit and callback failures. Windows tests also inject ownership and cleanup failures;
runner tests verify partial-output and stopped/error persistence across all three entry paths.
Route tests verify registry cleanup and terminal-marker fallback.

Tests do not invoke paid model turns or modify live realms. There is no realm-format migration.
Restart both the app and scheduler to load these source changes; no restart is performed by the
implementation ticket. Installed CLI/version and clean-machine verification remain release gates.
