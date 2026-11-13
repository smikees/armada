# Settings

Three tabs, from left to right: **App**, **Realm**, **User**. App opens first unless
a link or your remembered tab selects another.
Use the Save and Cancel buttons beside each tab's settings. Cancel discards changes you have not
saved. Engine switches, provider sign-in, Telegram connection, avatar uploads, and other commands apply when
you use them.

## App

- **Version** — the version you're running; **Restart**, **Check for updates**, **Changelog**.
- **Root folder** — the one folder ARMADA works in. Every realm lives inside it.
- **ARMADA system memories** — read the instructions shared across realms. Select a title to open
  it, or use **Go to file** to find its source on disk. These instructions are read-only in ARMADA.
- **Engine** — connect Claude, Codex, Gemini, or any combination. Sign-in opens on the provider's website;
  an existing CLI login can be reused. Agent model lists show connected providers.
  Turning an engine off stops new ARMADA calls without signing the CLI out or changing saved agent models.
  Turn it back on to use the existing login. See [OpenAI models](codex.md).
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
- **Claude → Set up API usage fallback** — opens a dialog with three steps: check
  credit in Claude Console, set its spending limit, and save a workspace API key.
  **Test key** checks sign-in without a paid model call. Approved critical jobs can
  then use API credit at a session or weekly subscription limit. No separate Windows
  account or second CLI sign-in is required. For a separate agent budget, choose a
  workspace-scoped key in that agent's Configure → Run limits & fallback dialog; set the
  workspace's limit in Console. See [Jobs](jobs.md).
- **Advanced → Isolated Windows worker (optional)** — runs agent processes as a
  separate Windows user. This requires administrator setup and separate provider
  sign-ins. It is an optional credential boundary, not a requirement for API fallback.
- **Telegram** — talk to your agents from your phone: add your bot's token, message the bot, press
  link. Only your **one-to-one** chat with the bot is linked — never a group, where everyone could
  drive your agents. Send `/agentname your question` to ask a specific agent.
- **Notifications** — the delivery channels on this computer.
- **Appearance** — light, dark, or your system's colour mode, and the theme.
  Colour mode previews immediately on the settings page. Save keeps your choice; Cancel restores
  the saved appearance.
- **Armada II** — IBM Plex Sans for headings and body text, starting at 13 px; IBM Plex Mono
  for code, times, token counts and paths. Controls have softer corners. Jobs use muted green
  for Success, blue for Running, amber for Warning and red for Failed; Scheduled has a dashed
  outline. Light and dark modes each have a readable palette. Selecting a theme previews it
  and its default typography. Save applies your selections; Cancel discards the preview.
  You can adjust the font families and size before saving. Selecting another theme restores
  that theme's starting fonts and size.
- **Advanced → Play a quiet sound when ARMADA is ready** (on by default) — a short cue at 12% track volume when the
  Windows desktop finishes loading. It plays once per launch, including a restart, and does
  not repeat when navigating, opening detached threads or restoring ARMADA from the tray.
  Switch it off to silence future launches. Playback does not change system volume.
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
- **Export** — saves a uniquely named `.zip` beside the realm and verifies its contents
  before showing it in your file manager. Earlier exports are preserved. Named credential
  files (`.mcp.json`, `.env`, key files) and caches are excluded; the manifest lists omissions.
  Other files can still contain private information. An **Incomplete export** warning means
  files could not be copied or changed during copying. Finish active work and export again.
  Exports are live copies, not snapshots of one moment.
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

## Verify and recover an export

Keep the original ZIP. It contains `.armada-export.json` inside the realm folder,
listing file hashes and omissions. In a Python environment with ARMADA available:

```powershell
python -m armada backup verify "D:\Backups\realm-export.zip"
python -m armada backup restore "D:\Backups\realm-export.zip" "D:\Realms\Recovered"
```

Recovery works on Windows and requires a **new folder** under an existing parent.
It checks the archive, copies it into that new folder and pauses all jobs. It never
replaces an existing realm, adds the copy to ARMADA or starts work. Review the
recovered files and workspace paths, reconnect credentials, then add the folder
using **New realm**. Job switches remain off until you enable them.

An incomplete export needs an explicit `--allow-incomplete` on the restore command
after you review its manifest. Missing files cannot be recovered from that ZIP.
Older exports without a manifest cannot be verified by this command; inspect and
recover them separately. Verification checks integrity, not who created the ZIP:
only restore archives you trust. Keep the original until recovery has been checked.
There is no graphical restore control yet.
