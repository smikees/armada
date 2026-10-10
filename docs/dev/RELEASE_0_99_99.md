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

## Published evidence — 2026-10-10

- Published normal/latest [v0.99.99 release](https://github.com/smikees/armada/releases/tag/v0.99.99)
  from source `27e4bdbb987aa1efcc1023bf358d21be7bd28e83`.
- Pinned isolated suite: **3,555 passed, 5 skipped**. The initial gate exposed two test-harness
  issues (an incomplete DOM mock and an asynchronous-probe timing assumption); both were
  corrected before rerunning the entire gate. No failed gate was bypassed.
- [Exact-source CI](https://github.com/smikees/armada/actions/runs/38045439115): both Windows
  Python configurations and the relay check passed.
- Native launcher recovery passed at all five interruption points; all 16 multi-window
  session checks and 63 packaged upgrade checks passed, upgrading 0.99.98 to 0.99.99.
- Fresh public downloads of all four assets match their local build hashes. The public
  Ed25519 manifest verifies, identifies the exact source commit, and matches the ZIP's
  size/hash. All 338 packaged source files match the committed source.
- Browser review covered search/filter/import/empty states, keyboard focus, narrow picker
  layout and light/dark themes. The fixed footer remains visible while the picker body
  scrolls. Final design review disposition: **Ship**. This does not claim responsive
  acceptance of the entire existing Capabilities page.
- Published the website's version, release and installer links using verified FTPS with a
  prior-page backup. Public HTTPS content matches the committed page after removing the
  hosting provider's known injection. The installer downloaded from that page matches
  the tested build. Other hosting files were unchanged.

| Public artifact | SHA-256 |
| --- | --- |
| `ARMADA-Setup-0.99.99.exe` | `6177b22d504afb291c4ba75d88a24d21cb1f6cbca1b3a82e2a553ef0e25a6c08` |
| `armada-0.99.99.zip` | `9416c5db2b6b79d8640f10350c0cac94ca8c0571431209a7398c941a2c517aa9` |
| `armada-update.json` | `dc1807a325c7cede9f3fde82f7346c11c890935fe058d1c806aa1c48a37b2e91` |
| `armada-update.json.sig` | `8341154f2adf8304284bb66c8e3758d20180eddd17249a3b20846ea25baf16ec` |
| Website source `index.html` | `aeb125da9761cc52eab2590d2b66385bb51bc50c1eca696408c0804a5316b65f` |

Local evidence: `build/release-evidence-0.99.99.json`, `build/upgrade-0.99.99.json`,
`build/public-0.99.99-verification.json`, `build/website-0.99.99-publication.json`,
`build/native-app-scope-09999.json` and `build/connectors-*-final.png`.
The owner's running app was not restarted. This evidence-only documentation update follows
the tagged source and does not change the released application.
