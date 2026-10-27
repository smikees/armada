# Capabilities

The page opens immediately with a loading indicator while its local inventory is prepared.
Drag an agent onto a capability to give access, or remove its chip to revoke access. The saved
change updates that card in place, preserving your filters, scroll position and expanded panels.
Granting access does not sign the agent's provider into a connector; its connection status stays
separate.

Press **Ctrl+F** anywhere in ARMADA to find visible text in the current section. The search box
opens at the top right, below the main menu. Matches are highlighted; **Enter** moves forward,
**Shift+Enter** moves back and **Escape** closes it. The results update as content arrives.
Hidden tabs, collapsed content and unsent editor drafts are excluded; expand a section to search it.

## Which engines can use it

ARMADA lets each agent run on Claude, Codex or Gemini, and keeps its context when you change the
model. Capabilities don't all travel that freely, so the Capabilities page is arranged by
**reach**: which engines a capability works with.

- **Any engine** — skills, local extensions and open servers (a public MCP address). Every engine
  can use them; a connector still needs its own sign-in in each engine you use, shown on its row.
- **Claude only / Codex only / Gemini only** — connectors that live inside one provider's account
  (a Claude connector hosted by Anthropic, a ChatGPT app), and Claude Code plugins. Agents on
  other engines can't use them. A connector set up in Claude stays Claude only unless it also has
  a public address another engine can use; to use the same service with Codex, add it for Codex.

The search box sits on its own line; below it, the engine switcher (All, Any engine, Claude,
Codex, Gemini) shows one reach at a time, followed by the agent, type, source and risk filters. Expand a card to see its
**Works with** strip: which engines can use it now, and why the others can't.

