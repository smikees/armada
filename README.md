# ARMADA

**Create, empower and control your army of agents.**

ARMADA is a desktop app for building and running your own team of AI agents — a *realm* — on your
own computer, through any one or combination of your connected Anthropic, OpenAI and Google accounts. Each agent has a role, a character, its own
memory and its own scheduled jobs; you talk to them in threads, give them tools deliberately, and
see what each one is being told before it answers.

- **A standalone desktop app.** ARMADA runs independently of provider desktop apps. It uses
  Claude Code, Codex CLI or Antigravity CLI with your saved sign-in. Model requests go to the
  selected provider; your realm and its files stay in your chosen local folder.
- **Your data is a folder.** A realm is plain Markdown and JSON in a folder you own — back it up,
  version it, move it to another computer.
- **Context you can see.** ARMADA decides what each agent and each thread is given — shared
  memory, the agent's own memory, its brief, the recent conversation — and shows you the mix and
  its size.
- **Jobs that run on their own.** Recurring work on a schedule while ARMADA is open or in the tray.
  Each job can choose its own model, effort, verbosity and retry policy. Run history separates
  execution, audit findings and delivery, and preserves the original output and specific errors.
- **Tools you choose.** Grant agents capabilities deliberately, with connector availability
  checked separately for each engine. Provider accounts and connector authorizations are distinct.

> **Status: beta, Windows only.** ARMADA is in a small invited beta. Expect rough edges — and
> please report them.

**Current release: [v0.99.90 — unsigned beta](https://github.com/smikees/armada/releases/tag/v0.99.90).**
[Download the Windows installer](https://github.com/smikees/armada/releases/download/v0.99.90/ARMADA-Setup-0.99.90.exe)
or browse [all releases](https://github.com/smikees/armada/releases).
Upgrading from 0.99.81 or earlier requires running this full installer once to add
browser-verified startup recovery. It preserves realms and settings. Later compatible
releases install through Settings → Check for updates → Restart to update.
Only one desktop/server can run per Windows user, independent of realm or installation.

## Before you give an agent tools

An agent with tools acts as you: it can read and write your files, run commands and use the
services you've connected. Read [Staying safe](armada/docs/user/safety.md) first.

## Requirements

- Windows 10 or 11
- At least one connected engine: **Claude Code** (Anthropic), **Codex CLI** (OpenAI), or
  **Antigravity CLI** (Google/Gemini). The setup wizard checks installation and sign-in and
  offers installation and login actions. Model access and quotas depend on your provider account.

The beta is installed with `ARMADA-Setup-<version>.exe` (per user, no admin rights needed; it
brings its own Python). The published 0.99.87 installer is unsigned: Windows may show a
SmartScreen warning. Windows Smart App Control
or an organization's Application Control policy can block its extracted temporary executable
with error 4551. This is not the ordinary SmartScreen warning; it has no "Run anyway" override.
This beta does not fix that restriction; publisher signing remains pending. Keep Windows protections enabled.
Packaged startup and update-recovery checks passed on the developer's machine. Clean Windows Sandbox GUI
acceptance remains open because Microsoft's WebView2 prerequisite installer failed there;
see the [release notes](https://github.com/smikees/armada/releases/tag/v0.99.90).
The installer is built with
`tools/build_installer.py` ([ADR-009](docs/adr/ADR-009-installer.md)).

To run from source instead (Python 3.12):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\pythonw -m armada app
```

The first launch opens the setup wizard: Alexander, ARMADA's guide, checks all three engines,
helps you connect at least one, sets up ARMADA's folder and your first realm and team, and guides
you through a first task. You can connect more engines later in Settings → App.

## Documentation

- **Using ARMADA:** [armada/docs/user](armada/docs/user/index.md) — also inside the app (the book icon, top
  right).
- **OpenAI models for existing agents:** [Codex setup](armada/docs/user/codex.md).
- **Google models:** [Gemini / Antigravity setup and current limitations](armada/docs/user/gemini.md).
- **Scheduled work:** [Jobs, run results and retries](armada/docs/user/jobs.md).
- **Building and publishing:** [Release procedure](docs/dev/RELEASING.md).
- **How it's built:** [ARCHITECTURE.md](docs/dev/ARCHITECTURE.md), the realm format in
  [SCHEMA.md](docs/dev/SCHEMA.md), and the rest of [docs/dev](docs/dev/index.md).
- **Why it's built this way:** the decision records in [docs/adr](docs/adr/README.md).
- **Where it's going:** [LAUNCH_PLAN.md](docs/LAUNCH_PLAN.md).

## Licence

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE): free for personal and
other noncommercial use; commercial use by agreement — get in touch. Third-party notices are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

ARMADA is independent and is not affiliated with or endorsed by Anthropic, OpenAI or Google.
Provider names and logos belong to their respective owners.
