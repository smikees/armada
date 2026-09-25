# ARMADA

**Your standing team of minds.**

ARMADA is a desktop app for building and running your own team of AI agents — a *realm* — on your
own computer, through your own Claude subscription. Each agent has a role, a character, its own
memory and its own scheduled jobs; you talk to them in threads, give them tools deliberately, and
see what each one is being told before it answers.

- **Local.** Nothing is hosted. The app runs on your machine and talks to Claude through Claude
  Code, signed in with your account. ARMADA never sees your password.
- **Your data is a folder.** A realm is plain Markdown and JSON in a folder you own — back it up,
  version it, move it to another computer.
- **Context you can see.** ARMADA decides what each agent and each thread is given — shared
  memory, the agent's own memory, its brief, the recent conversation — and shows you the mix and
  its size.
- **Jobs that run on their own.** Recurring work on a schedule, with the window closed.

> **Status: beta, Windows only.** ARMADA is in a small invited beta. Expect rough edges — and
> please report them.

## Before you give an agent tools

An agent with tools acts as you: it can read and write your files, run commands and use the
services you've connected. Read [Staying safe](armada/docs/user/safety.md) first.

## Requirements

- Windows 10 or 11
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview), signed in with your Claude
  subscription

The beta is installed with `ARMADA-Setup-<version>.exe` (per user, no admin rights needed; it
brings its own Python). It isn't code-signed yet, so Windows SmartScreen says "unrecognised app"
the first time: choose *More info → Run anyway*. The installer is built with
`tools/build_installer.py` ([ADR-009](docs/adr/ADR-009-installer.md)).

To run from source instead (Python 3.12):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\pythonw -m armada app
```

The first launch opens the setup wizard: Alexander, ARMADA's guide, checks Claude Code, sets up
ARMADA's folder and your first realm and team, and shows you round.

## Documentation

- **Using ARMADA:** [armada/docs/user](armada/docs/user/index.md) — also inside the app (the book icon, top
  right).
- **How it's built:** [ARCHITECTURE.md](docs/dev/ARCHITECTURE.md), the realm format in
  [SCHEMA.md](docs/dev/SCHEMA.md), and the rest of [docs/dev](docs/dev/index.md).
- **Why it's built this way:** the decision records in [docs/adr](docs/adr/README.md).
- **Where it's going:** [LAUNCH_PLAN.md](docs/LAUNCH_PLAN.md).

## Licence

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE): free for personal and
other noncommercial use; commercial use by agreement — get in touch. Third-party notices are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

ARMADA is independent and isn't affiliated with or endorsed by Anthropic. Claude and Claude Code
are Anthropic's.
