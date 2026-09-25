# Settings

Three tabs: the realm you're in, you, and the app on this computer.

## Realm

- **Realm** — its name, icon, timezone, and the **workspace** folder its agents work in.
- **AI provider & defaults** — the default model, effort and limits for agents that don't set
  their own.
- **Agent-to-agent communication** — defaults for the [Inbox](inbox.md).
- **Notifications** — which events notify you (job failed, approval needed, …) and on which
  channel (desktop, Telegram); whether this realm may notify you while you're in another one.
- **Export** — a `.zip` of the realm next to its folder. Files that hold keys or passwords
  (`.mcp.json`, `.env`, key files) are left out, and the message says which.
- **Archive / Delete** — archive hides the realm from ARMADA and leaves the folder alone; delete
  moves the folder to the Recycle Bin.

## User

**Your profile** — your name, timezone and a few facts. Agents know them through System memory.
Your avatar replaces "You" in threads.

## App

- **Version** — the version you're running; **Restart**, **Check for updates**, **Changelog**.
- **Root folder** — the one folder ARMADA works in. Every realm lives inside it.
- **Engine** — whether Claude is connected on this computer.
- **Telegram** — talk to your agents from your phone: add your bot's token, message the bot, press
  link. Only your **one-to-one** chat with the bot is linked — never a group, where everyone could
  drive your agents. Send `/agentname your question` to ask a specific agent.
- **Notifications** — the delivery channels on this computer.
- **Appearance** — light or dark, and the colour theme.
