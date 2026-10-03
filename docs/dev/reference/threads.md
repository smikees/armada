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
- `Thread.snapshot(self)` — A coherent summary and live log, including recovery of interrupted compaction.
- `Thread._messages(self)` — —
- `Thread.display_snapshot(self)` — Hide historical job turns without changing chat-action indexes or stored data.
- `Thread.summary(self)` — —
- `Thread._who(role: str)` — —
- `Thread._is_turn(m: dict)` — A conversational turn (goes to the model), as opposed to a UI 'event' entry.
- `Thread.render(self)` — —
- `Thread._render(cls, summary, messages)` — —
- `Thread._write(self, *records)` — —
- `Thread.append(self, user: str, assistant: str, attachments=None, outputs=None, caps=None)` — Write a complete turn — both halves at once. For a live chat use begin_turn / complete_turn instead, so the owner's message survives them walking away.
- `Thread.begin_turn(self, user: str, attachments=None)` — Record what the owner said, now, before the agent has said anything back.
- `Thread.complete_turn(self, turn: str, assistant: str, outputs=None, caps=None, status: str='ok')` — Close a turn opened by begin_turn. `status` is 'ok', 'error' or 'stopped'.
- `Thread._progress_path(self, turn: str)` — —
- `Thread.save_progress(self, turn: str, text: str, activity: str='Working on it…', events: list[dict] | None=None)` — Checkpoint visible output before emitting it, so navigation cannot lose it.
- `Thread.progress(self, turn: str)` — —
- `Thread.open_turn(self, messages: list[dict] | None=None)` — The last owner message without its matching reply, including overlapping turns.
- `Thread._turn_groups(cls, messages)` — Pair explicit IDs or adjacent legacy exchanges; ambiguous/orphan records stay live.
- `Thread.append_event(self, type: str, title: str='', subtitle: str='', icon: str='', status: str='', href: str='', pct=None, meta: dict | None=None)` — Append a non-message 'event' entry (rendered as an inline card in the UI, e.g. 'Created scheduled task …' or a compaction progress bar). Events are UI chrome — they are skipped when assembling the model context and preserved across compaction.
- `Thread.truncate(self, keep: int)` — Keep the first requested records; invalidate any summary currently being generated.
- `Thread.compact_if_needed(self, engine, threshold_chars: int=600000, keep_recent_pairs: int=3)` — Summarize a validated prefix outside the lock, preserving new appends and pending turns.
- `Thread.list_threads(agent_dir)` — —
