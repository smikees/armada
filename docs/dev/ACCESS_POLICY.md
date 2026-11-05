# Connector tools and file writes

Added in 0.99.121. `access_policy.py` validates policy, `tool_admission.py` compiles
connector globs to concrete per-run lists, and `policy_tools.py` checks file writes.
The owner configures these on Agent → Capabilities. Existing server grants still
apply: a tool allow never grants a connector, enables a disabled server, changes
provider reach, or transfers another provider's authorization.

## Schema and precedence

Agent JSON:

```json
{
  "tool_policy": {
    "broker": {
      "allow": ["get_*", "search_*", "create_order_instruction"],
      "deny": ["submit_order", "preview_order", "modify_order", "cancel_order"]
    }
  },
  "write_scope": ["Finance/desk/**", "agents/desk/**"]
}
```

Realm JSON:

```json
{
  "tool_policy": {
    "broker": {"deny": ["*order*", "create_alert", "update_alert", "delete_alert",
                         "set_alert_status", "create_watchlist", "update_watchlist", "delete_watchlist"]}
  },
  "read_only": ["skills/**"],
  "policy_builder": "builder"
}
```

Connector keys are exact logical catalogue IDs, translated through the owner's
provider bindings. Tools use case-sensitive shell globs (`*`, `?`, character
classes). Agent deny wins over everything. An agent policy requires `allow`:
only matching tools survive, and an empty list exposes none. An explicit matching
agent allow overrides the realm's default deny, including a matching allow glob.
Without an agent tool policy, the realm default removes matching tools from the
otherwise granted connector. Coordinators have no exemption from these rules.

Malformed types, unknown fields within a policy, unknown connector IDs, broken
globs and invalid path patterns are validation errors before engine selection or
context compaction. Policies are validated even on text-only and inspector turns.
Command jobs also validate policy and cannot run with file restrictions.

## Tool inventories and adapters

Patterns compile against names in the connector's `tool_names` catalogue field
and `.armada/tool-inventory.json`. Exact allow entries can be admitted without a
cached inventory. A glob policy with no inventory stops the run with a repair
message; it never falls back to unrestricted access. New tools stay outside the
concrete allowlist until refreshed. Inventory names contain no credentials.

The owner can refresh names or record exact names from the connector's tool list.
Claude exposes a no-model SDK control inventory and Codex exposes a no-model
app-server inventory. Antigravity versions that omit concrete connector names
from startup cannot refresh automatically; use **Record tool names** on the same
page. This is an inventory limitation, not a weaker permission mode. All three
providers enforce the same compiled list. Provider credentials remain local to
the provider. Native Codex apps with a tool policy are rejected; link an MCP
registration for that connector instead.
Existing provider tool allow/deny lists are intersected, never replaced by wider
ARMADA grants. An inventory refresh waits for connector startup without a model turn.

Restricted turns require the verified CLI versions or newer: Claude Code 2.1.263,
Codex CLI 0.157.1 and Antigravity 1.5.0. Older or unrecognized versions fail before
the model turn instead of silently ignoring a configuration field.

| Adapter | Tool restriction | File restriction |
| --- | --- | --- |
| Claude | Main custom agent `tools` is the closed schema list; `--disallowedTools` also removes explicit denies. `--allowedTools` alone is not used as a security boundary. | Native write, shell and child-agent tools are removed; guarded MCP filesystem tools perform writes. |
| Codex | Per-server `enabled_tools` and `disabled_tools`; an empty permitted list disables the server. | Read-only native sandbox, shell/unified execution/code mode/image generation disabled; guarded MCP filesystem writes. |
| Gemini / Antigravity | Per-server `enabledTools` and `disabledTools`, no inherited MCP/customizations. | Native write tools omitted, command execution off and command/unsandboxed execution denied; guarded MCP filesystem writes. |

The known filesystem extension is withheld in scoped turns and replaced by the
guarded file tools, so its legacy paths cannot bypass the write scope. Remote
connectors can have their own side effects; a local write scope is not a remote
service authorization policy. Configure their tool policy separately.

