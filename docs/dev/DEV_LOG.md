# Development milestones

User-visible changes live in the [changelog](../../armada/webui/changelog.py).
Release evidence is in `RELEASE_*.md`; architectural decisions are in [the ADR index](../adr/README.md).

- Portable realm schema, file-based memory, conversations and context assembly.
- Execution, scheduling, goals, task inbox and capability grants.
- Windows packaging, tray lifecycle and authenticated local application routes.
- Recoverable writes, durable scheduler claims and signed package updates.
- Claude Code, Codex CLI and Gemini/Antigravity adapters, usable individually or together.
- Provider-neutral setup, structured job outcomes, bounded retries and run-specific evidence.
- October 2026 reliability: native CLI discovery, scoped permissions, hidden probes,
  path-safe restarts, account-wide instance ownership and accurate update progress.

Examples use synthetic realms. Private deployment histories and account diagnostics
are not part of public product documentation.
