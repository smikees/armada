# `armada/inbox.py`

Agent-to-agent delegation — an inbox per agent.

An agent can ask a teammate to do something. The ask lands in the recipient's inbox; the recipient
acts on it on its own cadence, in its own dedicated thread, with all of its own context. That's the
point: Steve knows how the daily price-check job is built, so "add the Fitbit Air to it" belongs
with Steve rather than being explained to someone else.

Three things this module exists to make safe.

**Cost.** Checking an inbox is a plain file read — no engine, no tokens. The agent is only invoked
when a message is actually waiting. So a one-minute cadence means "act within a minute of being
asked", not "wake an agent 1,440 times a day to find nothing".

**Loops.** Two agents politely answering each other is an unbounded bill. Every message carries the
chain it came from and how many hops it's taken; chains die at _MAX_HOPS, identical asks collapse,
and each agent has a ceiling on how many delegated tasks it will run per hour.

**Exactly once.** Claiming a message is an atomic rename before the agent runs, so a scheduler
restart mid-task can't replay it.

Delegated work is never more privileged than self-directed work: the receiving agent runs with its
normal permissions, so anything that changes the realm (editing a job, installing a capability)
still goes through the owner's approval gate exactly as it would otherwise.

### `parent_id(msg: dict)`

The task a reply answers, or "" for an ordinary message.

### `threaded(items: list)`

Order a flat list so each reply sits directly under the message it answers.

### `_agent_dir(realm_root, agent_id: str)`

—

### `_box(realm_root, agent_id: str, state: str=PENDING)`

—

### `_read(p: Path)`

—

### `_list(realm_root, agent_id: str, state: str)`

—

### `_realm_cfg(realm_root)`

—

### `_agent_cfg(realm_root, agent_id: str)`

—

### `enabled(realm_root)`

Realm-wide switch. Delegation changes what the realm does while nobody's watching, so it can be turned off wholesale without unpicking every agent's cadence.

### `agent_enabled(realm_root, agent_id: str)`

Per-agent switch, on by default. Distinct from a cadence of 'off': that says "I'll get to my inbox never", this says "don't involve me in agent-to-agent work at all", which also means nobody can queue anything for this agent in the first place.

### `cadence(realm_root, agent_id: str)`

Per-agent, falling back to the realm default — the same pattern as model and effort.

### `accepts_from(realm_root, agent_id: str)`

—

### `_is_coordinator(realm_root, agent_id: str)`

—

### `_fingerprint(frm: str, ask: str)`

—

### `_recent_fingerprints(realm_root, agent_id: str)`

—

### `_ran_last_hour(realm_root, agent_id: str)`

—

### `send(realm_root, frm: str, to: str, ask: str, context: str='', origin: str='', hops: int=0)`

Queue a task for another agent. Returns {ok, id} or {ok:False, error, reason}.

### `has_mail(realm_root, agent_id: str)`

The cheap check — a directory listing, no engine, no tokens.

### `due(realm_root, agent_id: str, now=None)`

Has this agent's cadence elapsed since it last looked? Cadence is a latency promise, not a poll rate — with no mail waiting, being 'due' costs nothing.

### `mark_checked(realm_root, agent_id: str)`

—

### `claim(realm_root, agent_id: str, msg: dict)`

Move a message from pending to running. The rename is the lock: if it fails, someone else got there first, so a restart mid-dispatch can't run the same ask twice.

### `complete(realm_root, agent_id: str, msg: dict, ok: bool, detail: str='')`

File the message as done and tell the sender how it went — without a reply, a failed delegation is invisible to whoever asked for it.

### `screen(realm_root, agent_id: str, msg: dict)`

Enforce the rules at PICKUP, not just at send.

### `next_batch(realm_root, agent_id: str)`

Messages to act on right now, honouring the per-agent hourly ceiling.

### `prompt_for(msg: dict)`

A self-contained prompt. The inbox thread is long-lived and carries unrelated asks, so an instruction must never depend on what else happens to be in that thread's history.

### `all_messages(realm_root, recent_hours: int=24)`

Everything across every agent, split the way the page shows it: what's still waiting, what was handled recently, and the older pile that belongs in the archive.

### `_find(realm_root, agent_id: str, msg_id: str)`

—

### `requeue(realm_root, agent_id: str, msg_id: str)`

Mark a handled message unread — it goes back to pending and is acted on again next pass.

### `delete(realm_root, agent_id: str, msg_id: str)`

—

### `counts(realm_root, agent_id: str)`

—
