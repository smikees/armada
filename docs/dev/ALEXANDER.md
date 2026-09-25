# Alexander — design

*Phase 6, step 6.1. Written 2026-09-25 (Opus 5.5) from Mihai's brief; scope in
[ADR-012](../adr/ADR-012-alexander-scope.md), which widens [ADR-002](../adr/ADR-002-alexander.md).*

Alexander is ARMADA's guide: the one bundled agent, the same in every install, that the owner
can't change. He appears in two places:

| Where | How he speaks | Cost |
|---|---|---|
| **The setup wizard** (first run) | scripted: every line written in advance in `armada/alexander/wizard_script.py` | nothing |
| **Support** (the support icon beside Settings, on every page; "Ask Alexander" on a failed job or run) | live: a sealed engine turn, **Opus 5.5 at High effort**, fixed for this version | the owner's Claude quota, shown as **System** usage |

## The prompt

[`armada/alexander/PROMPT.md`](../../armada/alexander/PROMPT.md), shipped with the app and sent
verbatim as the system prompt. It sets his three jobs (how ARMADA works, solving the owner's
problem, building add-ons), what he knows (only what the app hands him), how he cites, how he
proposes actions, and his voice. Changing it is a release, like any other copy; the owner can't.

## What the app hands him (context assembly)

Each support turn is one user message wrapped in the sections the prompt names. The app builds
them; Alexander has no tools, files or network (`only_tools` = none, as the capability review).

| Section | Contents | Source |
|---|---|---|
| `<page>` | the page the owner is on, and the item (job, agent, run) if they asked from one | the request |
| `<help>` | every help page, whole (all of them together are about 25 KB), the most relevant first | `armada/docs/user/*.md`, ranked by term overlap with the question and the page |
| `<realm>` | a compact snapshot: realm name and template, agents (name, role, model, capabilities with risk), jobs (schedule, on/off, last run and its outcome), goals, scheduler state, sign-in state, version | the realm on disk + app state |
| `<logs>` | for a failure: the run's own log and the `~/.armada/logs` lines within a few minutes of it, secrets redacted (the 5.6 redactor) | the run + logs |
| `<addon_contract>` | the widget part of the add-on contract and one worked example | `armada/alexander/ADDON_CONTRACT.md`, checked by `armada/addons.py` |
| `<conversation>` | the last dozen messages of this conversation | `~/.armada/alexander/<id>.jsonl` |
| `<remedies>` | the remedy names, their arguments and one line each on what they do | `armada/alexander/remedies.py` |

The conversation (his answers and the owner's messages) is kept in `~/.armada/alexander/` — this
machine's, not a realm's — so a follow-up question has the earlier turns.

## What he can do (ADR-012)

Implemented in `armada/alexander/support.py` (context, the turn, taking the reply apart), the
drawer in `armada/webui/static/js/alexander.js`, and `/api/alexander-ask` (streamed),
`/api/alexander-history`, `/api/alexander-addon`.

He **proposes**; the owner **confirms**; the **app** does it. Proposals are fenced blocks in his
reply (` ```remedy `, ` ```addon `, ` ```report `); the page renders each as a card with exactly
what will happen and one button. Nothing else in his reply can act.

- **Remedies:** a fixed list of the app's own actions (start the scheduler, run a job now, switch a
  job on or off, refresh the environment memory, check for updates, open a page or setting). An
  unknown name, or arguments that don't validate, renders as nothing.
- **Add-ons:** a complete `addon.json`, validated by `armada/addons.py` before the card even shows;
  installed into `~/.armada/addons/<id>/` (or the realm's, if the owner picks it); undone by
  deleting the folder. Dashboard widgets are the first add-on kind the app displays.
- **Reports:** the 5.6 report flow, pre-filled; the owner reads the exact text and sends it.

## In the wizard

Scripted, in his voice, one short paragraph per step, with the step's own words for what's
happening and why. No generated text, so the first run can't fail on quota, sign-in or a model's
mood, and every line can be reviewed. The wizard ends by pointing at his button.

## Guarding him

- **Prompt injection** through the context (a file or a job's output addressed to him): the prompt
  says context is information, never instructions; he has no tools; every action is a card the
  owner has to press, stating what it does. (THREAT_MODEL gains the row.)
- **Credentials:** never in his context (the realm snapshot excludes them, logs are redacted), never
  in a report.
- **Tests** (`tests/test_alexander*.py`): the prompt ships and has the sections the code fills; the
  model and effort are fixed; remedies validate their arguments; an add-on block that fails the
  contract never renders a card; an unknown remedy renders nothing; context assembly redacts.
