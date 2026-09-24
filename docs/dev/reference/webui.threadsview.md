# `armada/webui/threadsview.py`

Threads / chat rendering (Layer 2, carved from _core.py in Phase 3).

The thread rail, chat centre/composer, turn + activity-segment rendering, thread artifacts and
capabilities rails, and per-thread meta helpers. Imports lower layers (never _core); _core
re-imports these names.

### `_user_avatar_file(realm_root)`

—

### `_user_avatar(realm_root, size: int)`

The owner's avatar <img> if one is set, else '' (callers fall back to the 'You' chip).

### `_sub(active: str, agent_id: str, counts: dict)`

—

### `_est_tokens(chars: int)`

—

### `_thread_title(meta: dict, slug: str)`

—

### `_meta_path(agent_dir)`

—

### `_touch_last_thread(agent_dir, slug: str)`

Remember the thread the owner is viewing so returning to the Threads tab reopens it (not 'main'). Persisted in meta.json; written only when it actually changes.

### `_write_thread_meta(agent_dir, meta: dict)`

Atomic write of meta.json. Callers doing a read-modify-write hold util.file_lock on it.

### `_mark_thread_unread(agent_dir, slug: str)`

Flag a thread as having unseen output (drives the teal 'unseen' status dot). Called when a run posts a reply, so the owner sees there's something new even away from that thread.

### `_clear_thread_unread(agent_dir, slug: str, render_meta: dict | None=None)`

Opening/viewing a thread clears its unseen flag. Updates the in-memory meta the current render reads from (if given) so the thread list shows it read immediately, and persists to disk.

### `_ordered_threads(agent_dir)`

Thread slugs in display order: main first, then pinned, then the rest (by saved order, else name).

### `_turn_actions(role: str, idx: int, aid: str, thread: str, is_last_user: bool, when: str)`

—

### `_event_card(m: dict)`

A non-message thread entry rendered as an inline, centered card — e.g. 'Created scheduled task …' or a compaction progress bar. Distinct from chat bubbles: no avatar, full-width, subtle border. Driven by a {role:'event', type, title, …} jsonl entry.

### `_render_segments(segs)`

Render an assistant turn's full activity trail: text notes (Markdown), tool-activity chips ('Ran a command · 2 notes'), and any thought-process blocks — like the Claude app.

### `_attachments_html(att, aid: str, thread: str)`

Thumbnails for image attachments + name chips for file attachments, in a user turn.

### `_turn(role: str, raw, ts: str, idx: int, is_last_user: bool, aid: str, thread: str, disp: str, coord: bool, av: str='', userav: str='', seg=None, att=None)`

—

### `_agent_model_label(realm_root, aid: str)`

The agent's model label (its own, else the realm default) for context-window sizing.

### `_thread_caps_used(msgs: list, realm_root=None, agent_id: str='', thread: str='')`

Capabilities the agent ACTUALLY exercised in this thread, grouped by type. Read from the `caps_used` recorded on each assistant turn (a real tool call to that connector/skill), NOT guessed from keywords — so a thread that used no capability shows nothing.

### `_thread_caps_rail(caps: dict)`

The 'Capabilities in this thread' block for the right rail, grouped by type under its icon. Always rendered — shows a placeholder until the agent actually invokes a connector/skill/plugin.

### `_thread_artifacts(agent_dir, aid: str, thread: str, msgs: list)`

Split a thread's artifacts into INPUTS (what the owner attached) and OUTPUTS (files the agent wrote/edited this thread). Inputs come off user turns' `attachments`, outputs off assistant turns' `outputs`. Both are de-duplicated; outputs note whether the file still exists on disk.

### `_art_chip(label: str, title: str, *, reveal: str='', lightbox: str='', icon: str='file', dim: bool=False)`

One artifact chip (type icon + filename). `reveal` (an absolute path) or `lightbox` (a URL) is stashed in a data- attribute and handled by a delegated click listener in chat.js — NOT inlined into onclick, so Windows backslashes in the path can't corrupt the JS string.

### `_thread_arts_rail(inputs: list, outputs: list, agent_id: str='')`

The 'Artifacts' rail block: Input artifacts (owner attachments) + Output artifacts (agent files). Always rendered — shows a placeholder until files are attached or created in the thread.

### `_thread_rail(realm_root, a, selected: str)`

The right rail for a thread: loaded-context breakdown + capabilities used + artifacts. Factored out of _tab_threads so it can be refetched on its own after a reply (new outputs appear without a full reload). Carries id='mc-rail' so chat.js can swap it in place.

### `_render_turns(realm_root, a, selected: str)`

Render just the transcript turns for a thread (server-canonical Markdown, icons, segments). Shared by _chat_center and the /api/thread-turns refresh endpoint, so the live view after a reply becomes identical to a reloaded page (no client/server rendering drift).

### `_working_turn(av: str, disp: str)`

The agent is working on the message above, right now.

### `_unanswered_turn(av: str, disp: str)`

The message above never got a reply and nothing is working on it.

### `_chat_center(realm_root, a, selected: str, embed: bool=False, lead: str='')`

The center chat column: transcript + composer. Shared by the Threads tab and the dashboard thread widget (embedded via iframe) so both use the exact same chat UI/UX. In embed mode the header line is dropped — the widget box header carries that info. `lead` prepends HTML (e.g. an avatar + status dot) inside the header, before the title.

### `_tab_threads(realm, realm_root, a, selected: str=None)`

—
