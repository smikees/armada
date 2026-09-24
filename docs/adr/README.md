# Architecture decision records

One page each: the situation, what was decided, what it costs. Written so a later session — or a
later Mihai — can see *why* without re-deriving it, and so a settled question stays settled.

A decision is **Accepted** when Mihai says so. Superseding one means a new ADR that names the old
one; the old one is not edited.

| # | Decision | Status |
|---|---|---|
| [001](ADR-001-single-engine.md) | Claude is the only engine for v1 | Accepted 2026-09-21 |
| [002](ADR-002-alexander.md) | Alexander: a guide in v1, a developer via extension points later | Accepted 2026-09-21 |
| [003](ADR-003-council.md) | The Council: plan-only, proposals as output, coordinator-curated | Accepted 2026-09-21 |
| [004](ADR-004-catalogue-reframe.md) | The Catalogue is search + bring-a-link, not browse | Accepted 2026-09-21 |
| [005](ADR-005-beta-launch.md) | The first launch is a labelled beta to an invited group | Accepted 2026-09-21 |
| [006](ADR-006-platform.md) | Windows for the beta; macOS in scope after | Accepted 2026-09-21 |
| [007](ADR-007-licence.md) | Source-available: free for personal use, commercial by agreement | Accepted 2026-09-21 |
| [008](ADR-008-name.md) | The name is ARMADA; internals stay `matcap` for the beta | Accepted 2026-09-24; internals policy superseded by 010 |
| [009](ADR-009-installer.md) | Installer: private embeddable Python + app source, per-user Inno Setup | Accepted 2026-09-24 (unsigned for the beta) |
| [010](ADR-010-internal-rename.md) | The internals are renamed `armada` too | Accepted 2026-09-24 |

Format: **Context** (what's true that made this a question) · **Decision** · **Consequences**
(what we now have to do, and what we've given up) · **Status**.
