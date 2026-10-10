# Provider connections for connectors

## Service discovery and connection design

The Add dialog follows the existing ARMADA capability UI and the token contract in
[DESIGN_TOKENS.md](DESIGN_TOKENS.md). The flow is: find a service, read its engine-specific
guidance, optionally label the account or workspace, add or import, then manage each engine's
connection independently. This implements the [product specification](../../SPEC.md): one
provider's connection does not authorize another provider's connectors.

The curated service list contains Google Drive, Gmail, Notion, Google Calendar, Slack and
GitHub. Search matches names and aliases (including Docs, Sheets and Slides under Google
Drive); category and engine filters narrow the list. Selecting a service shows its description
and separate Claude, Codex and Gemini guidance. The filter describes an available integration
route, not verified sign-in or permission to perform every advertised action. No results
disables Add and points to import or custom MCP setup. Provider-directory links and Catalogue
provide discovery beyond this small list.

“Find a service” is the default. “Import an existing connection” selects one engine and its
current inventory. “Custom MCP server (advanced)” accepts a service-provided endpoint and
offers Notion's official preset. Notion discovery also creates this remote MCP configuration;
the other listed services create native-provider entries. Adding an entry does not complete
sign-in. Setup details on each expanded connection row hold linking, unlinking, configuration
and provider guidance; connection actions and Recheck remain independent per engine.

The surface reuses ARMADA's heading/body fonts, token palette, compact fields, capability
disclosures and primary/secondary buttons. Service rows use separators and a subtle accent
selection fill, with a visible keyboard focus outline. The modal is capped at 600px/92vw and
90vh; its form body scrolls while the action footer remains visible. The service list has its
own 170px scroll limit. At widths up to 600px, filters stack and padding reduces. Search gains
focus on opening, Tab stays within visible controls, Escape closes, and closing restores the
opener's focus. Selection guidance and save feedback use live/status regions. After a successful
save, a session-storage marker returns the reloaded page to the affected connector.

### Persistence and limits

- The optional label is trimmed, limited to 80 characters and rejects control characters.
  It is owner-entered metadata, never a verified account identity. New entries save
  `account_label`; explicit engine bindings can save `connection_labels[engine]`, which takes
  display precedence. Service-created names include the label when supplied.
- Entries persist in `realm.json` under `toolkit.connectors`, with `service_id` where recognized.
  Engine bindings retain registration identity or native app ID and any shareable endpoint.
  Credentials remain with the engine. Labels do not select accounts or prove matching accounts
  across engines; multiple accounts require distinct connections supported by that engine.
- Unlink writes a disabled binding for that engine and removes its connection-specific label.
  It leaves other bindings, agent grants and the engine's saved sign-in intact.
- Native Claude/Codex apps cannot be reused by Gemini. A compatible MCP registration is still
  required there, and configured Gemini registrations remain unverified. Google OAuth and real
  service reads/writes require service-specific acceptance; UI review is not that evidence.

The scoped UI review disposition is **Ship**, with desktop/mobile captures at
`build/connectors-desktop-final.png` and `build/connectors-mobile-final.png`. This documents
the existing ARMADA extension; the global token source remains unchanged.

## Native provider connectors and registration bindings (0.99.99)

The default Add flow offers provider connectors, starting with Google Drive and Gmail. Creating
an entry requires no provider account. Claude opens its native connector settings and the owner
links a discovered registration; Codex resolves its native plugin metadata, binds its app ID,
and opens the provider's installation/consent page. ARMADA does not silently accept installation
interstitials or OAuth consent. Third-party integration services and a bespoke Google REST bridge
are not involved. Gemini remains explicitly unsupported for these native apps unless the owner
links a compatible MCP registration.

Codex `provider_bindings.codex` can contain an `app_id` (the `connector_` or `asdk_app_` family) instead of an MCP server.
The logical grant resolves to `CapabilityPolicy.allowed_app_ids`, never the whole `codex_apps`
MCP namespace. App-server turns keep plugins, hooks and other ungranted features disabled.
`apps._default.enabled=false` plus explicit invocation-only disables for installed/configured
apps prevent ambient grants. Only selected app IDs are enabled; existing per-tool rules remain.
After `thread/start`, `app/installed(threadId, forceRefresh=true)` must report exactly the granted
callable set before `turn/start`. Missing/extra apps or unsupported protocol fail closed. App
mentions select those native tools. Managed inspector/dry-run turns and no-tool calls keep apps off.

