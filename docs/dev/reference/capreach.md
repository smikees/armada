# `armada/capreach.py`

Which engines a capability works with — its *reach* — and what a model change would cost.

ARMADA runs each agent on Claude, Codex or Gemini and keeps its context when the model changes.
Capabilities do not travel that freely, and pretending they do turns a predictable limit into a
job failure the owner discovers later. This module is the one place that answers three questions,
so the Capabilities page, the model pickers, the execution policy and the agent's own context can
never disagree:

* **Reach.** Does this capability work with *any engine*, or with *one* (a connector hosted in the
  Claude account, a ChatGPT app, a Claude Code plugin)?
* **One engine at a time.** Some services refuse concurrent AI platforms — authorising a second one
  disconnects the first (Interactive Brokers, per its own staff). Such a capability has a *current
  engine* and is unavailable on the others until the owner moves it.
* **Impact.** Which of an agent's capabilities stop working if it runs on another engine, and why.

Reach is derived from what the record already says (its endpoint, its engine bindings, its kind)
rather than stored, so it cannot drift from the record. Explicit fields win when present:
`reach` on rows ARMADA created for one engine, `exclusive` as an owner override, and
`exclusive_engine` once the owner has moved a one-engine-at-a-time capability.

Two capabilities are the same only if they reach the same server. A ChatGPT app and a Claude
connector that both say "Google Drive" are two rows, never one (see docs/dev/CAPABILITIES_UPGRADE.md).

### class `Reach`

What one capability can be used with.

- `Reach.available_on(self, engine: str)` — —
- `Reach.usable_engines(self)` — —
- `Reach.blocked_reason(self, engine: str, name: str='')` — Why it does not work on `engine`, as a sentence; empty when it does.
- `Reach.as_dict(self)` — —

### `_https(value)`

—

### `endpoint(cap: dict)`

The capability's own remote MCP address, if it has one.

### `host(url: str)`

—

### `_host_in(h: str, suffixes)`

—

### `bindings(cap: dict)`

—

### `is_claude_import(cap: dict)`

A connector Claude set up arrives as `claude.ai <name>` / `claude_ai_<name>`.

### `_provider_hosted(url: str)`

—

### `known_one_at_a_time(cap: dict)`

The known service entry this capability belongs to, if it allows one platform at a time.

### `_connector_reach(cap: dict)`

(scope, how, why) for a connector row.

### `reach(kind: str, cap: dict)`

The reach of one realm capability. Never raises; unknown shapes read as any engine.

### `entry_reach(entry: dict)`

Reach of a catalogue entry before it is added: 'any' or one engine.

### `agent_engine(realm_root, agent, job=None, model: str | None=None)`

The engine an agent (or one of its jobs) runs on, optionally with a model swapped in.

### `impact(realm_root, agent, engine: str)`

Every capability the agent may use that would NOT work on `engine`, with the reason.

### `impact_text(display: str, engine: str, lost: list, limit: int=6)`

One line for a model picker or a confirmation.

### `sections(realm_root)`

{scope: {kind: [cap, ...]}} for the whole realm catalogue, in display order.

### `engine_scope(kind: str, cap: dict)`

Engines on which an MCP capability may be admitted to a turn right now.
