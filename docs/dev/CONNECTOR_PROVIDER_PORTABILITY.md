# Connector portability across engines

Assessment of the installed app, 9 October 2026. The subsequent source implementation is
documented in [Provider connections for connectors](CONNECTOR_PROVIDER_CONNECTIONS.md);
see [0.99.97 verification](RELEASE_0_99_97.md) for publication status.

## Current behavior

ARMADA does not select one exclusive provider for a connector. The realm's `enabled` flag
applies to the capability; agent grants and provider-specific connection/authentication checks
are independent. `connector_runtime.connection_snapshot()` checks Claude, Codex and Gemini
separately and returns their states for the same catalogue entry. Multiple providers may be
connected at once.

There are implementation and authentication limits:

- Claude subscription connectors are discovered in Claude's own inventory. Their existing
  session and connector authorization do not automatically establish a Codex or Gemini connection.
- Codex currently treats the realm capability's ID as its actual MCP server registration name.
  Names containing spaces, such as `claude.ai Google Drive`, fail server-ID validation, even
  when their underlying remote endpoint is portable. This is a missing provider-name mapping,
  not evidence of an exclusive-provider restriction.
- Codex endpoint discovery deliberately excludes Claude-only proxy identities, with an explicit
  portable public-endpoint translation for the IBKR registry entry. Gemini inspects its own
  `mcp_config.json` registration; an entry alone does not prove authentication or live tool access.

## External facts checked

[Google's Drive MCP setup guide](https://developers.google.com/workspace/drive/api/guides/configure-mcp-server)
documents the standard `https://drivemcp.googleapis.com/mcp/v1` Streamable HTTP server for
Antigravity, Claude and other MCP clients. It uses OAuth 2.0, with client-specific registration
and redirect settings. The Google-owned endpoint is therefore not inherently Claude-only.

[Claude Code's MCP documentation](https://code.claude.com/docs/en/mcp#use-mcp-servers-from-claudeai)
explains that claude.ai connectors reach Claude Code through its subscription login, and that
some Anthropic-hosted integrations require claude.ai's registered OAuth redirect. Copying their
URL or an existing credential is not a universal portability mechanism.

[Codex's MCP documentation](https://developers.openai.com/codex/mcp) describes its own remote
MCP configuration and OAuth flow. Configuring the same portable backend independently in
each supported client is the interoperable approach; registering one does not inherently
disconnect another. Live support still needs verification for each service/client combination.

## Recommended CX

Keep one logical connector card and one owner-approved agent grant. Associate independently
configured provider registrations with that card rather than requiring duplicate cards or
renaming the existing Claude registration. Store stable provider-specific server IDs separately
from the displayed name and logical capability ID.

Show each provider's actual state and action: Connected, Sign in, Not configured, Unverified,
or Unavailable through this integration, with the relevant reason. An unsupported imported ID
must not be presented as merely unsigned-in, and a realm's saved Connected label must not
override live provider checks. Connecting another provider must preserve working registrations.

Before an agent/job model changes, resolve job → agent → realm inheritance and flag required
connectors unavailable to the resulting provider. In particular, an agent model change does not
replace a job's explicit model override; that distinction should be visible where the user acts.

## Workarounds and longer-term options

For portable MCP services, configure and authorize the same backend independently in each
engine. ARMADA also needs a matching approved provider registration/name mapping before it can
admit that server into a turn. Claude OAuth storage must not be copied to another engine.

For a provider-only integration, a supported independent MCP/API integration can provide the
same service where available. Another current option for data-only work is a fresh, authenticated
retrieval followed by exact captured local artifacts; other engines review those approved files
instead of claiming direct live connector access. Freshness/provenance remain explicit.

A future ARMADA-owned MCP gateway could authenticate independently to supported services once,
then expose scoped tools to the engines. That is additional credential/authorization and tool
policy infrastructure. It would not automatically make every provider-owned integration portable.
