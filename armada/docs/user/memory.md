# Memory

What your agents know before you say anything. Memory is plain text; short, specific entries
("I'm left-handed", "Taxes are filed in Spain") work better than long ones.

## Kinds of memory

**Realm** is the default view. It shows the governing document and the memories for the current realm.

- **The governing document** — the principles every agent is bound by, at the top of Memory and in Realm settings. It is called The Constitution (State), The Memorandum (Company), The Code (Ship), or The Covenant (Blank).
  **Read** shows them; **Edit** changes them for the whole realm.
- **Realm memory** — loads for every agent.
- **System memory** — written and kept up to date by ARMADA: who you are (from Settings → User),
  your computer (Settings → Realm → Environment), the realm and its team. Saved environment values
  take precedence over detection. Use **Environment notes** for details such as an always-on host.
  ARMADA regenerates it when its source settings are saved, at startup and before agent runs.
  Its **Last regenerated** time is visible both on the Memory page and to the agent.
- **An agent's memory** — loads only for that agent. On the right of the Memory page, or on the
  agent's Memories tab.

Choose **App** to read **ARMADA system memories**, the instructions shared by agents in every
realm and by Alexander. Select a title to read it or choose **Go to file** to find its source on
disk. The same read-only view is available in **Settings → App**.

## Things you'll do

- **Add a memory:** **+ Add memory**, for the realm or for one agent.
- **Edit or delete:** open the memory.
- **Find one:** the search box.

Realm notes added here are UTF-8 Markdown files in `<realm>/memory/`. Every agent receives
their non-empty contents on its next turn. Private notes live in
`<realm>/agents/<agent>/memory/` and are supplied only to that agent. App memories are a separate
installation-wide source; **Go to file** reveals the active file.

Expand **Memories received** beneath a new reply or in a job result to see the titles, scopes,
source paths and regeneration times supplied for that run. These records are captured from the
same reads used to build its prompt; subsequent edits do not change them. A content fingerprint
is available by hovering over an entry. Older runs have no saved receipt, so ARMADA cannot
reconstruct exactly what they received. **Current context** in the thread sidebar estimates the
next reply from today's files.

System memory keeps the content-change date separately from the regeneration time. Unchanged
refreshes do not create history copies. Invalid UTF-8 settings are reported as an error and left
intact; ARMADA does not replace unreadable characters or regenerate from empty settings.

Agents are instructed to write only their own memories. For Claude, ARMADA also requests file-tool
restrictions on realm memory and other agents' existing folders. The current Codex integration
observes these memories but does not enforce that restriction. Shell scripts and MCP tools can
bypass the memory-specific rules, so these are not isolation guarantees.

When ARMADA observes changes during a run, it preserves the current files and adds a **Memory
boundary observation** to the thread. Expand it to inspect changed paths, reported write attempts
and any gaps in the scan. A change can come from another agent, your own edit or system upkeep;
the observation does not identify the writer. A reported tool attempt does not prove the write
succeeded. ARMADA never restores an earlier memory snapshot when a run finishes or fails.
