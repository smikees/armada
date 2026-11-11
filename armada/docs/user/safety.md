# Staying safe

## The one thing to know

By default, an agent with tools runs with your Windows permissions. Treat each grant
as permission to use that tool on your computer.

API fallback requires the **isolated Windows worker**, configured in App Settings.
Normal agent, shell and connector processes then use a separate non-admin account.
The owner API key and run-control files stay outside realms, inaccessible to that
account. Approved draft scripts retain their AppContainer restrictions and use a
private desktop. Set up the worker from the normal installation, then sign in to
providers and reconnect services for that account.

This protects owner credentials; files accessible to the worker and services you grant
remain available to agents. Agents sharing that account are not isolated from each
other. File restrictions and memory auditing still depend on the selected engine and
its supported tools; see [Memory](memory.md) and [Gemini](gemini.md).

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

- Provider sign-in happens through the selected provider's CLI and website. ARMADA does not ask
  you to paste your provider password into a realm or conversation.
- It only answers requests from this computer, addressed to it.
- It never shows you a capability as safer than what it can do.

## Autonomy

Each agent's **Configure → Autonomy** decides how much it may do without asking:
*manually approve everything* (safest), *auto-approve routine actions*, or *skip all approvals*.
New agents start on *manually approve everything*.
