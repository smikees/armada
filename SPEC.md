# ARMADA product specification

**Create, empower and control your army of agents.**

ARMADA is a Windows desktop app for standing teams of AI agents. Each team lives
in a local folder, called a realm. Agents have roles, memories, goals, conversations,
capabilities and scheduled jobs. Users direct the work and control each agent's access.

## 1. Providers

Claude Code (Anthropic), Codex CLI (OpenAI), and Gemini through Antigravity CLI
(Google) are supported engine choices. Any one connected provider is sufficient;
users may connect more and select different providers per agent or job. ARMADA
runs independently of provider desktop apps and reuses each CLI's saved login.
Account eligibility, models, quotas and tools depend on each provider. Connecting
one does not authorize another provider's connectors.

New teams choose defaults from authenticated engines available after setup.
Release-owned model preferences are used only when the provider reports the model.
Unknown catalogues fall back to provider defaults. Explicit saved choices are preserved.
A release preference does not make any engine a prerequisite.

## 2. Realms and agents

A realm is a portable folder of Markdown, JSON and generated files. Templates change
labels and starter profiles, not the storage model. Each realm has a coordinator and
agents with mandates, personalities, tenets and autonomy settings. The
[schema](docs/dev/SCHEMA.md) defines current files and compatibility fields.
Provider credentials remain outside exported realm data.

## 3. Conversations and memory

Agents have main and scoped sub-threads. Context includes the realm brief, relevant
memories, the agent's role and recent conversation. The UI shows context composition
and usage. Journaled compaction preserves concurrent messages. Provider-dependent
memory controls are documented in [Memory boundaries](docs/dev/MEMORY_BOUNDARIES.md).

## 4. Capabilities and authorization

Users grant tools, connectors, skills and plugins per agent and choose approval policies.
Availability is checked for the actual provider. Unsupported combinations explain the gap.
An agent with tools acts with the user's permissions; arbitrary shell and connector
access are not a security sandbox. See [Staying safe](armada/docs/user/safety.md).

## 5. Jobs and results

Jobs run manually or on schedules with timezones, bounded retries and durable claims.
The scheduler serves registered active realms while ARMADA is open or in the tray.
Archiving disables a realm's jobs; deletion requires typed confirmation.
Run results separate execution, audit outcome, delivery and evidence. A completed
report can contain findings or incomplete evidence. Original answers and specific
operational errors remain visible.

## 6. Desktop lifecycle and updates

One desktop/server instance owns an OS account regardless of realm, install path or
port. Reopening activates the existing window. A separate owned scheduler is an
internal service, not a second desktop. Full quit stops scheduled execution.
Installed copies verify signed update manifests and packages and apply compatible
updates through a stable recovery bootstrap. Updates wait for actual active work
across realms and block new admissions. UI progress distinguishes work, scheduler
shutdown and restart. Bundled dependency changes require an installer.

## 7. Distribution

The beta includes Python and requires WebView2. Setup can install the selected
provider CLIs and guide sign-in. Source is available under PolyForm Noncommercial
1.0.0; see [LICENSE](LICENSE). It is not an unrestricted open-source licence.
Windows publisher signing and clean-machine acceptance have separate release gates.

See [the README](README.md), [architecture](docs/dev/ARCHITECTURE.md) and
[roadmap](docs/LAUNCH_PLAN.md) for current use, implementation and planned work.
