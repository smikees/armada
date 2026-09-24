# `armada/preflight.py`

Is this realm actually able to run *here*?

A realm carries its team, memory, goals and jobs, but not the machine they were built around. Move
one to a new computer and the parts that don't travel are invisible until something fails quietly
at 03:00: the workspace folder is somewhere else, the engine isn't signed in, Telegram was never
linked so the failure notice goes nowhere either.

So a realm is checked when it arrives, and a realm that can't work is *held* rather than left to
fail nightly. A held realm is loud on arrival, which is the one moment the owner is looking at it.

Two severities, and the distinction is the whole design:

* **blocking** — every agent run would fail. No engine, no workspace. Holding the scheduler here
  prevents a week of identical failures nobody reads.
* **warning** — something is degraded but work still happens. Telegram unlinked means notifications
  don't reach a phone; the jobs still run and the bell still fills.

Never blocking: anything cosmetic, and anything about the *content* of jobs. A realm whose prompts
are wrong is not ARMADA's business.

One exception, about trust rather than correctness: a realm **adopted** from another folder holds
until its owner has seen what it will run (THREAT_MODEL T5). Its command jobs are shell commands on a
schedule and its agent jobs run with tools — someone else's realm is someone else's code. The hold
lifts when the owner allows it from the Jobs page, not when a check starts passing.

### `_check(id_, label, ok, detail, severity=BLOCK, fix='', action='')`

—

### `engine_check(engine: str='claude')`

—

### `approot_check(realm_root)`

Is this realm inside ARMADA's root folder?

### `workspace_check(realm_root)`

—

### `telegram_check()`

—

### `realm_check(realm_root)`

The realm's own files parse and hold what a realm needs.

### `job_inventory(realm_root)`

What this realm would run: every command job verbatim, and how many agent jobs.

### `adopt_review(realm_root)`

The pending review for an adopted realm, or {} if there isn't one.

### `begin_adopt_review(realm_root)`

On adopt: if the realm would run anything, record what, which holds its scheduler.

### `release_adopt_review(realm_root)`

The owner has seen it: drop the review and re-run the checks (which may still hold).

### `adopt_review_check(realm_root)`

—

### `run(realm_root, engine: str='claude')`

Everything that decides whether this realm can work on this machine.

### `_summary(blocking, warnings)`

—

### `hold_reason(realm_root)`

Why scheduled jobs are being held, or '' if they aren't.

### `held(realm_root)`

—

### `set_hold(realm_root, reason: str)`

Hold (reason) or release (empty) the realm's scheduled jobs.

### `apply_hold(realm_root, engine: str='claude')`

Check the realm and hold or release its scheduler accordingly.
