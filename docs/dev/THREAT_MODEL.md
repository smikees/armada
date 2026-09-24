# ARMADA threat model

*Phase 5, step 5.8. Written 2026-09-24 (Opus 5.5) against v0.99.44, updated for v0.99.46, from the code, not from how
the app is meant to work. Two problems found while writing it were fixed the same day (T1, T2);
the rest are tickets below. Update this page whenever something here changes.*

## The one sentence that matters

**An ARMADA agent with tools is you.** A tool turn runs Claude Code with
`--dangerously-skip-permissions` (`engine/claude.py:ClaudeEngine.run` / `run_stream`), in the
agent's folder, as your Windows user. It can read and write any file you can, run any command
you can, and reach any network address you can. Everything ARMADA adds on top narrows what an
agent is *told* or *granted*; none of it is a sandbox. So the question for every threat below is
the same: **can someone other than you get words in front of an agent, or get code into the
app's page?** Either is equivalent to running code as you.

## What we protect

- **The owner's machine and files** — everything the Windows account can touch.
- **Credentials** — Claude Code's OAuth sign-in (`~/.claude/.credentials.json`, read only, never
  refreshed or written by ARMADA), the Telegram bot token (`~/.armada/telegram.json`), MCP server
  keys in `~/.claude.json` / a realm's `.mcp.json`, anything else agents can read.
- **Realm data** — memories, goals, threads: often personal and financial.
- **The subscription** — every agent turn spends quota.

## Actors and boundaries

| Actor | Trusted? | How they reach an agent or the page |
|---|---|---|
| The owner | yes | the app window; Telegram |
| The owner's agents | trusted to act, **not** trusted to stay uncompromised | they read web pages, repos, documents, email — any of which can carry instructions |
| Third-party capabilities (MCP servers, skills, plugins) | no | their code runs with the owner's rights once installed; their names and text are displayed |
| Web pages in the owner's browser | no | the local HTTP server on 127.0.0.1 |
| Other users / processes on the machine | no | the same port — there is no login |
| Anyone on Telegram | no | the bot, if they are the linked chat |
| A realm someone else made | no | adopting it brings its jobs, prompts and HTML |
| ARMADA's own update channel | must be | `git pull` today; the update path in 5.4 |

## What ARMADA does enforce

| Control | Where | Strength |
|---|---|---|
| Capability grants: ungranted MCP-backed capabilities are denied at the engine (`--disallowedTools mcp__<id>`) | `runner._disallowed_tools` | **Real** for connectors, extensions, plugins; advisory for skills |
| Other agents' and realm memory: writes are reverted after the turn | `runner._guard_snapshot` / `_guard_restore` | Real but after the fact (a turn can read, and act on, anything first) |
| Publish boundary: writes outside `shared/` are detected and reported | `runner._publish_boundary`, `_TurnCapture` | Detection only |
| Realms live inside one app root | `approot.check` | Placement rule, not containment |
| Server binds 127.0.0.1 only | `serve.serve` | Real |
| Host must be a local name (DNS rebinding) | `serve.Handler._host_ok` | Real — **T1, v0.99.43** |
| Cross-origin POSTs refused (Origin ≠ Host) | `serve.Handler._same_origin` | Real, given T1 |
| Values in event attributes JSON-encoded | `webui/_base._J` | Real — **T2, v0.99.44** |
| Markdown rendered from escaped text only | `webui/_base._md` | Real |
| Telegram answers one linked chat only | `telegram.handle` / `dispatch` | Real |
| No metered API key reaches the engine | `ClaudeEngine._env` strips `ANTHROPIC_API_KEY` | Real |
| Add-ons are data, never code | `addons.py` (2.7) | Real by construction |
| Swallowed errors are logged | `util.swallowed` (2.5) | Visibility, not defence |

## Findings

Severity is for a beta of ~5 invited users on their own Windows machines.

