# Staying safe

## The one thing to know

By default, an agent with tools runs with your Windows permissions. Treat each grant
as permission to use that tool on your computer.

Claude API fallback normally uses this same Windows account. Keys are encrypted on
this computer and kept outside realms and exports. The CLI receives a temporary
invocation token instead of the real key. Code running as your Windows user can
still access your credential store: set the spending limit in **Claude Console**,
which also limits calls outside Armada. Keep auto-reload off to use existing credit
only. Armada's reported costs cover its own runs, not your authoritative balance.

For a stronger credential boundary, **App Settings → Advanced → Isolated Windows
worker (optional)** runs normal agent, shell and connector processes as a separate
non-admin user. Its setup needs administrator approval and separate provider
sign-ins. Owner credential files are inaccessible to that account. Approved draft
scripts keep their AppContainer restrictions. An explicitly configured worker
continues to be required until its configuration is repaired; losing its manifest
does not silently restore the owner identity.

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
