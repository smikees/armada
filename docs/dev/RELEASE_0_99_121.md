# 0.99.121 — Agent tool limits and file write scopes

Agents previously received whole connectors, and filesystem reach could let an
agent change another agent's skill code. Owners can now configure individual tool
patterns, realm default denials, per-agent file scopes and realm read-only paths.

The [access-policy contract](ACCESS_POLICY.md) records schema, exact precedence,
closed inventories, adapter enforcement, builder exemption, and the unavoidable
shell restriction on scoped Windows turns. Owner changes are atomic and logged.
Runs retain offered-tool and refusal evidence and produce operational warnings;
the first refused access per agent per day emits a deduplicated owner notification.

Synthetic tests cover all three adapter lists, denied order/allowed read tools,
deny precedence, default exceptions, malformed admission, protected writes,
path traversal, control-file protection, builder exemption and durable reporting.
Actual Claude, Codex and Gemini CLI probes used only a temporary synthetic
connector and files: the permitted read and file write succeeded, the order tool
was unavailable, and the protected skills write was refused and audited.

Automatic inventory refresh depends on the provider's no-model introspection.
Claude and Codex provide this; current Antigravity startup reports its general
builtin registry, not concrete connector schemas. Owners can record connector
tool names in the UI on any provider. Exact lists are enforced on all three;
an unavailable inventory never falls back to unrestricted tools. Gemini's actual
CLI was also checked with a wildcard name: it did not admit the read tool, so
ARMADA deliberately expands globs to exact names before configuring the CLI.

No personal finance realm or credentials are included in tests or source. The
owner's running app is neither restarted nor upgraded during validation/publication.
This release continues the existing maintenance beta distribution: update assets
are signed, while Windows publisher signing and clean-Sandbox acceptance retain
the documented maintenance-release boundary.

The hidden WebView2 probe passed tool visibility, invalid-path feedback, unchanged
state on failure, owner save/reload and change-log checks. Light and dark captures
were inspected at 1280 and 720 pixels. Existing capability-card and command-job
fixtures were updated for the added policy panel and required authorization files;
the focused regression group passed 149 tests. No authorization assertion was removed.
Claude's synthetic no-model inventory check passed after waiting for connector startup.
Read-only model metadata on November 4 confirmed the shipped preferred Claude Opus,
Codex Sol and Gemini Flash entries; defaults remain unchanged.
The existing hidden inspector/dry-run UI probe also passed. A further 110 focused
tests cover preserved native reads, disabled shell/writes and managed draft behavior.
The bundled Python runtime remains 3.12.10; the
[3.12.16 source-only security release](https://www.python.org/downloads/release/python-31216/)
was reviewed. Updating that runtime remains a separate installer compatibility change.

## Publication evidence — November 4, 2026

Published [v0.99.121](https://github.com/smikees/armada/releases/tag/v0.99.121)
from source `1c632e134bcc1a819283d57daf9e137613f5486f` through
`tools/publish_release.py --maintenance-unsigned`. The publisher's exact-source
isolated suite passed **3,909 tests, with 5 skipped**.
[Windows CI](https://github.com/smikees/armada/actions/runs/41873358661)
passed both Python jobs and the relay job. The final policy group includes 35
checks, including saved dry-run command denial and refusal to grant a withheld
filesystem capability through a write scope.

Packaged validation passed native recovery at all five interruption points,
16 WebView2 session checks, 68 tray lifecycle checks and 69 signed-update upgrade
checks. Evidence is retained outside version control in
`build/release-evidence-0.99.121.json`, `build/tray-lifecycle-staged.json` and
`build/upgrade-0.99.121.json`. Synthetic UI and actual-provider probes used only
temporary data; the owner's running app was not restarted or upgraded.

All four public assets were downloaded and compared byte-for-byte with the build.
The Ed25519 manifest signature, source commit and package hash were verified,
and all 446 package files matched the committed application source.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `armada-0.99.121.zip` | 7,115,049 | `9aef8183b164ed9fc6abeb177e6f5ccc1f8f84b12bdd85058e8b59197d1e4dee` |
| `ARMADA-Setup-0.99.121.exe` | 22,024,699 | `5a5d24cd6c186a7e689fbdb03c759fbaf91f13324609440be1301895c3a9cc3c` |
| `armada-update.json` | 349 | `ce093241a528e1bc695ae17ef9f0e30e5bb5e07a6d7d0651fa24c58158783509` |
| `armada-update.json.sig` | 89 | `80bd69521f902d9fbcb77b1403b9a7379ff9e157898a02d238abe7a112afde89` |

[armada.stamih.com](https://armada.stamih.com/) was deployed through the documented,
certificate-validated FTPS procedure, with replacement backups under private
deployment `20261104T171801Z`. The public page displays 0.99.121 and its installer
link returns the exact verified installer bytes. Public HTML matches source after
normalizing line endings and removing only the exact pre-existing hosting analytics
snippet. Its fetched SHA-256 was
`7866623557ea4336a68d1616b0dfe190ca89bfebafd21fc7e4e357ce2e3532ce`.

The maintenance beta boundary is unchanged: the Windows installer is unsigned,
and clean-Sandbox GUI acceptance is not certified. Update assets are signed.
