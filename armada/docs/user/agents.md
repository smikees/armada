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

- **Dictate** (microphone): speak a message, then choose **Done** to insert it at the cursor.
  Review or edit the draft and press **Send** when ready. The agent replies normally in text,
  using its selected model and capabilities. **Cancel** discards the recording's text and
  keeps your existing draft. Dictation never sends a message or plays an agent reply.
- **Voice chat** (waveform): speak and hear spoken replies in a hands-free conversation.

Both require microphone permission and use your existing Codex connection in this preview.
Dictation uses that live connection for speech recognition, so it consumes voice usage. It
does not share the agent's context or thread history with the speech session. Your speech
transcript appears as an editable draft; it is not added to conversation history until sent.

Choose **Voice chat** beside the message box. Allow microphone access to
start a hands-free conversation. **Mute** switches off microphone input while replies remain
audible; **End call** closes it from either thread view. Only the
window that started the call owns the microphone; the other view can end the call.

This proof of concept uses Codex's native realtime voice model and existing Codex sign-in.
It carries the agent's core context and recent conversation, but the speaking model is separate
from the agent's configured text model. It is **conversation only**: no files, shell, web,
connectors, messages or jobs. End voice to ask for actions in normal chat.

Final spoken transcripts are saved in the same thread as typed messages and appear in both
views. ARMADA does not record audio; your browser sends live microphone audio to Codex.
Voice usage is marked unconfirmed when Codex does not report accounting. The experimental
protocol was verified with Codex CLI 0.157.1; older versions or accounts without native voice
support may fail to connect. There is no API-key or paid-service fallback.

One call can run at a time, for up to ten minutes. Closing or leaving its microphone-owning
window ends voice; a disconnected window expires automatically. This differs from an ordinary
typed reply, which can continue after its window closes. Reopening the thread keeps the saved
transcript and lets you start a new call.

## Model and effort chips

The chip shows the model family (Opus, Sonnet, Haiku, …) and the effort level (low → max). A chip
that disagrees with what you set means the realm's default is being used — set it on the agent to
pin it.
