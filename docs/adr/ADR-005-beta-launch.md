# ADR-005 — The first launch is a labelled beta to an invited group

**Status:** Accepted · 2026-09-21 (fields filled by Mihai the same day)

## Context

ARMADA has been built and used by one person on one machine. Every feature on the launch list
assumes strangers will install it on machines we've never seen — and the distribution work
(installer, updates, realm-format migration, a report-a-problem path) was not on the list
until the launch review. The app also has no feedback loop: nothing tells Mihai what breaks
for someone else.

A public v1 with those gaps would spend its first impression on installer failures. A beta
changes what users tolerate: they forgive a missing Council; they do not forgive a broken
install.

## Decision

The first launch is a **beta**, labelled as such in the version string, the title bar and the
About page, shipped to a **small invited group**, with an **in-app feedback path** visible on
every page. Nothing public until the beta has run at least two weeks and Mihai has decided
(launch plan step 8.5) whether it needs another round.

The feedback path (step 5.6) bundles the last N log lines, the app version, the realm schema
version, the platform and the user's own description, redacts anything that looks like a
token, and sends it to a destination Mihai chooses.

**Decided by Mihai (launch plan step 0.5):**

- **About five beta users.** Set.
- **Feedback goes through Alexander.** A support icon beside the settings gear opens Alexander;
  one of the things you can do there is *report an issue*. Alexander knows which section the
  user is on, records the user's message together with the app and section context, and sends
  the report on a dedicated channel — a dedicated email address, via a transactional mail
  service (Resend) — where Mihai or his agents pick it up.
- **Updates are automatic**, with an off switch under Settings → Advanced.

Two things that decision implies, recorded so they are built rather than discovered:

- *The user sees what is being sent before it goes.* The report is assembled — section, app
  version, realm schema version, platform, recent log lines with anything token-shaped
  redacted, and the user's own words — and shown as one message the user confirms. Alexander
  sends on that click and not otherwise. This is the one outbound action Alexander performs in
  v1, and it is user-initiated; it does not soften ADR-002's rule that Alexander writes no realm
  state and no code.
- *A sending credential has to live somewhere.* Whatever sends the email holds a key, and a key
  shipped inside a distributed app can be extracted. Two options, one to choose (step 5.6):
  (a) a **send-only** Resend key restricted to one sender address, embedded in the beta build
  and rotated when the beta ends — simplest, acceptable for five invited users, not for a
  public build; or (b) a tiny relay (one HTTPS endpoint that holds the key, rate-limited) that
  the app posts to — one more thing to host, but the key never leaves Mihai's side, and it is
  what a public build will need anyway. Recommendation: (a) for the beta, (b) before public.

## Consequences

- Phase 5 (distribution) is a hard gate for Phase 8; the clean-machine test (5.10) is repeated
  before every beta build.
- Triage is a daily habit for the beta's duration (step 8.4): each report becomes a ticket or
  a written "won't fix, here's why".
- The beta label is honest about the app's state and buys the right to ship without dark mode,
  without a second engine, and with a Council that will iterate.
- We give up: a splashy v1. A beta that works quietly is worth more than a v1 that doesn't.
