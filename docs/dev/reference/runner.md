# `armada/runner.py`

Runner (SPEC §8) — runs ONE job through an engine and writes a tokenized run-report.

This closes the telemetry gap the P1 cockpit surfaced: every run now records
input/output/cache tokens + cost, per agent, in the realm files.

v0.2 reads a minimal ARMADA-native realm (JSON configs + .md context) so a job has a
prompt to run — the reference cabinet keeps its prompts in the scheduler, so the native
format is what the runner operates on. Context assembly is the P2 slice of §5: realm
objectives + tenets + agent mandate + soul + the job prompt. (Threads/compaction = P3.)

### `_fs_snapshot(agent_dir: Path)`

{abs_path: mtime} for candidate artifact files under the agent dir — pruning the plumbing subtrees (jobs/threads/memory) and dot/underscore files. Used to detect files a turn creates via ANY tool (Bash, scripts, …), not just the Write/Edit tools we can see in the event stream.

### `_guard_snapshot(realm_root: Path, agent_dir: Path)`

Snapshot every memory file the acting agent is NOT allowed to change — the realm memory dir and every OTHER agent's memory dir (its own is exempt). Paired with _guard_restore to revert any out-of-bounds writes an agent makes during a tool turn.

### `_guard_restore(snap: dict)`

Undo any change the agent made to guarded memory files: delete files it created, restore ones it edited or deleted. The agent's own memory folder is untouched. Returns the number reverted.

### `_is_internal_artifact(path: str, agent_dir: Path)`

True for files that are plumbing, not a user-facing artifact: the agent's own realm records (job proposals, ledgers, thread logs/attachments, memory). We still surface anything the agent writes OUTSIDE its own agent dir (e.g. into D:\Work\Hand), which is where real deliverables land.

### `_running_marker(agent_dir: Path, job_id: str, on: bool)`

Write/remove a transient marker so the UI can show a job as 'running' while it executes. Best-effort: any filesystem error is swallowed (telemetry, not correctness).

### `_read(p: Path)`

—

### `_load_json(p: Path)`

—

### `_cli_model(display: str, realm_root=None)`

Map a ARMADA model label ('Claude Opus 4.8', 'Claude Sonnet 5', …) to a selector the Claude Code CLI accepts.

### `_resolve_model(realm_root: Path, agent: dict)`

Effective CLI model for an agent: its own model, else the realm default, mapped to a CLI selector. Always returns a valid selector (or '') — never the raw display label, so a label like 'Claude Opus 4.8' can't reach the CLI verbatim and error.

### `_resolve_effort(realm_root: Path, agent: dict)`

Effective reasoning-effort level to pass to the engine (--effort): the agent's effort, else the realm default, else 'high'. (Effort IS the thinking level in current Claude models; the CLI has no hard 'off' — 'low' is the floor — so there's no separate Thinking toggle.)

### `_resolve_fallback_model(realm_root: Path, agent: dict)`

Model to fall back to if the primary is overloaded/unavailable (--fallback-model): the agent's own choice, else the realm default, else '' (no fallback). Run through _cli_model so a display label ('Claude Opus 4.8') can't reach the CLI verbatim.

### `_resolve_timeout(realm_root: Path, job: dict)`

