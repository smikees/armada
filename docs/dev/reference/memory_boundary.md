# `armada/memory_boundary.py`

Non-destructive memory boundary: provider denials where available, observation everywhere.

A before/after fingerprint cannot identify a writer. Never use it to restore or delete data.
Observations contain paths and change kinds, not copies of private memory contents.

### `protected_roots(realm_root, agent_dir)`

Include missing memory directories, so creating one doesn't evade the launch policy.

### `claude_denials(realm_root, agent_dir)`

Absolute Edit rules cover Claude's built-in file editors, not arbitrary shell/MCP code.

### class `MemoryAudit`

Bounded, read-only observations over a turn; completion never writes guarded memories.

- `MemoryAudit.__init__(self, realm_root, agent_dir, provider='unknown')` — —
- `MemoryAudit._label(self, path)` — —
- `MemoryAudit.protects(self, path)` — Recognize logical and resolved targets, including a newly appointed agent's memory.
- `MemoryAudit.observe(self, event)` — A tool event is evidence of an attempt, not proof that the provider performed a write.
- `MemoryAudit._scan(self)` — —
- `MemoryAudit.finish(self)` — Return idempotent observations; unknown writers are never labelled as this agent.
- `MemoryAudit.record(self, thread=None)` — Keep evidence even if the engine raises/cancels before it can produce a run report.
