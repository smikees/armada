# ADR-003 — The Council: plan-only, proposals as output, coordinator-curated

**Status:** Accepted · 2026-09-21

## Context

A council is a staged debate: the user poses a topic, the coordinator decides which agents
should join (they "raise their hands"), adds framing context, the chosen agents weigh in one
after another, and the coordinator summarises into actions the user approves or dismisses.
Mihai wants it in v1 as the feature that differentiates ARMADA for casual users.

The parts that look hard — the UI — mostly exist: threads with turns, a roster, avatars. The
parts that are actually hard are cost and judgement. Seven agents each reading the full context
is seven times the tokens of one, against a subscription with a weekly limit the app already
has to display. And a coordinator deciding who to invite and how to summarise is fine on the
first demo and embarrassing on the fifth unless the design constrains it.

Two pieces of machinery already exist for "an agent proposes, the user decides": job proposals
(an agent writes a proposal file, the user approves or dismisses it in the app) and inbox
delegation (an agent asks a teammate to do something, with the same gate).

## Decision

1. **A council only plans. It never executes.** Nothing an agent says in a council runs a tool,
   writes realm state, or sends anything. This removes nearly every side-effect risk at once.
2. **Its output is proposals through the existing approve/dismiss machinery** — job proposals
   and inbox delegations, the two types that exist. No new action type. The council's summary
   is a *batch* of those, each approved or dismissed individually.
3. **The coordinator curates.** It picks participants with a one-line reason each and adds
   framing; the user can add or remove before the session starts. Participants are capped.
4. **Turns are sequential and visible**, each participant seeing the prior turns, with a hard
   cap on turns and on tokens per council.
5. **A cost guard runs before convening**: the estimated token spend is shown, and the app
   refuses to convene if it would cross the weekly limit.
6. **Design before code.** A dedicated design session (Phase 7, step 7.1) with Mihai settles
   the turn model, the cap, the invite logic, the context each participant gets, and what a
   council thread looks like beside an ordinary one — into a design doc and a UI sketch —
   before anything is built. Two rounds of UI iteration with Mihai are budgeted.

## Consequences

- Reusing proposals and delegation means the council is largely assembly. The novel code is the
  invite step, the turn loop, and the thread view.
- A council is a thread with a roster and a phase (convened → in session → summarised →
  actions), stored as threads are stored.
- Phase 7 comes after the wizard and Alexander (Phase 6): it is the feature least likely to
  decide whether a beta user keeps the app installed, however good it is.
- We give up: councils that act. If a council's plan is good, the user approves the proposals
  and the agents act on their own schedules, through the gates that already exist.
