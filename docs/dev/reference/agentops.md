# `armada/agentops.py`

Agent lifecycle — retire, reinstate, delete.

An agent is a folder: `agents/<id>/` holding its agent.json, mandate, soul, tenets, jobs, threads,
memory, run history and capability grants. Every part of ARMADA that asks "who is in this realm"
answers by listing that directory — the reader, the scheduler, the capability scan, the inbox
sweep, the delegation roster the system prompt is built from.

So retiring moves the folder to `retired/<id>/` and that is the whole mechanism. The alternative —
a `retired: true` flag in agent.json plus a filter at every site that iterates agents — is a filter
you can forget in one place, and the place you forget is the scheduler, which then runs a retired
agent's jobs at 3am. A folder the scheduler cannot see cannot be run by it. "Jobs turned off" comes
out of the move rather than out of editing seven job files and hoping to put them back correctly.

Nothing is edited on the way out except a timestamp. That is what makes reinstating exact: the
jobs, their schedules and their on/off states, the threads, the memories, the grants and the run
history all travel together and come back as they were. The two stamps we do write — `retired` and
`reinstated` — exist because the week strip needs them: a job with a 09:00 cron that spent a
fortnight retired should not come back showing fourteen missed days. It wasn't missed. It wasn't
due.

What stays behind, deliberately:

* **Goal membership.** A goal's `agents:` list keeps the retired id, so reinstating restores the
  goal without anyone re-adding them. `goals_for_agent` is only ever called for agents that exist,
  so a retired id sitting in that list costs nothing while they are gone.
* **Realm capability catalogue.** Grants live in the agent's own toolkit and travel with it; the
  "Available to" list on a realm capability is computed from the live agents at render time, so a
  retired agent drops off it and comes back on by itself.
* **Other agents' inboxes.** A message from a retired agent keeps its sender name. It is a record
  of something that happened, not a live link.

What is genuinely lost while an agent is retired is its share of the usage charts, which read the
live agents. That is visible and reversible rather than silent: the tokens come back when they do.

### `_now()`

—

### `_read_json(p: Path)`

—

### `live_dir(realm_root, agent_id: str)`

—

### `retired_dir(realm_root, agent_id: str='')`

—

### `list_retired(realm_root)`

Retired agents, newest first — enough of each to fill the Reinstate form.

### `is_retired(realm_root, agent_id: str)`

—

### `reinstated_at(realm_root, agent_id: str)`

When this agent last came back, or ''. What the week strip uses so a job isn't marked as having missed fire times that fell while its owner was retired.

### `_live_agents(realm_root)`

—

### `_guard(realm_root, agent_id: str, verb: str)`

The two agents you must not remove, whichever way you are removing them.

### `retire(realm_root, agent_id: str)`

Move an agent out of the realm without touching what is inside it.

### `reinstate(realm_root, agent_id: str, overrides: dict | None=None)`

Bring a retired agent back, optionally with edits made on the way in.

### `delete(realm_root, agent_id: str, permanent: bool=False)`

Delete an agent's folder — live or retired.
