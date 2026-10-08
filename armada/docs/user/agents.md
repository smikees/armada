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

Long conversations are compacted into a summary while recent exchanges stay in the thread.
Messages added during summarization and unanswered questions are preserved. If you edit or
restart the conversation while a summary is being generated, ARMADA asks you to retry against
the current history. An interrupted summary update is recovered when the thread is next opened.

## Model and effort chips

The chip shows the model family (Opus, Sonnet, Haiku, …) and the effort level (low → max). A chip
that disagrees with what you set means the realm's default is being used — set it on the agent to
pin it.