How long to let one agent run take: the job's own `timeout`, else the realm's `default_job_timeout`, else nothing (the engine's default applies).

### `_resolve_max_budget(realm_root: Path, agent: dict)`

Per-run spend ceiling in USD (--max-budget-usd): the agent's value, else the realm default, else None (uncapped). 0/blank means 'no cap'.

### `_disallowed_tools(realm_root: Path, agent: dict)`

MCP tool patterns to withhold for this run — every capability this agent may NOT use.

### `_record_used_capabilities(realm_root: Path, tool_names)`

Ensure every MCP capability an agent actually used shows up in the REALM's list, keyed by its real server name. Best-effort; never breaks a run.

### `_model_label(realm_root: Path, agent: dict, job: dict | None=None)`

The human model label used for context sizing (job override → agent → realm default).

### `_compact_threshold(realm_root: Path, agent: dict, job: dict | None=None)`

—

### `_host_preamble(realm_root: Path)`

Runtime/host parity: tell the agent the real environment so prompts written for another runtime (e.g. the Cowork sandbox) resolve here. Provider- and host-aware, ~60 tokens.

### `_jobs_capability(agent_dir: Path)`

The self-service job-proposal contract, addressed to THIS agent (absolute pending path).

### `_say(*parts)`

print() that can't take a run down.

### `_thread_href(agent_id: str, thread: str='main')`

Where to go to read what a run produced — the agent's thread.

### `_took(seconds)`

—

### `_note(headline: str, subject: str='', rows=())`

(title, body) for any notification: a headline, who or what it's about, then labelled rows.

### `_cadence_text(job: dict)`

A schedule in words. Deliberately a small local reader rather than the UI's full humaniser: that lives in the web layer, and the runner shouldn't drag the whole UI in to write a sentence.

### `_approval_note(agent_disp: str, agent_id: str, job: dict)`

What the owner needs in order to decide without opening the app: which agent wants what, what kind of thing it is, when it would run, and what it would actually do.

### `_job_note(state: str, who: str, what: str, *, why: str='', took=None, thread: str='', agent_id: str='')`

One shape for every job notification: (title, body).

### `_notify(realm_root, event: str, title: str, body: str='', href: str='')`

Announce an event: archive it in the in-app feed and, if it warrants interrupting, raise a desktop notification too. Never raises, never blocks — a failure to notify must not disturb the run that triggered it.

### `_cap_request_note(agent_disp: str, agent_id: str, req: dict)`

What the owner needs to decide on a capability request without opening the app.

### `_sync_cap_requests(realm_root, agent_id: str, thread: str='')`

Notice a capability the agent just asked for, and tell the owner.

### `_sync_proposals(realm_root, agent_id: str)`

Best-effort: record 'proposed' ledger events for any job the agent just wrote to _pending.

### `_jobs_status_text(realm_root: Path, agent_dir: Path)`

A live, authoritative snapshot of this agent's own proposals (pending/approved/rejected), so it can answer accurately instead of guessing from the thread history.

### `_cap_lines(inv: dict)`

—

### `_capabilities_context(realm_root: Path, agent_dir: Path)`

What this agent has, what else the realm has, and how to ask for the difference.

### `_norm_cap(s)`

—

### `_capability_index(realm_root: Path, agent_dir: Path)`

(kind, cap, keys) for each capability this agent may USE — for recognising which one a tool call exercised. `keys` are normalised id/name tokens.

### `_match_capabilities(tool_name: str, tool_input, index: list)`

Which capabilities a single tool call exercised. Real capability tools count: MCP tools (`mcp__<server>__…`), skill invocations, and Claude's built-in web research (WebSearch/WebFetch, surfaced as a 'built-in' capability) — NOT plumbing like Bash/Read/Write. Returns a list of (kind, cap). Empty for the common case where the agent used no capability at all.

### class `_TurnCapture`

Records what a single agent turn produced: the files it wrote, and which of its declared capabilities it actually exercised.

- `_TurnCapture.__init__(self, realm_root, agent_dir, use_tools: bool)` — —
- `_TurnCapture._add_output(self, path: str)` — —
- `_TurnCapture.on_event(self, ev)` — Sniff one streamed engine event. Never raises — it sits directly in the event path, so a capture bug must not be able to kill the run it is only observing.
- `_TurnCapture.finish(self)` — Fold in files the event stream couldn't see, and register tools used as capabilities.

### `_publish_boundary(realm_root: Path, agent_dir: Path)`

Tell the agent where its own output belongs.

### `_memory_boundary(agent_dir: Path)`

Tell the agent where it may and may not write memory. Pairs with the runtime guardrail that reverts any writes it makes outside its own memory folder.

### `_tool_preamble(realm_root: Path, agent_dir: Path)`

Everything a tool-using turn should see before ARMADA's assembled core: host/path parity, the self-service job-proposal contract, a live status snapshot of this agent's proposals, the agent's capability inventory, and the write boundaries — memory, and where output belongs.

### `_skill_registry_contract(agent_dir: Path)`

Every agent records where a skill it wrote or fetched came from.

### `_inbox_capability(realm_root: Path, agent_dir: Path)`

How this agent hands a task to a teammate — the delegation contract, addressed to THIS agent. Same shape as the job-proposal contract: write one file, no exploration needed.

### `run_job_prompt(realm_root, agent_id: str, prompt: str, thread: str='main', engine='claude', allow_tools: bool=True, label: str='adhoc')`

Run a one-off prompt as this agent, through exactly the same path a scheduled job takes.

### `run_inbox(realm_root, agent_id: str, engine='claude')`

Act on whatever is waiting in one agent's inbox.

### `process_message_now(realm_root, agent_id: str, msg_id: str, engine='claude')`

Run one waiting message immediately, ignoring the agent's cadence.

### `dispatch_inboxes(realm_root, engine='claude')`

One pass across every agent. The expensive part happens only where mail is actually waiting — everything else is a directory listing.

### `_write_report(agent_dir: Path, agent_id: str, report: dict)`

—

### `_run_command(realm_root: Path, agent_id: str, job_id: str, job: dict, agent_dir: Path)`

Deterministic job: run a shell command / script, capture status+output. No engine, no tokens. This is what runs the cabinet's Python collectors (collect_*.py, render_status.py, telegram push).

### `chat(realm_root, agent_id: str, thread: str, message: str, engine: EngineAdapter | str='mock', allow_tools: bool=False)`

Ad-hoc owner↔agent turn in a thread (SPEC §5). Same context assembly as a job run: always-on core as system + thread history + the owner's message; appends the turn.

### `_save_images(agent_dir: Path, thread: str, images: list)`

Decode data-URL images from the composer to files under the thread. Returns [{"path": abs, "file": basename, "name": original}] for saved images.

### `chat_stream(realm_root, agent_id: str, thread: str, message: str, on_event, engine: EngineAdapter | str='claude', allow_tools: bool=False, on_proc=None, images: list | None=None, files: list | None=None)`

Streaming version of chat(): emits intermediate steps via on_event(dict) as the agent works, then appends the completed turn to the thread. Falls back to a single event for engines without run_stream (e.g. mock).

### `run_job(realm_root, agent_id: str, job_id: str, engine: EngineAdapter | str='mock', thread: str='main', allow_tools: bool=False)`

—

### `_run_job_inner(realm_root, agent_id, job_id, engine, thread, allow_tools, eng, agent_dir, agent, job)`

—
