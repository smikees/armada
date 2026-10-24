# `armada/voice_turns.py`

Admit native speech as ordinary agent work, independently of the audio call.

Accepted messages and queued progress are saved before returning. The server owns the
FIFO worker and RunSessions: leaving voice or closing a view never cancels its work.
Like typed turns, an application shutdown does not automatically replay side effects.

### `_target(root, agent, thread)`

—

### `submit(root, agent, thread, text, *, voice_session, voice_item, reply=None)`

—

### `_drain(key)`

—
