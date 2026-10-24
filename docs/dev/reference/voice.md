# `armada/voice.py`

One opt-in native voice preview, bound to an ARMADA realm, agent and thread.

Final user speech enters the ordinary agent runner; audio is only its input/output layer.
Audio and SDP are never saved.
The ordinary run registry owns cancellation; a browser lease bounds disconnected calls.

### `_key(root, agent, thread)`

—

### `current(root, agent, thread)`

—

### `active(root, agent, thread)`

—

### class `VoiceCall`

—

- `VoiceCall.__init__(self, root, agent, thread, offer, *, transport=None, mode='voice')` — —
- `VoiceCall._transcript(self, item, *, incomplete=False)` — —
- `VoiceCall.flush_speech(self, *, force=False)` — —
- `VoiceCall._save_spoken(self, identity, text)` — —
- `VoiceCall._finish_reply(self, reply, *, interrupted=False)` — —
- `VoiceCall._interrupt_reply(self)` — —
- `VoiceCall._end_replies(self)` — —
- `VoiceCall._reply(self, result)` — —
- `VoiceCall.play_reply(self, identity)` — The owning player is unmuted before this trusted, saved reply is sent.
- `VoiceCall.playback_received(self, identity)` — Commit native words only after the owning player reports output samples.
- `VoiceCall.playback_finished(self, identity)` — Only retire the owned reply after the browser has drained its audio.
- `VoiceCall.retry_playback(self, identity)` — —
- `VoiceCall.set_mode(self, mode)` — —
- `VoiceCall.event(self, method, params)` — —
- `VoiceCall.snapshot(self, *, owner=False)` — —
- `VoiceCall.stop(self)` — —
- `VoiceCall._watch(self)` — —
- `VoiceCall.run(self)` — —

### `start(root, agent, thread, offer, *, transport=None, call_id=None, mode='voice')`

—

### `close_all()`

—