This protocol was verified against installed CLI-generated JSON schemas and a real ephemeral
thread on 2026-10-09 (`tools/native_app_scope_probe.py`): one native app callable, all other apps
blocked, no model turn, no service content reads, no saved configuration changes. The installed
CLI treats quotes in `-c` dotted keys literally; app IDs must be unquoted validated segments.
`app/read`/plugin metadata is not authorization evidence. Native Google Drive metadata confirms
write-capable Docs/Sheets/Slides workflows, but Google OAuth and document writes remain owner
acceptance checks after provider sign-in.

Primary references: https://learn.chatgpt.com/docs/app-server and
https://learn.chatgpt.com/docs/plugins . These supersede earlier assumptions below that Codex
connectors always require a separately registered remote MCP server.

### Remote MCP bindings

The connector entry is a logical realm capability. `provider_bindings` maps engine names to
`server_name` and an optional shareable `endpoint`. Import reads that engine's inventory and
saves only these fields. Automatic import retains only recognized public endpoint paths;
unknown proxy paths may contain credentials and are omitted. Private URL queries, headers, OAuth settings, environment variables and
local commands are not copied into the realm. New remote connectors can instead have an
explicit owner-selected `mcp_url`. Imported integrations are not assumed portable.

`connector_registry` validates and atomically saves additions and links under the realm lock.
It refuses another capability already claiming that engine registration. Execution policy
translates grants and denials through the same mapping; a denied alias wins. Newly linked
connections require their actual engine registration at turn startup; adapters verify public
endpoints and reject missing/disabled registrations. Provider-private endpoint contents stay
private, so only registration identity can be checked for those links.

The Add dialog supports remote endpoints and selective imports from all three engines. Each
connection row can link an existing registration, connect, sign in, inspect setup and recheck.
Claude uses `mcp add --scope user --transport http` and `mcp login`; Codex uses `mcp add --url`
and `mcp login`. Gemini uses `agy mcp add --type http`, then opens its interactive `/mcp` menu
on an explicit sign-in action. The installed CLI help was checked on 2026-10-09. Gemini's saved
registration remains unverified because it has no supported noninteractive tool-health command.

Codex's granted new connections receive `default_tools_approval_mode="approve"` as an
invocation override only. Explicit per-tool policy still wins. Ungranted servers stay disabled;
shell approvals stay `never`. This fixes real tool calls being rejected despite a realm grant.
Its live startup check exposes tool names, and unavailable required registrations fail the turn.

The Google-owned REST bridge experiment is not part of this implementation. Its source is
preserved in an ignored local build archive, and its host credentials are untouched. Official
Google MCP endpoints remain advanced custom setup, separate from native provider apps. No
third-party integration is installed or authorized automatically. Notion's official remote MCP is also listed as a non-Google example.