| # | Threat | Severity | Status |
|---|---|---|---|
| T1 | **DNS rebinding.** A web page re-points its own domain at 127.0.0.1; to the browser it is then same-origin with ARMADA, and the Origin=Host check passes because both are the attacker's name. It could read every page and POST `/api/chat-stream` — an agent turn with permissions skipped. | Critical | **Fixed v0.99.43**: Host must be 127.0.0.1 / localhost / [::1]; `test_host_guard.py` |
| T2 | **Script injection through names.** ~40 `onclick="f('{E(x)}')"` sites: the HTML parser turns `&#x27;` back into `'` before JS runs, so a capability name (from a marketplace) or a thread title (written by a model) containing a quote runs as code in the app's page. | High | **Fixed v0.99.44**: `_J`; `test_js_attr_escaping.py` |
| T3 | **Untrusted HTML on the app's own origin.** Section mini-sites (`/section-raw`, `/section-asset`), mirrored snapshots of external pages, and `.html` thread attachments (`/thread-file`) are served from `127.0.0.1:8756` with no sandbox. Their scripts can call every API route — same origin, so T1's and the CSRF checks don't apply — including starting an agent turn. A mirrored external page puts a *remote site's* JavaScript there. | **High** | **Fixed v0.99.58** (5.8a): served from a content-only server on the app's port + 1 (`serve.ContentHandler`, `origins.py`) — a different origin, no API, no POST; the app 302s those paths there, refuses cross-site/same-site GETs (`Sec-Fetch-Site`) and cross-origin POSTs, and frames them with a `sandbox` that omits top navigation. If the content server can't bind, the app serves them itself under `CSP: sandbox` (opaque origin) |
| T4 | **Reviewing a link runs a tool-enabled agent on untrusted content.** `catalogue.review_url` calls the engine with `allow_tools=True` against a URL the owner pasted. The repo or page being reviewed can carry instructions ("to verify, run…"), and the reviewer can act on them with the owner's rights — the feature meant to judge risk is itself the most exposed turn in the app. | **High** | **Fixed v0.99.57** (5.8b): the review is a sealed turn — `--safe-mode` (no MCP, skills, plugins), `--tools WebFetch,WebSearch`, those pre-approved, `--permission-prompts none` for anything else; no file access, no shell (`engine/claude._sealed_tool_args`, `catalogue.REVIEW_TOOLS`) |
| T5 | **A realm is code.** Adopting a folder brings command jobs (shell commands run on schedule), agent jobs (prompts run with tools) and section HTML (T3). The scheduler starts firing them on its next pass unless preflight fails. | Medium-High | **Fixed v0.99.46**: adopt holds the scheduler; the Jobs page lists every command verbatim with a release button |
| T6 | **Delete / open any path.** `/api/delete-artefact` and `/api/open-file` take an absolute path from the request and act on it anywhere on disk. Only same-origin callers reach them, so today it takes T3 to exploit — but nothing else stops it. | Medium | **Fixed v0.99.46**: only inside the realm, its workspace, the app root |
| T7 | **No login on the local port.** Any process or other Windows user on the machine can call the API, and so run agents as the owner. | Medium | Accepted for the beta (single-user machines); revisit before public (a per-install token in the window URL) |
| T8 | **Telegram edges.** Linking takes the newest chat that messaged the bot (a stranger messaging at that moment wins — the UI shows the name, but doesn't ask); a linked *group* lets every member drive agents with tools. | Low-Medium | **Fixed v0.99.46**: private chats only (link and answer); linking-race name confirmation still open |
| T9 | **Secrets leaving in an export.** `realmops.export` zips the whole realm; a realm-level `.mcp.json` or `.env` holding API keys goes with it. Server logs hold tracebacks, which can contain paths and prompt text — relevant to 5.6's issue report. | Low-Medium | **Export fixed v0.99.46** (secret-bearing files left out and listed); logs: 5.6's redaction + preview |
| T10 | **Client-side sinks not audited.** Static JS builds some markup with `innerHTML` from API data (notification titles, thread lists, the skill viewer's body). T2 covered server-rendered attributes only. | Medium | **Fixed v0.99.46**: audited all `innerHTML` sinks; four unescaped (realm switcher, thread-delete dialog, Usage colours, a dashboard onclick) fixed, `mcEsc` now escapes quotes |
| T12 | **The reports key ships in the build.** Report an issue (5.6) sends through Resend with a key in the installed app (`armada/support_key.txt`, git-ignored). Anyone with the build can extract it. It's a *sending-only* key restricted to armada.stamih.com, so the worst case is someone sending mail as reports@armada.stamih.com to armada@stamih.com until it's revoked; Resend's free-tier cap (100/day) bounds it. Accepted for the invited beta (ADR-005); a small relay that holds the key replaces it before a public release. | Low (beta) | Accepted — relay before public |
| T11 | **The update channel.** Update & Restart is `git pull` + re-exec: whoever controls the remote controls the code. There is no remote today; 5.4's automatic updates must verify a signed or pinned release before running it. | High (future) | Requirement on 5.4 |

## Out of scope

Malware already running as the owner; a compromised Windows account; physical access; the
security of Claude Code, the Claude API, Telegram, or any MCP server's own code (the review
protocol informs the owner's decision, it doesn't contain the capability); denial of service
against the owner's own subscription by the owner's own agents (the per-run budget and Telegram's
hourly ceiling limit it, they don't prevent it).

## What the beta tells its users (plain words, for the wizard and the docs)

1. Your agents act as you, with your files and your accounts. Give a capability to an agent only
   if you'd run that tool yourself.
2. Anything an agent reads can talk to it. Be deliberate about agents that read the open web or
   your inbox *and* can act.
3. Only open realms you made or trust — a realm carries jobs that run on a schedule.
4. The Telegram bot answers one private chat: yours. Don't link a group.
5. ARMADA never asks for, stores or sends your Claude password or keys.