## Write boundary

Paths are relative to the realm. Both slash styles work. `*` matches within a
path segment; `**` crosses folders. Matching is case-insensitive on the supported
Windows platform. Omitting `write_scope` preserves the existing write authority
except for realm read-only paths; `[]` allows no writes. Read-only wins over an
agent's write scope. Native reads and guarded read/list operations remain available.

Targets are normalized and checked for traversal, alternate data streams, reserved
Windows names, symlinks, junctions and reparse points before creating a directory
or writing. The guarded write re-reads policy and rechecks the target under the
shared file lock, then uses the atomic write utility. Broad own-folder grants do
not allow overwriting agent/realm authorization or hidden provider/control files.
The shared `control_files` classification also protects live jobs, run reports and
annotations, threads, profiles, notification state, managed inbox/goals and nested
realms. Inspector output grants use the same reserved names and managed trees.

Within an owner's scope, the guarded file tool preserves two agent-authored workflows:
the agent's own `memory/*.md` notes and `jobs/_pending/*.json` proposals. Proposals
must pass job validation and match their filename; the broker strips `approved_at`,
sets the actual agent as proposer and keeps the proposal disabled. The scheduler
never discovers pending files. Only the owner approval operation creates a live job.
Other agents' notes and proposals remain control data, even under `**` grants.
Read-only rules and write scopes still apply to both exceptions.

Windows shell commands cannot be safely confined to arbitrary path globs by these
adapters. Shell is therefore unavailable whenever `write_scope` or realm read-only
paths apply, including command jobs. This also disables script-based workflows in
those turns; there is no prompt exception. The builder ID is set by the owner in
`policy_builder` (default `builder`) and is exempt from file restrictions. Owner
application actions are unaffected. The builder is a trusted role, not the realm
coordinator; connector tool restrictions still apply to it.

Dry runs follow the same policy: saved draft commands cannot bypass shell denial,
and model-chosen draft writes must satisfy the scope. ARMADA's private dry-run
storage is a control folder, so scoped agents cannot write draft artifacts there.
Application-owned run records and final answers are still saved normally.

## Owner changes and audit

The authenticated owner API saves policy and `_policy_changes` together in one
locked atomic JSON replacement. There is no model tool for granting permissions
or editing these policies. Each log entry records timestamp, owner actor and
before/after values. Connector lists are refreshed again after context assembly;
file policy is checked at each write. Mid-run connector changes take effect next run.

Every run result has `access_audit` with `offered_tools`, `denied_attempts` and
`warnings`, plus `operational_warnings`. Adapter startup evidence and compiled
lists record offered tools. Provider-reported attempted calls and guarded file
refusals retain tool/path/reason, never file contents or tool arguments. Only
observable tool attempts can be recorded; text in a model's private reasoning is
not an attempted call. A refusal becomes a warning, without replacing the answer.
For an unrestricted Gemini connector whose CLI does not report individual names,
the audit records its full server namespace (`mcp__server__*`). Restricted
connectors always record the concrete compiled tool list.
Job results expose the audit and include the warning in application verification.

The first refusal per agent per local day claims `.armada/policy-notifications.json`
under a shared lock and emits `policy_denied` through the owner's notification
settings. Later attempts remain in their individual run audits without another
notification. No personal finance realm is changed by installing this release.

## Verification

`tests/test_access_policy.py` uses synthetic realms for all three adapter lists,
deny precedence, default exceptions, malformed admission, write boundaries,
builder exemption, atomic owner changes and durable warning/notification behavior.
`tools/access_policy_probe.py` runs actual provider CLIs against a harmless local
synthetic connector and temporary files. It checks a read, an absent order tool,
a refused protected write and a successful permitted write. It never starts,
restarts, or upgrades the owner's running application.

Provider references: [Claude tool lists](https://code.claude.com/docs/en/sub-agents),
[Codex MCP configuration](https://developers.openai.com/codex/config-reference/),
[Antigravity MCP filters](https://antigravity.google/docs/mcp).