**One engine at a time.** Some services allow only one AI platform per account: connecting
another disconnects the previous one (Interactive Brokers works this way). Such a capability shows
**One engine at a time · on Claude** (or whichever engine it's on). Agents on other engines aren't
offered it. To use it elsewhere, choose **Move to …** under Works with: ARMADA shows which agents
gain and lose it before saving. Then sign in from the new engine; the service disconnects the old
one itself. For a service ARMADA doesn't recognise, turn on **Advanced → One engine at a time**.

Agent chips under **Available to** say when an agent's engine can't use the capability, and the
agents list marks each agent's engine and how many of its grants that engine can't use. An agent's
own Capabilities tab opens with the same summary.

**Changing an agent's model.** Under the model field, a line says what the agent can still use on
that model's engine, and updates as you choose. Saving a change that loses capabilities asks you to
confirm, listing each one and why. During a run, anything granted but unavailable on the run's
engine is withheld and named to the agent, so a job that needs it says exactly why.

## Adding a capability

Open **Add a capability** and tell Alexander what you need, in your own words: "a PDF viewer for
Codex", "connectors already set up in Claude Code", "skills I made in other realms". He searches
the sources switched on under **Sources** and lists what is most likely to help, with one or two
lines on what he found. Each result shows which engines can use it, where it came from, and
whether you already have it. A search takes from a few seconds to under a minute and runs on
Claude Opus through your Claude account.

Paste a GitHub repository link in **Search** to review it directly, even with all search sources
off. You can also paste a link under **Got a link?**.

Reviews keep running when you navigate elsewhere. Return to **Add a capability** to see their
progress or saved reports; the latest 20 are shown. Closing ARMADA interrupts unfinished reviews,
which show **Retry review** after reopening rather than spending another agent turn automatically.
Completed reports are stored locally and survive app restarts.

Before reviewing again, ARMADA checks the GitHub commit or the contents of a local skill,
including its scripts. An unchanged verified version reuses the saved report; a changed version
or review protocol requires a new review. For other links, or when version verification is
unavailable, ARMADA preserves the report but does not claim it is current or reuse it for a new
review. Reviewing or restoring a report never enables a capability by itself.

**Sources** come in two groups, and you can switch any of them off:

- **What you have:** this realm, your skills in other realms, what Claude Code already has set up,
  and plugins already installed in your ChatGPT account.
- **Where to find more:** engine connectors (Gmail, Google Drive… added per engine), ChatGPT's
  plugin directory (read through Codex; Codex only), Claude plugin marketplaces, Anthropic's
  skills, and the MCP registry (open to anyone and unreviewed).

What a result offers depends on what it is:

- **Review**: nothing new is added straight from a result. A link is read by an agent, as with any
  link you paste; one of your own skills is checked from its files. **Add to realm** appears on
  the review.
- **Add for Claude / Add for Codex**: an engine connector. Then press **Connect** on its row:
  for Claude, add the service in Claude's connector settings and ARMADA links it; for Codex,
  ARMADA finds the ChatGPT app.
- **Add for Codex** on a ChatGPT plugin: creates "<plugin> · Codex". Install it in ChatGPT
  (**Open in ChatGPT**) if you haven't, then press **Connect** on its row.
- **Bring in from Claude**: brings what Claude Code already has into this realm.
- **In this realm**: already here; **Go to skill** (or connector, plugin, extension) shows it on
  the User tab.

Alexander can only show what a source returned; he can't install, grant or review anything.

**Got a link?** In the panel beside the search, paste a repository, package, skill or an MCP
server's address and choose **Review**. An agent reads it and reports before **Add to realm** is
offered; an MCP server's address is added as a connector for every engine, each signing in
separately. **Browse for yourself** below it links to Claude's and ChatGPT's directories,
skills.sh, the MCP registry and others; paste a link back from any of them.

## Accounts and changing engines

Engine connectors cover Google Drive, Gmail, Google Calendar, Slack, GitHub and Notion. Other
services can be brought in from Claude or added by their MCP address. The list is curated
guidance, not a promise that a service is available on every provider plan.

Give a service an optional **Personal** or **Work** label to distinguish connections. These are
owner-provided labels, not verified account identities. Confirm the account during provider
sign-in. Separate accounts need separately addressable registrations in the engine; ARMADA
does not create a second account session by renaming a connection. A registration can belong
to only one realm capability, so two labels cannot accidentally grant the same connection twice.

**Setup details → Unlink this engine** removes only that realm binding. It preserves other
engine connections and agent grants, and does not sign out other clients. Re-link explicitly
to restore access. Revoke provider credentials in the provider's own settings when needed.

Agent chips show their default engine's current connection status. Jobs can override that
engine. The model warning is a configuration check, not a live permissions test: every run still
checks the actual connections, and ARMADA never reroutes a connector call to another engine or account.

## Asking your agent to connect

In a normal chat, ask your agent to check or connect a capability already approved for it.
The agent can start the engine’s supported connection flow; you complete browser/provider
sign-in yourself. Claude may open its own sign-in terminal as well as the browser. Credentials
stay with the provider. After sign-in, ask again: newly connected data tools load on the next turn.

An agent cannot add an arbitrary server, change its endpoint, enable a disabled realm capability
or grant itself access through these tools. It can request your approval for an existing realm
capability; a coordinator can request access for another agent. Scheduled jobs, inspectors and
dry runs do not receive these connector setup tools.

Missing or signed-out connections do not end a conversation. Their tools are withheld, and the
agent can continue unrelated work. If the requested task needs the unavailable connection, the
agent must explain that it could not complete it; it must not invent data or claim a successful
read or delivery. Malformed permissions and ungranted tools still stop a turn for safety.

## Connection status and actions

Connectors show separate Claude, Codex and Gemini status badges. A spinner means the engine's
check is pending; a saved connector entry alone is not proof of a working connection. Authorize
each engine you intend to use. The bundled filesystem capability uses Gemini's native scoped
file tools. See [Gemini models](gemini.md) for setup and current tool limitations.
Checks finish independently for each engine; a slow check does not hide another engine's result.
A timed-out check is marked unverified with a reason, rather than left spinning. Recheck retries
the live connection. The legend starts open and remembers whether you last left it open or closed.

Expand a connector's **Connections** section to see separate Claude, Codex and Gemini rows.
Each row shows its status, reason and relevant action:

- **Connect / Sign in** starts that provider's supported authentication flow. Preparation and
  CLI errors are shown separately. **Open sign-in page** appears when the CLI supplies a URL,
  so you can open it if the browser did not appear. Codex registers reviewed direct MCP
  endpoints; Claude can register a direct endpoint or authenticate an existing registration.
  Gemini registers the endpoint through Antigravity CLI. Its **Open sign-in controls** action
  opens `/mcp`; select the server and choose Authenticate, then finish in your browser.
- **Set up / Setup details** shows instructions for that provider, including a copyable
  Codex or Antigravity configuration and service-specific OAuth guidance where needed.
  **Copy configuration / Copy setup template** copies the displayed text and confirms success.
  A template's placeholders must be replaced before use. No copy button appears for empty text.
- **Recheck** checks only the selected provider. An error includes a recovery action.
- **Setup details** also displays verified tool names when the CLI exposes them. A connection
  status is not a promise that every service operation exists or has the required permission.
- **App settings** takes you to a provider that needs installation, sign-in or reconnection.

Several engines can connect to the same open server at once, unless it is marked one engine at a
time. Connecting another engine does not replace your working connection or change which agents
have access. Claude-managed
integrations without a reviewed portable endpoint show **Unavailable through this integration**,
with options to use a compatible integration. A provider's **Registered · unverified** state
means its configuration exists; it does not prove authorization or live tools. Gemini currently
uses this state because ARMADA cannot verify its live connector health.

Advanced direct Google MCP endpoints have different OAuth requirements from the providers'
native apps. If you deliberately configure one, follow its service-specific setup instructions.
These requirements do not apply to the native Codex Google Drive plugin described above.

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

Bring-a-link reviews currently use Claude Code and its plan limits. A provider refusal, such as
a session limit, shows Claude's explanation and reset time when supplied. Wait for the stated
reset or resolve the reported provider issue, then choose **Review** again. A failed review
does not add or install the capability.

## Keeping them current

**Check for version updates** asks Claude Code which installed plugins and servers have newer
versions; an update button appears on those cards. ARMADA also checks on its own every so often.
This action manages Claude-owned plugin installations. It does not make Claude a prerequisite
for using Codex or Gemini; each capability's engine badges show where that capability is available.
