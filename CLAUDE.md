# ARMADA contributor guide

ARMADA supports Claude Code, Codex CLI and Gemini through Antigravity CLI as equal
provider choices. Users can connect any one or any combination. No specific
provider account or development model is required to contribute.

Read [the specification](SPEC.md), [architecture](docs/dev/ARCHITECTURE.md),
[roadmap](docs/LAUNCH_PLAN.md) and [release procedure](docs/dev/RELEASING.md).
The maintainer approves acceptance milestones; passing tests alone do not complete them.

## Working conventions

- Route model execution through the engine adapter and selection interfaces. Respect
  provider-specific authentication, tools and telemetry; never silently require another provider.
- Keep personal realms and credentials out of source control and tests. Use synthetic fixtures.
  Modify live data through application APIs with authorization.
- Use shared locking and atomic-write utilities for realm mutations. No network on page-render paths.
- Use `desktop_launch.spawn()` for independent Windows launches and the account-wide instance guard.
  Do not restart the user's app merely to publish a release.
- Run the pinned isolated release gate. Regenerate module references and intentionally changed
  golden pages, reviewing every diff. Keep version, changelog, docs and release metadata current.
- Publish signed update assets and the installer under the release procedure. Website deployment
  is a separate authorized action. Windows publisher signing is distinct from update signing.

## Repository map

`armada/`: app; `armada/engine/`: adapters; `armada/webui/`: UI;
`armada/docs/user/`: in-app docs; `tests/`: isolated tests; `docs/`: engineering;
`website/`: landing page.
