# `armada/capabilities.py`

Who may use which capability.

One rule, stated once, so every other part of the app can ask instead of deciding for itself:

* **The realm holds the catalogue.** Everything discovered, installed or imported lands at realm
  level and nowhere else. A capability existing is not a capability anyone can use.
* **A coordinator may use all of it.** If a realm has a PM, that role is the one that sees across
  the whole realm, so granting it everything is the honest description of the job rather than a
  shortcut. A realm with no coordinator has no agent with blanket access — nobody inherits it.
* **Every other agent may use only what it has been granted**, either by the owner mapping it on
  the Capabilities page or by approving a request the agent made in a thread.
* **Every agent can SEE the whole catalogue.** Discovery is the point — an agent that can't know a
  tool exists can't ask for it. Seeing is not using.

The inversion that matters: before this, an empty agent toolkit meant *inherit everything*, and
the only thing that could stop an agent was a capability switched off for the entire realm. Empty
now means **nothing**, and a grant is a positive act. That way the question "what can this agent
reach" is answered by a list you can read, rather than by the absence of a prohibition.

**What is actually enforced.** Connectors and extensions are MCP servers, so an ungranted one is
withheld by denying its `mcp__<id>` tools at the engine — real enforcement, not advice. Skills and
plugins have no equivalent per-call handle, so for those a grant controls what the agent is *told
it has*; an agent that goes looking for an ungranted skill is not stopped by this module. Said
plainly here because the difference decides how much weight the grant list can carry.

### `_now()`

—

### `_read(p: Path)`

—

### `cap_key(cap)`

The identity of a capability, for comparing across realm and agent lists.

### `catalogue(realm_root)`

{kind: [cap, ...]} — everything this realm knows about.

### `catalogue_flat(realm_root)`

[(kind, cap), ...] across every kind, in a stable order.

### `find(realm_root, cap_id: str)`

(kind, cap) for a capability in the realm catalogue, or (None, None).

### `realm_enabled(cap)`

Is this capability switched on for the realm at all? A realm-level off beats any grant.

### `_agent(realm_root, agent)`

Accept an agent id or an already-loaded agent dict.

### `is_coordinator(agent)`

—

### `has_coordinator(realm_root)`

—

### `grants(realm_root, agent)`

{kind: [cap, ...]} the agent has been explicitly granted (its own toolkit).

### `granted_keys(realm_root, agent)`

—

### `usable(realm_root, agent)`

{kind: [cap, ...]} the agent may actually use, resolved against the realm catalogue.

### `visible(realm_root, agent)`

{kind: [cap, ...]} the agent may KNOW ABOUT. The whole enabled catalogue, always.

### `requestable(realm_root, agent)`

{kind: [cap, ...]} visible but not usable — exactly what an agent could ask for.

### `may_use(realm_root, agent, cap_id)`

—

### `grant(realm_root, agent_id: str, cap_id: str, *, via: str='user', thread: str='')`

Let an agent use a realm capability.

### `revoke(realm_root, agent_id: str, cap_id: str)`

—

### `grant_record(realm_root, agent, cap_id)`

The agent's own grant entry for a capability — carries granted_at / granted_via / thread.

### `granted_in_thread(realm_root, agent, cap_id, thread: str)`

Was this capability granted to this agent through THIS conversation?

### `denied_tool_patterns(realm_root, agent)`

`mcp__<id>` patterns to withhold from this run: every MCP capability the agent may not use.

### `_slug(s: str)`

—

### `requests_dir(realm_root, agent_id: str)`

—

### `request(realm_root, agent_id: str, cap_id: str, reason: str='', thread: str='')`

Record an agent asking to use a realm capability. Nothing is granted by this.

### `iter_requests(realm_root)`

(agent_id, slug, request, path) for every outstanding capability request.

### `count_requests(realm_root)`

—

### `approve_request(realm_root, agent_id: str, slug: str)`

Grant what was asked for, recording the thread it was asked in.

### `reject_request(realm_root, agent_id: str, slug: str)`

—
