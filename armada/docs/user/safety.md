# Staying safe

## The one thing to know

**An agent with tools acts as you.** When an agent works with its tools, it runs on your computer
with your permissions: it can read and write your files, run commands, and use the services you've
connected. ARMADA limits *which tools* each agent gets and keeps agents out of each other's memory,
but it doesn't put the agent in a box. Treat giving an agent a tool the way you'd treat running
that tool yourself.

## Five habits

1. **Grant tools deliberately.** An agent gets only the capabilities you grant. Start with none;
   add what a job actually needs.
2. **Be careful with agents that read the outside world *and* can act.** Anything an agent reads —
   a web page, an email, a document, a repository — can contain instructions aimed at it. An
   agent that reads your inbox and can also send money is the combination to avoid.
3. **Read the report before adding a capability.** The risk colour is the worst thing it *can* do,
   not a promise about what it *will* do.
4. **Only open realms you made or trust.** A realm carries jobs that run on a schedule. ARMADA
   pauses them when you add an existing folder, and shows you every command; read them.
5. **Keep Telegram to your own chat.** The bot answers one private chat — yours.

## What ARMADA won't do

- It never asks for, stores or sends your Claude password or keys; signing in happens in Claude's
  own window.
- It only answers requests from this computer, addressed to it.
- It never shows you a capability as safer than what it can do.

## Autonomy

Each agent's **Configure → Autonomy** decides how much it may do without asking:
*manually approve everything* (safest), *auto-approve routine actions*, or *skip all approvals*.
New agents start on *manually approve everything*.
