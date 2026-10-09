# Capabilities

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
  endpoints; Claude authenticates its existing registration.
- **Set up / Setup details** shows instructions for that provider, including a copyable
  Codex or Antigravity configuration and service-specific OAuth guidance where needed.
  **Copy configuration / Copy setup template** copies the displayed text and confirms success.
  A template's placeholders must be replaced before use. No copy button appears for empty text.
- **Recheck** checks only the selected provider. An error includes a recovery action.
- **App settings** takes you to a provider that needs installation, sign-in or reconnection.

Several providers can connect to the same service at once. Connecting another provider does
not replace your working connection or change which agents have access. Claude-managed
integrations without a reviewed portable endpoint show **Unavailable through this integration**,
with options to use a compatible integration. A provider's **Registered · unverified** state
means its configuration exists; it does not prove authorization or live tools. Gemini currently
uses this state because ARMADA cannot verify its live connector health.

Google Drive's direct MCP endpoint is portable, but each client needs compatible OAuth setup.
Google Drive rejects automatic client registration. Until Codex has its own pre-registered
Google OAuth client ID, its row shows **Setup required**, with instructions and a template.
Create and configure that OAuth client using the service guide and Codex's supported client
options; register the exact callback URL printed by Codex. Copying the template alone does
not register or authorize a client. Then choose **Sign in** and **Recheck**.
See [Google's setup guide](https://developers.google.com/workspace/drive/api/guides/configure-mcp-server).
Existing Claude credentials are never copied into Codex or Gemini.

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
