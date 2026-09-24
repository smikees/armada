# `armada/verbosity.py`

How much an agent writes back.

ARMADA composes the whole system prompt (it passes `--system-prompt`, not `--append-system-prompt`),
so this is one more paragraph in something we already build — no extra CLI flag, no settings file.

The alternative was Claude Code's own `outputStyle`, which is the official mechanism and has a
built-in Concise style. Two things ruled it out: it's a settings-file field scoped to a session
rather than to one agent, and `--safe-mode` disables output styles — and ARMADA passes `--safe-mode`
on its no-tool and restricted paths. A verbosity setting that silently stops applying on some of
our own code paths is worse than not having one.

Two rules hold across every level, because "be brief" is otherwise an instruction to do less work
rather than to write less about it:

* Length is about the reply, never about the work. The same checking, reading and verifying happens
  at every level.
* Some things are never compressed: what went wrong and why, warnings, anything needing the owner's
  approval, and the exact content of an error. Those are the moments brevity costs the most.

### `normalise(value)`

A stored level, or '' for anything unrecognised (which means 'inherit').

### `_json(p: Path)`

—

### `realm_level(realm_root)`

—

### `agent_level(realm_root, agent_id: str)`

Per-agent, falling back to the realm default — the same pattern as model and effort.

### `prompt_block(level: str)`

The system-prompt section for a level. Always returns something: an agent that has never been configured should still be told what's expected, rather than being left to guess.

### `label(level: str)`

—
