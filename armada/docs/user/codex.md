# OpenAI models with Codex

Existing agents can run on Claude, OpenAI or [Gemini](gemini.md) models while keeping their roles, memories and
conversation threads.

1. Choose the optional **Codex CLI** installation in the Armada installer, or use **Install Codex CLI**
   during setup. A label confirms whether the CLI is installed. Armada also detects the CLI bundled
   with the Codex desktop app on Windows.
2. In setup or **Settings → App**, press **Sign in (opens browser window)** beside Codex. Sign in on the provider's
   website in your browser; Armada detects completion. An existing CLI login can be reused.
3. Connect Claude too if you want models from both providers. **Disconnect** and **Reconnect**
   control Armada's access without signing other CLI applications out.
4. Open any agent's **Configure** tab and choose a model. OpenAI models are labelled **OpenAI**.
   An agent set to inherit follows the realm's default model. Jobs can override their agent's model.

Model lists come from the CLIs' catalogues. If Codex has not cached its model list yet, choose
**OpenAI · Codex default model**, or run Codex once and reload Armada. Changing a model affects
future turns; it keeps the agent's history and memory.
If a model does not support the selected thinking effort, the error lists its supported levels;
choose one of those levels in the agent's configuration.

Codex uses its own signed-in account. MCP connectors must be configured in Codex and granted to
the agent in Armada using the same server ID. Claude plugins are not transferred. Codex app and
plugin integrations are not yet offered through Armada. The workspace sandbox still applies to
files and commands.

The Overview header shows **Subscription limits** for Codex, Claude and Gemini,
each identified by its icon beside **Week** and **Session** rows. These limits cover
your whole account, including use outside Armada. Readings are cached for five minutes and refresh
in the background; the last reading stays visible while the next check runs. Percentages and
reset countdowns appear only when available. Missing or stale values leave a gray bar without
numbers; hover a row for the reason or the last reading's age.
Codex only shows windows reported by your account; API-key logins may not report subscription
limits. Token usage is recorded; API-equivalent estimates use the reported actual model and
standard text rates. They are comparison figures, not subscription charges. Unreported accounting
is marked separately rather than counted as zero.
Codex cannot enforce Armada's per-run dollar budget; clear that field to use Codex. Automatic
fallback models are currently a Claude feature. Setup and Alexander support Codex-only accounts.
Alexander defaults to GPT-6 Sol at Medium with Codex only; change this in **App → Advanced**.