Sources: [Claude MCP](https://code.claude.com/docs/en/mcp),
[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
[Antigravity MCP](https://antigravity.google/docs/mcp),
[Google MCP](https://developers.google.com/workspace/guides/configure-mcp-servers),
[Notion MCP](https://developers.notion.com/guides/mcp/get-started-with-mcp).

Opt-in acceptance: `tools/connector_provider_probe.py --output build/connector-probe.json`
registers three unique loopback servers, lets Claude create a synthetic document, Codex read
and edit it, and Gemini read the result. It removes only its own registrations afterward.
This validates actual CLI routing and tool execution; it does not validate Google OAuth or a
real Google Doc. Never substitute that synthetic result for service-specific acceptance.

## Historical remote-MCP implementation (0.99.97–0.99.98)

The following describes the earlier remote-MCP route. Native apps above supersede its
Google client-registration requirement for users choosing the native integration.
Prepared for 0.99.97; see [release verification](RELEASE_0_99_97.md) for publication status.

0.99.98 follow-up: [verification](RELEASE_0_99_98.md). Connector sign-in no longer discards
CLI failures or assumes a browser opened. Setup copy now works with displayed Codex templates
and a clipboard fallback; empty copy controls stay hidden.

## Release changes

- Expanded connectors have separate Claude, Codex and Gemini connection rows, with status,
  reasons, setup instructions, sign-in where supported and independent Recheck controls.
- A connector's agent grant is shared; each provider maintains its own registration and
  authentication. Configuring one provider never disconnects another.
- Imported names containing spaces now have stable CLI-safe registration names. Existing
  valid names stay unchanged, and grants and revocations apply to the mapped registration.
- Unavailable integrations and unverified registrations are explicit, with recovery actions.

## Implementation

`connector_runtime.connection_snapshot()` preserves its flat state fields and adds per-provider
`details` with `state`, `reason`, `action` and the CLI registration identity. A `provider` query
parameter limits forced refresh to that provider. Browser request generations also live per
provider, so a delayed full-page check cannot overwrite a newer provider-specific result.

`POST /api/connector-action` resolves the realm connector by its logical identity. Setup is a
read-only, credential-free response. Connection actions require an enabled realm connector
and a connected provider. The client cannot supply a command, endpoint, registration name or
credential. Claude's existing CLI registration is looked up before `claude mcp login`; Codex
uses the reviewed direct endpoint and its existing registration/authentication flow. Gemini
uses guided configuration because the installed Antigravity client lacks an equivalent verified
noninteractive OAuth action.

`engine.mcp.registration_id()` preserves valid names and creates a readable, SHA-256-suffixed
name for invalid display names. `capabilities.provider_policy()` translates owner-approved
grants at launch, including revocations and disabled aliases. It does not infer grants from the
provider's ambient inventory. Tool-use discovery recognizes these aliases to avoid duplicate
connector cards. Claude's existing cloud/display registration remains admitted through the
same logical grant.

Google Drive's exact published endpoint is allowed for portable setup. Other Claude-managed
proxy identities remain unavailable outside Claude unless a reviewed portable endpoint mapping
exists, such as the existing IBKR registry mapping. A conflict or disabled provider registration
is never overwritten. Provider OAuth client registration may still require service-specific setup.

`connector_login.begin()` supervises an owned CLI process for at most 300 seconds and observes
its stdout. Preparation, an issued authorization URL, failure and completed login are distinct
states. Only HTTPS URLs without embedded username/password and with OAuth code/client parameters
is eligible for the fallback link; transient URLs remain in memory and are removed when the
attempt ends. Error diagnostics strip URLs and OAuth secrets. Duplicate clicks reuse the active
attempt, shutdown cancels owned processes and completed attempts expire after 15 minutes.
Completion invalidates the provider's earlier health check; Connected still requires a live check.
Provider conflicts, disabled connections and realm grants retain precedence over login progress.

Google Drive currently rejects dynamic OAuth client registration. ARMADA checks only the presence
of Codex's own non-placeholder `mcp_servers.<id>.oauth.client_id` in the configured `CODEX_HOME`
before launching its Google sign-in. Without it, Set up replaces a misleading Connect action.
The owner must create the compatible Google OAuth client and configure Codex's supported
client options, registering the exact callback URL provided by Codex. ARMADA creates no OAuth
credentials, never copies Claude authorization and provides only a placeholder TOML template.

Copy controls honor `hidden` despite shared button styling. Clipboard writes reject empty text,
try the browser Clipboard API, then a selected textarea copy for hosts without that API. The
fallback restores focus and text selection. Success is reported only after the copy operation
succeeds; failures provide manual-copy guidance without overwriting the setup instructions.

Gemini checks the same global `mcp_config.json` read by `GeminiEngine`. It verifies a matching
`serverUrl` and enabled registration, but always labels that evidence `configured`, not `ready`.

## Verified references

- [Claude MCP setup and CLI authentication](https://code.claude.com/docs/en/mcp)
- [Codex MCP configuration and OAuth](https://developers.openai.com/codex/mcp)
- [Antigravity MCP configuration](https://antigravity.google/docs/mcp)
- [Google Drive MCP and client-specific OAuth setup](https://developers.google.com/workspace/drive/api/guides/configure-mcp-server)

The installed Claude CLI's `mcp --help` and `mcp login --help` confirm that login accepts a
configured HTTP/SSE or claude.ai connector name. The installed Codex CLI's `mcp --help`
confirms separate add/list/login commands. No provider connection was changed during validation.
