# Settings

Three tabs, from left to right: **App**, **Realm**, **User**. App opens first unless
a link or your remembered tab selects another.
Use the Save and Cancel buttons beside each tab's settings. Cancel discards changes you have not
saved. Provider sign-in, Telegram connection, avatar uploads, and other command buttons apply when
you use them.

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
- **Appearance → Fonts** — choose separate font families for headings and body text (each
  option in the list is shown in its own face), and a
  **Default size** from 10 to 26 px (initially **13 px**). Headings and smaller labels scale
  proportionally; icons and images keep their dimensions. The size selector previews immediately;
  Save sets your default and Cancel restores the saved size. Font-family changes preview in
  the sample box and apply throughout the app after Save.
  **Ctrl+** (or **Ctrl=**) increases the current size by 1 px, **Ctrl−** decreases it by 1 px,
  and **Ctrl+0** restores your saved default without changing your font families. Shortcut
  adjustments never replace that default. Numpad shortcuts also work.
  Shortcuts save immediately, preserve conversation drafts and apply across realms and
  Alexander's window. If a save fails, ARMADA explains the failure and restores the saved size.
- **Advanced → Keep Armada open in the tray when closing the window** — on by default.
  Minimize or close the window to keep scheduled jobs running in the tray. Turn this off to
  make closing the window quit ARMADA and stop future scheduled runs until it opens again.
- **Advanced → Alexander** — choose his model and effort for all realms. Automatic uses
  an available connected engine according to ARMADA's defaults. Any supported provider
  can be used on its own; Alexander's model choice does not set your agents' defaults.
  Choose **Automatic (default)** in either dropdown to restore its default behavior.
  An explicit model stays selected when its provider disconnects; reconnect or choose Automatic.

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

New teams choose their initial model from the engines connected during setup, using
that ARMADA release's preferences. If your provider offers models the release does
not recognize, ARMADA uses the provider's default. Agents inherit this realm default
until you choose their own model. Alexander's model is independent. Updating ARMADA
does not replace models you have already chosen.

## User

**Your profile** — your name and a few facts. Agents know them through System memory.
Your avatar replaces "You" in threads.

## Restarting and updating

The new-version ribbon has a **×** button to dismiss that version's notice. It
stays dismissed across page navigation and polling; a later version appears again.
Dismissal leaves the downloaded update ready and available in Settings. Active
update progress and restart errors remain visible.

Only one ARMADA desktop/server instance can run under your Windows account. Opening it
again brings forward the existing window, including from the tray. Changing realms does
not create another app instance. The scheduler is an internal background process.

**Restart to update** pauses new task admissions and waits for active work across all
realms. The banner distinguishes active conversations/jobs from scheduler shutdown and
restart. An idle scheduler is not a running job. If an activity record cannot be read,
the update explains the error rather than claiming that a job is running.

An older copy still holding the installation open is shown with its process ID.
**Postpone update** resumes task admissions and starts the scheduler if needed;
the downloaded update stays ready for later.

Before closing, ARMADA starts an independent restart monitor and waits for its
acknowledgement. The monitor waits for the old app to exit, launches the checked
update, and verifies the new version, loaded desktop and scheduler (when autostart
is enabled). A startup failure has a specific message and a saved startup log.
It does not force-close running jobs or claim success merely because a process started.

The restarted window must authenticate through its actual browser session before
scheduled work resumes. If an updated package cannot start, ARMADA restores its
verified previous code when it is safe to do so, preserves your realm data, and
records the failure. The failed version is not installed again automatically.
An unavailable provider or exhausted subscription does not trigger rollback.

Restart preserves your page, thread, window placement and unsent text. Update
preparation checks disk space and retries temporary download/file-lock errors.
Old update helpers are cleaned up automatically; no extra background service is installed.

Version 0.99.82 needs the full installer once when upgrading from 0.99.81 or earlier,
to add startup recovery to the stable launcher. Your realms and settings are preserved.
Later releases with a compatible runtime use **Restart to update**.
