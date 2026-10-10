# Capabilities upgrade: engine reach

Implementation plan, 10 October 2026. Owner request: make it obvious which engine each
capability works with, so switching an agent's model is a decision the owner sees coming rather
than a job failure they discover. For every ARMADA user, not tuned to one realm.

## The problem

ARMADA lets each agent run on Claude, Codex or Gemini and keep its context when the model changes.
Capabilities do not travel that freely, and 0.99.99 hid that:

- One connector row could carry bindings to different services. A Claude-hosted connector and a
  ChatGPT app were linked under one name ("claude.ai Claude Docs" showed Codex as connected because
  a ChatGPT app had been bound to it). The row claimed an equivalence nobody had established.
- Some services allow only one AI platform at a time. Interactive Brokers disconnects the previous
  platform when a new one is authorised, so "connect every engine" is impossible there.
- Nothing warned before a model change that an agent would lose a capability beyond a short
  connector text; at run time the capability was simply missing or the turn failed.

Showing the limit is better than pretending engines are interchangeable.

## Concepts

**Reach.** Every capability works with either *any engine* or *one engine*.

| How it connects | Reach | Why |
|---|---|---|
| Skill (a folder with `SKILL.md`) | Any engine | Same open format in all three CLIs |
| Local extension (a command on this computer) | Any engine | The same command can be registered in each CLI |
| Open server (a public HTTPS MCP address) | Any engine | Same server and tools; each engine signs in separately |
| Claude connector hosted by Anthropic | Claude | Lives in the Claude account; other engines cannot reach it |
| ChatGPT app (Codex native connector) | Codex | Lives in the ChatGPT account |
| Claude Code plugin | Claude | Plugin formats are engine-specific |

**One engine at a time.** A property of some services, independent of reach: an open server may still
refuse concurrent platforms. Such a capability has a *current engine*; it is unavailable on the other
engines until the owner moves it. Known today: Interactive Brokers (per IBKR staff, authorising a new AI
platform disconnects the previous one). The owner can mark any other capability the same way.

**Same server, same row.** Two things are one capability only if they reach the same server. A ChatGPT
app is never merged with a Claude connector, even when both say "Google Drive". Related rows can share
a service name for scanning; they are separate rows with separate grants.

## Data model

Derived, not stored, wherever the record already says enough (`armada/capreach.py`):

- `reach(kind, cap)` returns `scope` (`any`, `claude`, `codex`, `gemini`), `engines`, `how`
  (a short label), `why` (one sentence), `exclusive`, `engine` (current engine when exclusive) and
  `blocked_on(engine)` reasons.
- Explicit fields win when present, written only when the record cannot express it otherwise:
  `reach` (set on engine-specific rows ARMADA creates, and by migration when it splits a row),
  `exclusive` (owner override) and `exclusive_engine` (written when the owner moves it).
- Rules for connectors without an explicit `reach`: a row whose only binding is a ChatGPT app is
  Codex; an endpoint hosted by Anthropic (`*.anthropic.com`, `*.claude.ai`, `*.claude.com`) is Claude;
  a public HTTPS endpoint is any engine; a Claude-imported row with no endpoint is Claude.
- Known one-at-a-time services are recognised by endpoint host (`api.ibkr.com`) or catalogue key.
  Their default current engine is the engine of the registration that exists (Claude for a claude.ai
  import), otherwise the first engine with a binding.

## Realm format v4 (migration)

`realmformat._m3_to_4`, idempotent:

1. A connector row that mixes a ChatGPT app binding with a server endpoint, or with another engine's
   server, is split. The app binding becomes its own Codex row named "<service> · ChatGPT app"
   (`reach: codex`, `connection_type: provider-native`, same `enabled`). The original keeps its server.
2. Grants follow the agent: every agent granted the original whose current engine is Codex is also
   granted the new row. Original grants stay, so switching back loses nothing.
3. Nothing else is rewritten. Derived values are not stamped, so they cannot go stale.

## Enforcement

