# Steering an active owner conversation

Version 0.99.138 adds text steering to an already admitted conversational run.
`ProviderCapabilities.steering` declares adapter support; a live process handle's
`can_steer` also must be true. Only Codex app-server advertises it today. Claude,
Gemini, Codex exec fallback, queued runs and scheduled/inbox jobs stay unavailable.

The authenticated, realm-bound `POST /api/chat-steer` accepts `agent`, `thread`,
`tid` (the exact ARMADA run), `request_id` and `message`. It cannot select a newer
run implicitly. Detached windows retain their original realm. Cancellation and
admission share the active-run lock. Admission writes a journaled receipt on the
original owner record before passing text to the process. Duplicate IDs return
that receipt; reuse with changed text/run is rejected. Input is bounded to 32,000
characters, 64 messages per run and one unacknowledged message at the adapter.

The process's `steer(id, text, callback)` synchronously admits to a queue and can
raise only before admission. Delivery is asynchronous. The RPC owner drains the
queue; a single bounded RPC writer owns stdin. A full or stalled pipe cannot
prevent the supervisor enforcing Stop or deadlines. Codex receives `turn/steer` with `threadId`,
`expectedTurnId` and text `input`, with no model, sandbox, approval or directory
overrides. Matching `result.turnId` confirms acceptance. Provider errors reject
the message; unsupported-method errors disable steering for that run. A queued
message is rejected on shutdown; a sent message without acknowledgement becomes
uncertain. A persistence error is surfaced, never converted into confirmed success.

Protocol reference: [Codex app-server, steer an active turn](https://learn.chatgpt.com/docs/app-server#steer-an-active-turn).
The installed CLI's generated `TurnSteerParams` and `TurnSteerResponse` schemas
were checked without provider inference. Synthetic subprocess tests exercise the
real transport and verify that the initial turn permissions remain unchanged.

Receipts live in the original user record's optional `steering` array with `id`,
`run_id`, `turn`, `text`, `ts`, `status` and `error`. Status is `pending`, `accepted`,
`rejected` or `uncertain`. This does not create a second user/assistant turn or
change edit/restart indexes. Future context and compaction include accepted
instructions; unconfirmed ones are explicitly labelled, and rejected ones are
excluded. The UI shows all outcomes without edit/restart controls for individual
steering messages. Poll payloads include only receipt IDs, statuses and errors.

The composer uses the same request ID after transport errors, with a 15-second
HTTP wait limit and explicit Check action. It never automatically replays a
message or queues it for a future turn. Acknowledgement clears only the exact
submitted draft; later edits survive. Browser reloads preserve unsent draft text
and show persisted receipt outcomes, but do not resume an in-memory pending
request automatically. After a crash, an unconfirmed instruction may have reached
the provider: the owner must review the result before resending. Steering is not
an undo or an immediate interruption guarantee.

Verification: `tests/test_steering.py`, `tests/steering_harness.js` and the native
`tools/thread_window_probe.py` exercise acceptance, refusals, exact-run binding,
duplicate IDs, recovery, model context, draft preservation, both windows and Stop.
The native probe uses only a temporary synthetic realm and simulated engine.
