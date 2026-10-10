# 0.99.100 verification

Engine reach for capabilities, from [the implementation plan](CAPABILITIES_UPGRADE.md). The
Capabilities page, model pickers, execution policy and agent context share one answer
(`armada/capreach.py`) to which engines can use each capability. No credentials move between
engines; ARMADA still never signs in or out for the owner.

## Behavior and boundaries

- Reach is derived from the record: skills and local extensions work with any engine; open
  servers (public HTTPS MCP) work with any engine, signed in per engine; connectors hosted by
  Anthropic are Claude only; ChatGPT apps are Codex only; Claude Code plugins are Claude only.
  Explicit `reach` on rows created for one engine wins.
- One engine at a time: Interactive Brokers is recognised by endpoint host or catalogue key
  (IBKR staff: authorising a new AI platform disconnects the previous one). The owner can mark any
  other service. Such a capability is admitted only on its current engine; Move previews who gains
  and loses it, then saves `exclusive_engine` under the realm lock. The provider sign-in remains
  the owner's step.
- `provider_policy` denies a capability outside an engine's reach, or held on another engine,
  before alias mapping, so a stale registration (a Claude connector after a move) cannot admit it.
- Provider turns name granted-but-unavailable capabilities to the agent with the reason; test
  engines keep the previous inventory text. Model pickers on agents and jobs show the impact live
  (`/api/engine-impact`); save-time review lists each capability lost and missing sign-ins.
- Provider-hosted services are added for one engine ("Gmail · Claude", "Gmail · ChatGPT app").
  Open servers remain one row for every engine.
- Realm format v4 splits a row that mixed a ChatGPT app with another service into its own Codex
  row; agents currently on Codex are granted the new row, and original grants stay. Idempotent;
  rows without mixed bindings are unchanged; a newer realm is left untouched.
- Add a capability shows each result's reach and filters by Works with. Provider directory
  listings and per-run injection of open servers are Phase 2 (see the plan), not this release.

## Checks

- `tests/test_capreach.py`: reach rules, one engine at a time, impact text, policy denial before
  and after a move, agent context, v3 → v4 migration (split, grants, idempotence), move/exclusive
  routes, engine-impact endpoint, per-engine provider rows, sectioned page, model hint, catalogue
  filter, and a Node harness for the switcher and stale-answer-safe hint.
- Updated connector tests for per-engine provider rows and IBKR's single-engine card.
- Golden pages regenerated after the version and changelog; diffs reviewed: the new icon entries in
  the shared icon map, the sectioned Capabilities page, the agent reach summary, the changelog and
  the help page.
- Visual review of the Capabilities page (light and dark), an expanded one-engine-at-a-time card,
  the connector dialog and an agent's Configure page, rendered from a migrated COPY of the owner's
  realm; the original realm was not modified.

## Results

The full Windows suite passed with the release changes in place: **3,589 tests passed, 5 skipped,
0 failed** (Python 3.12, offline fake transports). Publication evidence (exact-source CI, native
session and packaged upgrade gates) is recorded under `build/release-evidence-0.99.100.json` when
the maintenance publisher completes.
