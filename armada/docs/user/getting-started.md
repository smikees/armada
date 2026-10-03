# Getting started

## What you need

- **Windows.** The beta runs on Windows only.
- **Claude Code, Codex CLI, or Antigravity CLI for Gemini, signed in** with your provider account.
  Choose one or more. Install and connect them from App Settings. Google sign-in is saved for
  future Gemini runs; Google's free access is subject to its account quotas.
  The Armada installer can optionally install any of the three CLIs for you. You can also install them
  during setup; each provider shows whether its CLI is installed and needs an update.
- **One folder for ARMADA** — every realm you create lives inside it. You choose it the first time
  you open ARMADA (it suggests `ARMADA` in your user folder). Settings → App → Root folder
  displays the current path; changing the root folder there is not available yet.

## 1. Set up with Alexander

The first time you open ARMADA, press **Start setup**. **Alexander**, ARMADA's guide, walks you through
nine short steps: install or update your chosen provider's CLI, then select
**Sign in (opens browser window)**. Complete sign-in on the provider's website. If the browser
does not open automatically, use **Open sign-in page**; you can cancel an unfinished sign-in and retry.
Connect at least one provider to continue. Next, you choose ARMADA's
folder; enter your name and realm name on Naming, then choose a realm type and build your team on Team; you choose
recommended capabilities, with their sources and risk levels shown; you watch your coordinator write you a
first brief; and he shows you round. Close the window halfway and ARMADA picks up where you left
off. After that, add more realms from the realm switcher (top left) → **+ New realm**.

- **Create** starts fresh from a template. The template only sets the words the app uses — a
  *Cabinet* of *Ministers* led by a *Prime Minister*, a *Board* of *Executives*, a *Crew* — and a
  roster of starter profiles. Drag profiles into your team, or use **Add**. **View more** opens their
  full mission, soul, tenets and configuration defaults. **Create an agent** adds your own profile.
  Enter both your name and the realm name before choosing agents; your name is used in the starter
  profiles. State uses the prepared Cabinet profiles; Company and Crew currently use simpler starter roles.
- **Add an existing folder** opens a realm you already have — one you made on another computer or
  restored from a backup. Its scheduled jobs start **paused** until you've looked at them (see
  [Jobs](jobs.md#paused-jobs)).

New realms start with the same model and effort as Alexander. Agents inherit realm model defaults unless
you change their settings. **Settings → Realm → Model defaults** includes model, thinking and output verbosity,
plus **Set for all agents** to apply them across the team.

Check also lists Python and WebView2. The installer includes Python; it does not need a separate installation.

## 2. Meet your team

The **Overview** shows everyone. Click an agent to open their page, then **Threads** to talk to
them. Each agent has:

- a **mandate** — their role and what they're responsible for;
- a **soul** — their character and voice;
- their own **memory**, on top of what the whole realm shares.

Edit these under the agent's **Configure** tab. They're plain text, and they matter: the mandate
is the brief the agent works from on every turn.

## 3. Ask for something

Type in the thread. The agent answers in the same window; you can watch what it's doing (reading a
page, writing a file) as it works. Files it writes appear under **Artefacts**.

## 4. Make it recurring

On the agent's **Jobs** tab, **+ New job**: give it a name, what to do, and when — a cron
expression such as `0 9 * * 1-5` (weekdays at 9), or blank to run it only when you ask. On the
job's own page, the schedule presets and day circles fill the expression in for you. ARMADA runs it on schedule
while running, including with its window hidden in the tray. Quitting ARMADA stops its scheduler.
You'll find every run on the **Jobs** page and in the **Job calendar**. Expand a job to read its
prompt, output and run history. Execution, audit outcome and delivery have separate statuses;
completed does not mean an audit passed. Jobs inherit the agent's model defaults or can override
model, thinking and verbosity. Choose zero to three retries for retryable failures in Edit Job.

## 5. Give it tools, carefully

An agent with tools can act on your computer as you — read files, run commands, use your
connected services. Before you give one more reach, read [Staying safe](safety.md). Tools are
added and granted on the [Capabilities](capabilities.md) page.

## Where things are

| You want to… | Go to |
|---|---|
| see what's running, what failed, what's next | Jobs |
| see how much of your plan you've used | Overview → Usage, or the bars in the header |
| change what everyone knows | Memory |
| stop an agent doing something | its Jobs tab (switch the job off) or Configure → Autonomy |
| back up or move a realm | Settings → Realm → Export |
| ask how something works, or why it broke | Alexander, the portrait beside the gear |
