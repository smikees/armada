# 0.99.99 verification

Service-first connector discovery extends ARMADA's existing capability cards, controls,
tokens, disclosures and confirmation dialog. One realm capability can bind independent
Claude, Codex and Gemini registrations. No credentials are transferred between providers.

## Behavior and boundaries

- Search by service or task words, filter by category/engine and review integration guidance
  before adding. Initial services: Drive, Gmail, Calendar, Slack, GitHub and Notion. Native
  provider directories and existing-registration import cover other services; custom HTTPS
  MCP remains an explicit advanced path. Discovery does not call providers while rendering.
- Optional account/workspace labels are owner assertions. The UI never presents them as
  verified identity. Engines must expose separate registrations for multiple accounts.
- Link/unlink uses locked atomic realm writes. A tombstone prevents legacy registration
  inference after unlinking; other engines and shared provider credentials are untouched.
- Agent chips report their default engine's connection state. Agent/job engine switches
  require owner review before saving. Runtime admission checks remain authoritative for
  every turn, including inherited realm defaults and fallbacks. Operation parity is not assumed.
- Native Codex apps are admitted through actual app-server thread inventory, with only granted
  app IDs callable. Ambient apps, plugins and hooks remain disabled. Explicit owner-disabled
  apps and per-tool restrictions are preserved. Inspectors/dry runs never gain these apps.
- CLI verification found two native ID families (`connector_` and `asdk_app_`); both are
  validated without allowing dotted config keys. Public plugin metadata was checked for the
  offered native integrations; these checks did not authorize services or access content.
- The earlier synthetic real-CLI probe created, read and edited one synthetic MCP document
  across Claude, Codex and Gemini; registrations were cleaned up. The real Codex scope probe
  confirmed only one approved app was callable, without sending a model prompt.

Native Google OAuth and live document editing still require the owner's provider consent.
Synthetic probes do not certify those flows. Gemini registration remains explicitly unverified
where its CLI cannot provide live tool health. Provider availability and operation sets can change.

## Release gate

Publication uses the enforced maintenance publisher: isolated pinned tests, exact-source Windows
CI, native recovery/session checks and signed-asset packaged upgrade. Evidence is written under
`build/release-evidence-0.99.99.json` and `build/upgrade-0.99.99.json` when completed.

This continues the standing owner-authorized unsigned Windows beta distribution. Installer
Authenticode and clean Windows Sandbox acceptance are not claimed. Update manifests remain
Ed25519-signed. Runtime/bootstrap compatibility is unchanged; the owner's app is not restarted.
The release includes publication and HTTPS verification on https://armada.stamih.com.
