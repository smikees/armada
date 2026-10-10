# Capabilities

## Which engines can use it

ARMADA lets each agent run on Claude, Codex or Gemini, and keeps its context when you change the
model. Capabilities don't all travel that freely, so the Capabilities page is arranged by
**reach**: which engines a capability works with.

- **Any engine** — skills, local extensions and open servers (a public MCP address). Every engine
  can use them; a connector still needs its own sign-in in each engine you use, shown on its row.
- **Claude only / Codex only / Gemini only** — connectors that live inside one provider's account
  (a Claude connector hosted by Anthropic, a ChatGPT app), and Claude Code plugins. Agents on
  other engines can't use them.

Use the switcher above the sections to show one reach at a time. Expand a card to see its
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

## Adding a connector

Choose **Add a connector**, then find a service.

- **An open server** (Notion, for example) is one connector for every engine. Connect each engine
  you use from its row; each signs in separately.
- **A service that lives in a provider's account** (Google Drive, Gmail, Calendar, Slack, GitHub)
  is added for one engine: choose **Claude** or **Codex**. ARMADA creates "Gmail · Claude" or
  "Gmail · ChatGPT app" and files it under that engine. Add both if agents on both engines need it.
  - **Claude:** complete sign-in in Claude's connector settings, then **Setup details → Link
    existing connection** to select its registration.
  - **Codex:** ARMADA links the ChatGPT app. Review permissions, install and sign in using the
    same account as Codex CLI, then **Recheck**.
  - **Gemini:** apps from Claude or Codex are not available to Antigravity. Add an open server for
    the service instead, if one exists.

**Import an existing connection** imports services already configured in an engine.
**Custom MCP server (advanced)** adds a service's HTTPS MCP endpoint; the Catalogue offers more.
A website address is not an MCP endpoint.

Each connector has one set of agent grants. **Setup details → Link existing connection** maps a
differently named registration in an engine to a connector of the same server. Choose the intended
service and account: matching names do not prove they reach the same service. ARMADA never copies
credentials between engines or into the realm, and never puts two different services on one row.
Adding a connector does not grant it to every agent; the coordinator's access follows its role.

A grant permits the tools that the selected engine actually exposes, including write operations
when available. Codex native apps are enabled only for granted connectors during normal tool
turns; other apps remain disabled, and ARMADA verifies the thread's callable app inventory before
sending the prompt. Inspectors and dry runs do not gain native apps.

## Accounts and changing engines

The connector picker includes Google Drive, Gmail, Google Calendar, Slack, GitHub and Notion. Other services
can be imported from an engine's directory or added by their trusted MCP endpoint. The list is
curated guidance, not a promise that a service is available on every provider plan.

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
