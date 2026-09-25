# Capabilities

The tools your agents can use — and, more importantly, where each came from, what it can reach,
and who may use it.

## Four kinds

- **Connectors** — outside services (a broker, a drive, a data feed) an agent reads from or acts on.
- **Extensions** — local tools that run on this computer.
- **Skills** — packaged know-how for a repeatable task.
- **Plugins** — bundles of the above, installed as one.

## Reading a card

- **from …** — where it came from (the MCP registry, a Claude plugin marketplace, Anthropic's
  skills, or something you wrote).
- **Runs** — *reads only*, *runs code here*, or *outside service*.
- **Can touch** — *files*, *network*, *shell*, *connectors*, *hooks*: what it can reach on your
  computer.
- **The coloured stripe** — the risk: red (**High risk**), amber (**Medium risk**), green (**Low risk**).
  It's decided by the riskiest thing the capability can do, not by its description. The legend on
  the right repeats all of this.

## Who may use what

The realm holds the list; **agents only use what you grant them**. Drag an agent from the right
onto a capability to grant it. The coordinator may use everything. When an agent needs something it
doesn't have, it asks in a thread and you approve or decline.

## Adding one

**Add a capability** has two ways in:

- **Search known sources** — the MCP registry, Claude plugin marketplaces you've added, Anthropic's
  skills. Add to the realm, then grant it.
- **Bring a link** — paste the address of a repository, package or server. An agent reviews it
  (it takes a couple of minutes, and uses your plan) and writes a report: what it is, who published
  it, what it can reach, what it found, and what it couldn't check. **Read the report before you
  add it.** The reviewing agent can only read the web: it can't run anything, touch your files or
  use your connected services, so a page written to trick it has nothing to trick it into.

## Keeping them current

**Check for version updates** asks Claude Code which installed plugins and servers have newer
versions; an update button appears on those cards. ARMADA also checks on its own every so often.
