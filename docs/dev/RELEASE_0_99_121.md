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

Final gate and publication evidence will be recorded after verification.
