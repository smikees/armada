# Gemini models

Gemini is one of ARMADA's supported engines. Use it on its own or alongside other providers.
An agent can use a Google model in threads and
scheduled jobs while keeping the same role, memories and history.

## Connect Google

Install from the standalone ARMADA app. Windows can redirect installers launched by packaged
developer tools into their private app-data storage, making the CLI invisible to a normal
desktop launch. ARMADA records the installed executable path and reuses the CLI's saved login.

1. Open **Settings → App → Engines → Gemini** and install the CLI if needed. ARMADA's current
   Google adapter uses **Antigravity CLI** (`agy`); the card identifies the installed engine.
2. Choose **Sign in**, then complete the Google sign-in in the CLI and browser window.
   ARMADA reuses the saved login on future runs; you do not sign in for every task.
3. Once the card says **Signed in**, choose a Gemini model in **Realm settings → Model defaults**,
   an agent's configuration, or a job's **Edit** page. Jobs inherit the agent's settings unless
   you override them. You can keep Claude and Codex connected alongside Gemini.

The model list comes from your signed-in CLI account, so available models and quotas can vary.
Select a supported thinking level; output verbosity controls how much the agent writes back.
**Automatic** follows the engine's available default; recorded usage uses the actual model
when the provider reports it.

## Files and connectors

Grant capabilities to the agent in **Capabilities**. ARMADA refreshes grants for each turn and
job. Its bundled Anthropic filesystem capability enables Gemini's native file tools inside
the realm and explicitly approved folders; it does not need a separate MCP sign-in.

Remote connectors must also be configured and authorized for Google. A Claude or Codex
connector login does not establish a Gemini connection. Each connector card shows all three
engines separately, with a spinner during checks and a reason when unavailable.

The adapter uses a temporary project configuration for each invocation and cleans it up afterward.
It retains explicitly approved workspace roots, including parent folders, without adding
unapproved locations or global permission bypasses. Network access
requires the run's explicit grant. Shell commands, automatic fallback models, enforced dollar
budgets and sealed review turns are currently unavailable through this adapter. A job that needs
one of these should use a compatible engine; ARMADA explains the unsupported requirement.

## Usage and limits

The Overview header shows Gemini alongside Codex and Claude. Week and Session percentages appear
only for windows the provider reports; missing windows remain gray. Pending readings show dots.
These are account-wide limits, including activity outside ARMADA.
Readings are cached for five minutes and remain visible during background refreshes.

The Usage widget records tokens returned by the CLI. **API-eq** estimates their value at standard
API text rates, including reported cached tokens. It is a comparison figure, even for a free
account, and is not a subscription bill. Missing accounting stays unknown; a **+** beside a total
means some runs could not be counted. Long-context surcharges, cache-storage and tool fees are
not included in the base-rate estimate. Published rates are linked in [Overview](overview.md).

If a run fails, check its exact error in the thread or job output. **Not configured in Gemini**
means the connector is unavailable to this engine. **Sign-in required** means the CLI needs
authorization. A missing quota reading alone does not mean your account is disconnected.
