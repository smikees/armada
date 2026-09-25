# Getting started

## What you need

- **Windows.** The beta runs on Windows only.
- **Claude Code, signed in** with your Claude subscription. ARMADA runs every agent through it and
  never sees your password. If you're signed out, a bar at the top of the app offers to open
  Claude's own sign-in.
- **One folder for ARMADA** — every realm you create lives inside it. You choose it the first time
  you open ARMADA (it suggests `ARMADA` in your user folder), and can change it later in
  Settings → App → Root folder.

## 1. Set up with Alexander

The first time you open ARMADA, **Alexander**, ARMADA's guide, walks you through setup in eight
short steps: he checks Claude Code is installed, up to date and signed in; you choose ARMADA's
folder and name your first realm; you appoint a team from a template; you switch on a few
recommended capabilities (all Low risk, all from Anthropic); you watch your coordinator write you a
first brief; and he shows you round. Close the window halfway and ARMADA picks up where you left
off. After that, add more realms from the realm switcher (top left) → **+ New realm**.

- **Create** starts fresh from a template. The template only sets the words the app uses — a
  *Cabinet* of *Ministers* led by a *Prime Minister*, a *Board* of *Executives*, a *Crew* — and a
  starter team you can keep, rename or untick. Pick whatever reads right to you; nothing else
  changes.
- **Add an existing folder** opens a realm you already have — one you made on another computer or
  restored from a backup. Its scheduled jobs start **paused** until you've looked at them (see
  [Jobs](jobs.md#paused-jobs)).

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
job's own page, the schedule presets and day circles fill the expression in for you. ARMADA runs it on schedule — even when the window is
closed, as long as the ARMADA scheduler is running (opening the app starts it; a yellow bar
tells you if it stops) — and you'll find every run on the
**Jobs** page and in the **Job calendar**.

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
