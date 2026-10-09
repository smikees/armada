# Provider connections for connectors

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
