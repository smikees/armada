# `armada/threads.py`

Threads + compaction (SPEC §5).

An agent has a **main** thread (default) and optional **sub-threads** for scoped context
(e.g. a `taxes` thread that carries tax history but not options-trading). A thread is an
append-only `messages.jsonl` plus an optional `summary.md` of older, compacted turns.

Compaction: when a thread's rendered history exceeds a threshold, the oldest turns are
summarized (via the engine) into `summary.md` and dropped from the live log — while the
agent's always-on core (memory.py) is re-injected fresh every run and never compacted.
Sub-threads inherit the core but NOT each other's history — that's the scoping lever.

### class `Thread`

—

- `Thread.__init__(self, agent_dir, name: str='main')` — —
- `Thread._messages(self)` — —
- `Thread.summary(self)` — —
- `Thread._who(role: str)` — —
- `Thread._is_turn(m: dict)` — A conversational turn (goes to the model), as opposed to a UI 'event' entry.
- `Thread.render(self)` — —
- `Thread._write(self, *records)` — —
- `Thread.append(self, user: str, assistant: str, attachments=None, outputs=None, caps=None)` — Write a complete turn — both halves at once. For a live chat use begin_turn / complete_turn instead, so the owner's message survives them walking away.
- `Thread.begin_turn(self, user: str, attachments=None)` — Record what the owner said, now, before the agent has said anything back.
- `Thread.complete_turn(self, turn: str, assistant: str, outputs=None, caps=None, status: str='ok')` — Close a turn opened by begin_turn. `status` is 'ok', 'error' or 'stopped'.
- `Thread.open_turn(self)` — The last owner message with no reply after it, or None.
- `Thread.append_event(self, type: str, title: str='', subtitle: str='', icon: str='', status: str='', href: str='', pct=None, meta: dict | None=None)` — Append a non-message 'event' entry (rendered as an inline card in the UI, e.g. 'Created scheduled task …' or a compaction progress bar). Events are UI chrome — they are skipped when assembling the model context and preserved across compaction.
- `Thread.compact_if_needed(self, engine, threshold_chars: int=600000, keep_recent_pairs: int=3)` — Summarize older turns when history grows past the threshold. Returns True if compacted. Only conversational turns are summarized/dropped; 'event' entries are always preserved.
- `Thread.list_threads(agent_dir)` — —
