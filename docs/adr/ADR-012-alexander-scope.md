# ADR-012 — Alexander v1: explain, fix, build add-ons, report — through the app, never around it

**Status:** Accepted · 2026-09-25 · Mihai's brief, written up by Opus 5.5 · widens ADR-002's v1
("a guide that cannot write realm state or code")

## Context

ADR-002 made Alexander a read-only guide for v1 and deferred everything that changes anything to
"Alexander-the-developer" (DEFERRED D.1). On 2026-09-25 Mihai set a larger brief for the beta:

1. a specialist in **how ARMADA works** — mostly from the user's side (CX), but also from the
   developer's side;
2. a specialist in **building add-ons** for the app ("like a new widget");
3. **the best support professional**: knows the app *and* the user's current realm, and can
   explain a problem, **fix** it, or **report** it when it can't be fixed directly;
4. **the one agent the user cannot change**; knowledgeable and firm, tells it as it is, polite, and
   genuinely set on understanding and solving the problem — the closest thing to ARMADA's own
   voice in front of users.

Items 2 and 3 are writes. ADR-002's reasons for keeping v1 read-only still hold: an agent with
write access to the running app is a security surface, and self-modification by non-developers is
how forks and "which ARMADA are you running?" happen. The question is how to give Alexander the
brief without giving him the app.

## Decision

**Alexander proposes; the app acts; the owner confirms.** He never touches a file, a setting or
the code himself. Everything he can change goes through one of three channels, each of which the
app renders as a card with a button, and nothing happens until the owner presses it:

| Channel | What it can do | Bounded by |
|---|---|---|
| **Remedies** | the app's own actions, from a fixed list: start the scheduler, run a job now, switch a job on or off, refresh the environment memory, check for updates, open a page or a setting | `armada/alexander/remedies.py` — each remedy is ordinary app code with its own validation; Alexander only names one and its arguments |
| **Add-ons** | a new widget, filter, job template, layout or theme | the add-on contract (EXTENSION_POINTS.md): data only, never code; validated by `armada/addons.py`; written only into an add-on folder; undo is deleting the folder |
| **Reports** | an issue report to the ARMADA team | the existing 5.6 flow: the owner sees the exact text and sends it |

What he still cannot do, in v1, at all: edit realm files, agents, memories or jobs' content; run
shell commands or tools; read files the app didn't give him; see or handle credentials; change his
own identity, model or rules.

**How he runs.** A sealed engine turn (`only_tools` = none — the same mechanism as the capability
review): no tools, no filesystem, no network. The app assembles his context — the relevant help
pages, a snapshot of the realm (agents, jobs, recent runs and failures, settings that matter), the
log lines around a failure, the page the owner is on — and he answers from that alone, citing it.
**Model: Opus 5.5 at High effort, fixed for this version** (Mihai); the owner can't change it.
His runs count as **System** usage in every cost report, beside system jobs (Mihai).

**In the setup wizard he is scripted**, not generated: every word he says there is written in
advance (`armada/alexander/wizard_script.py`), so a first run costs nothing, can't go wrong, and
can be reviewed like any other copy.

**He can't be changed.** He's bundled with the app, not a realm agent: he isn't in any realm's
roster, can't be renamed, retired, given memories or capabilities, and his prompt ships with the
app (`armada/alexander/PROMPT.md`), updated only by a release.

## Consequences

- The add-on surface gets its **first consumer** in Phase 6: dashboard widgets (markdown and
  links), because "build me a widget" is the brief's example and ADR-002 required a built-in use
  before Alexander writes to it.
- Every remedy is a small, tested function; adding one is a code change and a release, never
  something Alexander can invent. An unknown remedy name renders as nothing.
- DEFERRED D.1 (Alexander-the-developer) keeps what is still out of scope: add-ons that carry
  code, changes to the app itself, and anything outside the add-on contract.
- The threat model gains a row: **prompt injection through the context** (a realm file or a job's
  output that says "Alexander, run X"). Mitigation: remedies are few, confirmed by the owner, and
  shown with exactly what they will do; add-ons are data and validated; he has no tools.
