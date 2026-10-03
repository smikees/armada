# Settings

Three tabs: the realm you're in, you, and the app on this computer.
Use the Save and Cancel buttons beside each tab's settings. Cancel discards changes you have not
saved. Provider sign-in, Telegram connection, avatar uploads, and other command buttons apply when
you use them.

## Realm

- **Realm** — its name, icon, timezone, and the **workspace** folder its agents work in.
- **Model defaults** — the default model, thinking and verbosity for agents that don't set
  their own. **Set for all agents** confirms the selected combination, then saves it as the
  realm defaults and applies it to every current agent, including the coordinator. Capabilities
  and any job-specific model overrides stay as configured.
- **Agent-to-agent communication** — defaults for the [Inbox](inbox.md).
- **Notifications** — which events notify you (job failed, approval needed, …) and on which
  channel (desktop, Telegram); whether this realm may notify you while you're in another one.
- **Export** — a `.zip` of the realm next to its folder. Files that hold keys or passwords
  (`.mcp.json`, `.env`, key files) are left out, and the message says which.
- **Archive / Delete** — archive switches off all agent and system jobs, hides the realm from ARMADA,
  and retains its folder and history. Adding it back leaves its jobs off until you enable them. Delete
  moves the folder to the Recycle Bin. If you archive or delete the realm you are viewing, ARMADA
  opens another registered realm, or the welcome screen if none remain. Delete asks you to type
  the realm folder's name and waits for its active tasks to finish.

## User

**Your profile** — your name and a few facts. Agents know them through System memory.
Your avatar replaces "You" in threads.

## App

- **Version** — the version you're running; **Restart**, **Check for updates**, **Changelog**.
- **Root folder** — the one folder ARMADA works in. Every realm lives inside it.
- **Providers** — connect Claude, Codex, Gemini, or any combination. Sign-in opens on the provider's website;
  an existing CLI login can be reused. Agent model lists show connected providers.
  Disconnect stops new Armada calls without signing the CLI out or changing saved agent models.
  Reconnect restores access. See [OpenAI models](codex.md).
  Gemini uses Google's supported Antigravity CLI and reuses its saved Google login.
  Available Flash and Pro models come from your account's live catalogue; Gemini Auto selects
  the latest available Flash. You can select Gemini for an agent or override it for a job.
  Weekly quota appears in the Overview. Output verbosity controls the reply length.
  Gemini uses its native file tools for the recognized Anthropic filesystem extension, within
  Armada's approved folders; no separate filesystem sign-in or Google MCP setup is needed.
  Disabling that extension also removes these file tools on the next turn.
  Gemini supports file tools and explicitly assigned, provider-local MCP connectors; shell
  commands and sealed review turns are currently unavailable. A Claude or Codex connector login
  does not authorize that connector for Google. Tool access remains limited to the current
  agent folder and explicitly approved job folders. Web tools require the job's network grant.
  Claude sign-out appears as a dismissible notification once per app session. After closing it,
  sign-in remains available here; restarting Armada allows the notice to appear again.
- **Telegram** — talk to your agents from your phone: add your bot's token, message the bot, press
  link. Only your **one-to-one** chat with the bot is linked — never a group, where everyone could
  drive your agents. Send `/agentname your question` to ask a specific agent.
- **Notifications** — the delivery channels on this computer.
- **Appearance** — light, dark, or your system's colour mode, and the colour theme.
  Colour mode previews immediately on the settings page. Save keeps your choice; Cancel restores
  the saved appearance.
- **Advanced → Keep Armada open in the tray when closing the window** — on by default.
  Minimize or close the window to keep scheduled jobs running in the tray. Turn this off to
  make closing the window quit ARMADA and stop future scheduled runs until it opens again.
- **Advanced → Alexander** — choose his model and effort for all realms. Automatic uses
  Claude Opus 5.5 at Medium whenever Claude is connected, GPT-6 Sol at Medium with Codex only,
  or the latest Gemini Flash at Medium when only Gemini is connected.
  Choose **Automatic (default)** in either dropdown to restore its default behavior.
  An explicit model stays selected when its provider disconnects; reconnect or choose Automatic.