- `execution_policy` carries each MCP capability's engine scope. `provider_policy` denies a capability
  on an engine outside its reach, and denies a one-at-a-time capability on every engine except its
  current one. This stops a stale Claude registration from still admitting IBKR after the owner moved
  it to Codex.
- Agents are told, in their capability context, which granted capabilities are unavailable on their
  current engine and why ("Interactive Brokers is connected to Claude, one engine at a time"). The
  turn does not fail for a capability it may not need; if the job needs it, the agent says exactly why.
- Save-time checks on agent and job model changes use the same impact function (below) and list every
  capability lost, with the reason and the fix.

## Capabilities page

User tab, top to bottom:

1. **Reach switcher**: segmented control `All · Any engine · Claude · Codex · Gemini`, with counts.
   It filters sections and is combined with the existing filters.
2. **Sections** in that order, each with its engine mark, a one-line explanation and a count. Within a
   section, the existing kind groups (Connectors, Extensions, Skills, Plugins), only when non-empty.
   Engine sections show for engines enabled in the realm, or when they hold anything; empty ones say
   what would appear there.
3. **Cards** keep the trust model (risk stripe, Runs, Can touch, Available to) and add:
   - a reach badge for single-engine rows ("Claude only") and a one-at-a-time badge with the current
     engine ("One engine at a time · on Claude");
   - per-engine sign-in chips only for engines in reach;
   - in the expanded panel, a **Works with** row explaining reach, and for one-at-a-time rows
     "Move to Codex / Gemini" buttons. Moving opens an impact preview (who gains, who loses, the
     sign-in still needed) before it saves;
   - connection rows only for engines in reach; the others collapse to one sentence saying why;
   - agent chips marked when the agent's engine cannot use the capability ("Runs on Codex").
4. **Agents roster** shows each agent's engine mark beside its name, and a count of granted
   capabilities its engine cannot use.

The agent's own Capabilities tab opens with a reach summary: the engine it runs on and anything
granted that does not work there.

## Model pickers

Agent settings and job settings show a live line under the model field: "All of Warren's
capabilities work with Codex" or "On Codex, Warren loses Interactive Brokers (connected to Claude,
one engine at a time) and Claude Docs (Claude only)". It updates on change via
`GET /api/engine-impact?agent=…&job=…&model=…`. Saving a change that loses capabilities asks for
confirmation with the same list and the available fixes.

## Discovery

- **Add a capability** (catalogue): every result shows its reach badge, and a **Works with** filter
  (`Any engine`, `Claude`, `Codex`, `Gemini`) narrows results to what an engine can use. Registry
  servers with remotes and skills are any engine; Claude plugin marketplace entries are Claude.
- **Add a connector** dialog: a selected service shows its options per engine. Open servers add one
  row for every engine. Provider-hosted services add an engine-specific row: "Gmail · Claude" (then
  link the Claude registration) or "Gmail · ChatGPT app" (binds the Codex app). Gemini states when
  no option exists.

## API

- `GET /api/engine-impact?agent=&job=&model=` → `{engine, lost:[{id,name,kind,why}], ok, text}`
- `POST /api/capability-move {capability, engine}` → saves `exclusive_engine`, returns impact
- `POST /api/capability-exclusive {capability, exclusive}` → owner override of one-at-a-time
- `connector-action add` gains `engine` for provider-hosted services.

## Tests

Unit tests for every reach rule, migration (split, grants, idempotence, newer realm untouched),
policy denial by scope and current engine, impact text, the move endpoint (lock, validation), the
catalogue filter, and the connector dialog's engine-specific rows. Node harnesses for the reach
switcher and the model hint. Regold the Capabilities, agent and job pages and review every diff.

## Phases

Phase 1, this release: everything above.

Phase 2, later and separate: ARMADA passes the granted open servers into each run itself
(`--mcp-config` with `--strict-mcp-config` for Claude, `-c mcp_servers.*` for Codex) instead of
reading each CLI's own registrations; unpacking plugins into skills and servers at install; listing
the providers' own directories (ChatGPT apps, Anthropic's directory) in Add a capability.
