# Your agents

## The team page

The page named after your realm's agents (Ministers, Executives, …) shows everyone as a card: role,
model, a short line from their character, their week strip, and counts of their goals, jobs,
memories and capabilities. **+ Appoint** adds someone — from a blank form, or by **reinstating** an
agent you retired earlier (their files were kept).

## An agent's page

Tabs across the top:

- **Threads** — talk to them. On the right: what's loaded into their context (and how big it is),
  which capabilities this thread has used, and the files it produced. The ⋮ on a thread renames,
  pins, archives or deletes it.
- **Goals** — the goals they own.
- **Jobs** — their scheduled work. Switch a job on or off, open it to edit, **+ New job**.
- **Inbox** — tasks other agents handed them, and how often they check (every minute, hour, day,
  or never) and who may hand them work.
- **Memories** — what only they know.
- **Artefacts** — files from their threads.
- **Capabilities** — what they may use.
- **Configure** — name, role, mandate, soul, tenets, model and effort, autonomy, colour, and
  advanced limits such as a per-run spending cap.

## Things you'll do

- **Change how an agent works:** edit the mandate (their brief) or soul (their voice) under
  Configure. Save keeps you on the page.
- **Pick a model:** Configure → Model and Effort. Higher effort thinks longer and uses more of your
  plan. The model chip beside the agent's name shows what they'll use.
- **Limit what they may do alone:** Configure → Autonomy.
- **Retire someone:** Configure, at the bottom (**Retire…**). Their folder is kept; you can
  reinstate them from **+ Appoint**. The coordinator can't be retired.

## Separate thread windows

Open a thread’s **three-dot menu** in the left-hand list and choose **Detach thread**, directly
below **Pin** (or **Unpin**). For the main thread, which is always pinned, Detach thread is first.
The window shows that thread's conversation and the same message, attachment, edit, restart,
rename and Stop controls. Its compact header groups the agent, realm, thread name and compaction
information beside the agent’s avatar and color crescent. Messages use text names without avatars.

Drag the bottom-right corner to resize the native window. You can also focus that grip with Tab
and use the arrow keys. The window has a broad, soft shadow, with subtle separation beneath the avatar and header.
The avatar sits closer to the header to leave more vertical room for chat, and its activity dot
is smaller. The window keeps a minimum size for the composer.

Both views render the same saved conversation throughout a reply: messages, Markdown, tool
activity, edits, message counts and compaction information. They keep refreshing in the
background. Messages and reply progress started in either view appear in the other; unsent
drafts stay local to each view. A selected passage or an unsaved message edit stays in place
until you finish reading or editing, then catches up with the latest saved content.

**Stop** cancels the active reply from either view, including a window that did not start it.
Both views show **Stopping…** while cancellation finishes. If cancellation fails, the window
shows the error and lets you try again. Losing the live connection does not stop the reply:
the view keeps checking the saved conversation and restores its progress and final answer.

Opening an already-open thread brings its window forward. Closing the window does not delete
the thread or cancel a running reply. Open it again from **Detach thread** to see the current
conversation and use Stop.

A companion stays with its original realm when you switch the main app to another realm.
If a thread is archived or deleted, its old window reports that it is unavailable.
In browser mode this opens a separate browser window; allow pop-ups for ARMADA if asked.

## Conversation history

Formulas render in both thread views, including fractions, subscripts and annotated equations.
Use `\(...\)` for inline math and `\[...\]` or `$$...$$` for a separate equation. Ordinary
prices such as $50 and $55 stay text, and formulas inside code examples stay literal. Unsupported
formulas show their original text. The renderer and fonts are bundled with ARMADA.

Long conversations are compacted into a summary while recent exchanges stay in the thread.
Messages added during summarization and unanswered questions are preserved. If you edit or
restart the conversation while a summary is being generated, ARMADA asks you to retry against
the current history. An interrupted summary update is recovered when the thread is next opened.

## Dictation and voice chat preview

For an agent using Codex, the message box has two audio controls:

- **Dictate** (microphone): keep speaking; the agent replies in text.
- **Voice chat** (waveform): keep speaking and hear the agent's replies aloud.

Both send finalized speech into the same thread automatically. Unlike the earlier draft-only
Dictate control, you do not need to press Send after each utterance. Existing typed drafts stay
untouched. Use **Mute** to pause input, or **End** to finish the audio session.

Switch using the other composer icon or the labelled **Dictation / Voice chat** action in the
voice panel. The microphone stays connected, unfinished speech is retained, and accepted work
continues. Switching to Dictation stops current spoken output immediately; future replies stay
in text. Switching back speaks subsequent completed replies, without replaying old text replies.

Both modes require microphone permission and use your existing Codex connection for speech.
Wait for the spinner and “Enabling voice mode, just a few seconds…” to change to **Listening**.
The microphone does not transmit until connected. ARMADA asks you to allow the microphone only
when the browser reports that permission is needed. Only the window that started the session
owns the microphone; either thread view can end it.

Voice is another way to use the same conversation. Each finalized spoken request enters the
normal agent runner, with the agent's configured model, effort, context and approved tools.
You see its actual progress, tool activity and final reply in both thread views. While the call
is open, Codex speaks the saved reply; long replies may be shortened for speech, with the full
answer retained in the thread. Brief audio acknowledgements are not task results and remain
silent. If output is blocked or no reply audio arrives, the panel offers **Enable sound**;
your saved answer and agent work are preserved.

**End** stops audio. **Stop work** cancels the agent's active and queued work. Ending a call,
closing its window or leaving voice mode does **not** cancel requests already accepted. Follow-up
spoken requests queue in order, so each sees the earlier result. The app must remain running,
just as for a typed request. Reopening the thread shows progress and lets you start another call.

The microphone meter reacts to actual sound. Words appearing live in the thread confirm speech
recognition. Mute clears the meter. Final transcription becomes a saved user message exactly once.
If the call ends before transcription finishes, already received text is kept with an
**Incomplete transcript** label and is not executed; review it and send the completed request.

This experimental preview uses your existing Codex sign-in for speech; the speech model is
separate from the configured agent model. ARMADA does not record audio. Your browser sends live
microphone audio to Codex. Audio usage is marked unconfirmed when Codex does not report it;
normal agent work has its usual separate accounting. The protocol was verified with Codex CLI
0.157.1; older versions or accounts without native voice support may fail to connect. There is
no API-key or paid-service fallback. One audio call can run at a time, for up to ten minutes.
A disconnected microphone window expires automatically; accepted agent work continues.

## Model and effort chips

The chip shows the model family (Opus, Sonnet, Haiku, …) and the effort level (low → max). A chip
that disagrees with what you set means the realm's default is being used — set it on the agent to
pin it.
