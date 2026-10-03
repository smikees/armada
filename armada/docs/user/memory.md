# Memory

What your agents know before you say anything. Memory is plain text; short, specific entries
("I'm left-handed", "Taxes are filed in Spain") work better than long ones.

## Kinds of memory

- **The governing document** — the principles every agent is bound by, at the top of Memory and in Realm settings. It is called The Constitution (State), The Memorandum (Company), The Code (Ship), or The Covenant (Blank).
  **Read** shows them; **Edit** changes them for the whole realm.
- **Realm memory** — loads for every agent.
- **System memory** — written and kept up to date by ARMADA: who you are (from Settings → User),
  your computer, the realm and its team. You don't edit it; change the settings it comes from.
- **An agent's memory** — loads only for that agent. On the right of the Memory page, or on the
  agent's Memories tab.

## Things you'll do

- **Add a memory:** **+ Add memory**, for the realm or for one agent.
- **Edit or delete:** open the memory.
- **Find one:** the search box.

Agents are instructed to write only their own memories. For Claude, ARMADA also requests file-tool
restrictions on realm memory and other agents' existing folders. The current Codex integration
observes these memories but does not enforce that restriction. Shell scripts and MCP tools can
bypass the memory-specific rules, so these are not isolation guarantees.

When ARMADA observes changes during a run, it preserves the current files and adds a **Memory
boundary observation** to the thread. Expand it to inspect changed paths, reported write attempts
and any gaps in the scan. A change can come from another agent, your own edit or system upkeep;
the observation does not identify the writer. A reported tool attempt does not prove the write
succeeded. ARMADA never restores an earlier memory snapshot when a run finishes or fails.
