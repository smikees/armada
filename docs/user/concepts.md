# How ARMADA thinks

The words the app uses, and what each one means for you.

**Realm** — one team and everything it knows, kept as a folder on your computer. You can have
several (one for home, one for a project); the switcher at the top left moves between them. A realm
can be backed up, versioned or moved like any folder.

**Agent** — a member of the team, with a role (*mandate*), a character (*soul*), rules (*tenets*),
its own memory and its own threads. The app calls agents whatever your realm's template calls them
— Ministers, Executives, Mates.

**Coordinator** — the one agent who leads (Prime Minister, CEO, Captain). The coordinator can use
every capability in the realm and can hand work to the others; everyone else only uses what you've
granted them.

**Thread** — a conversation with an agent. **Main** is always there; add more to keep topics apart
("taxes" doesn't need to load your trading context). Old turns are summarised automatically so a
long thread stays fast.

**Memory** — what an agent knows before you say anything. *Realm memory* loads for every agent;
an agent's own memory loads only for them. *System memory* is written by ARMADA itself (who you
are, your machine, the team). The **Covenant** is the set of principles every agent is bound by.
See [Memory](memory.md).

**Goals** — what the realm is working towards, each with owners and a status. Goals load into
their owners' context, so agents know what they're for.

**Job** — work that runs on a schedule. An *agent job* is a prompt an agent runs; a *command job*
runs a command on your computer. Agents can **propose** jobs; proposals wait for you under
**Approvals** unless the agent's autonomy lets them through.

**Autonomy** — how much an agent may do without asking: *manually approve everything*,
*auto-approve routine actions*, or *skip all approvals*.

**Inbox** — agents hand each other **tasks** here: one agent asks another to do something, and it
runs on the receiving agent's next inbox pass.

**Capability** — a tool an agent can use: a *connector* (an outside service such as a broker or a
drive), an *extension* (a local tool), a *skill* (packaged know-how), or a *plugin* (a bundle of
those). The realm holds the list; agents get only what you **grant**. Each shows what it **runs**
and what it **can touch**, and a risk colour. See [Capabilities](capabilities.md).

**Artefact** — a file an agent wrote, or one you attached to a thread.

**Section** — a page you add to the top menu: a dashboard widget promoted to its own page, a local
mini-site, or a link.

**Usage** — every agent turn uses your Claude plan. The header shows your session and weekly
limits; the Usage widget shows who used how much.
