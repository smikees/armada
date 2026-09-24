# ADR-002 — Alexander: a guide in v1, a developer via extension points later

**Status:** Accepted · 2026-09-21

## Context

Alexander is a bundled agent — not a realm agent the user sets up — that first appears in the
setup wizard and is thereafter reachable from a Support button on every page. Two capabilities
were envisaged for it: *guiding* (walk through setup, answer "how do I", explain why a job
failed) and *developing* (modify ARMADA itself on the user's behalf — new filters, widgets,
colours, features — by forking the app's code and iterating on it, with a way back to the
official version).

These are two products. The first is a content problem plus a thread UI that already exists.
The second has consequences that reach past effort: users end up on divergent forks, so updates
break and "which ARMADA are you running?" becomes unanswerable; an agent with write access to
the running app is a security surface; "revert to official" is a version-control product in its
own right; and unsupervised self-modification by non-developers is the fastest route to the
entropy that the launch plan's architecture phase exists to prevent.

## Decision

**v1: Alexander is a guide.** It has the documentation and the app's logs as context, can read
realm state, and cannot write realm state or code. It narrates the wizard, answers questions
from the docs, and can be summoned from a failed job or run with the log attached. Every answer
cites the doc page or log line it came from, so a wrong answer is traceable to a wrong doc.

**Later: Alexander-the-developer works through extension points, never by patching the app.**
Phase 2 (step 2.7) designs and stubs a plugin surface — widgets, filters, themes, job
templates, dashboard layouts — each with a schema, a loader, a location on disk, and a
fail-safe test for malformed input. When Alexander-the-developer ships (DEFERRED D.1), it
writes into that surface only. The user's ARMADA stays the official build plus their plugins;
updates still apply; reverting a change is deleting a file. It runs as a separate process with
its own checkout, as Mihai specified — the separation is what keeps the blast radius small.

## Consequences

- Phase 3 (docs) precedes Phase 6 (Alexander): the guide's quality is capped by the docs.
- Alexander's system prompt is a document in `docs/dev/`, reviewable like any other.
- One outbound action, user-initiated: *report an issue* (ADR-005). Alexander assembles the
  report, shows it, and sends it only when the user confirms. That is a send, not a write to
  realm state or code, and it is the only action Alexander takes in v1.
- Phase 2 must design extension points for a consumer that does not exist yet. The test of the
  design is that at least one *built-in* feature uses the surface before Alexander does — a
  plugin surface nothing uses is a guess.
- **The surface:** [`docs/dev/EXTENSION_POINTS.md`](../dev/EXTENSION_POINTS.md) (contract v1, 2026-09-24,
  `matcap/addons.py`). Called *add-ons*, not plugins, because "plugin" is already a capability kind.
  No built-in consumes it yet; the doc names themes as the cheapest first one.
- We give up, for v1: "ask the app to change itself". Users get it later, in a form that
  survives updates.
