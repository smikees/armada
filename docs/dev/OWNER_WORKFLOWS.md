# Owner workflows and their boundaries

M11, November 2026. These refinements preserve the existing visual language and
saved dashboard layout; no provider or permission defaults change.

## Permissions before saving

Agent Capabilities now offers **Preview agent access** and **Preview defaults for
this agent**. Both use `access_policy.preview` through the authenticated, realm-bound
POST route. Preview shares the exact candidate-update helper and validator used by
Save. It does not write policy, append an audit receipt, discover tools or invoke a
provider. Malformed candidates fail validation. Realm previews validate the proposed
defaults against the other agents as well.

The result compares current and proposed access using the same local compiler as
execution (`tool_admission.compile_rules`), recorded names and current connector
grants. Literal allow names need no inventory and are labeled if not yet recorded;
missing glob inventories show the run refusal. Aliases to one registration
intersect, unsupported connections remain unavailable, and a scoped native
filesystem is shown as replaced by the guarded file tool. Deny wins; an explicit agent allow can override a realm
default denial but cannot grant the connector. Unknown inventory is labeled as
incomplete. Builder exemption, write scopes, read-only paths, disabled shell/native
writes and protected control records are stated separately.

Preview is advisory, not an authorization token. Changes invalidate its display.
Save remains a separate owner action with the existing locked atomic mutation and
audit log. Every run still validates canonical permissions and provider reach fresh.
The UI does not equate a supported connection with permission to call every tool.

## Keyboard and responsive presentation

The shared confirmation dialog starts destructive actions on Cancel. Enter on Cancel
cannot confirm; typed confirmations still support Enter in their input. Shared
modal focus ownership traps Tab, handles Escape only in the top dialog, names the
dialog and returns focus to its opener. Lazy avatar/changelog dialogs use the same
focus owner. This is not a claim that every older modal or screen is fully audited.

At narrower widths the main navigation uses two rows, with scrollable page links
and the account actions remaining reachable. Dashboard widgets occupy full rows
without overwriting saved desktop spans. The register has its own keyboard-focusable
horizontal scrolling region. Subscription-limit content adapts to the available
width; truncated reset text retains its full tooltip. Shared focus indicators remain
visible. Native checks cover a 1024-pixel window and 150% WebView2 zoom, not every
Windows display scaling configuration or a full WCAG conformance audit.

## Visible outcomes

Overview summarizes local damaged records, today's failed/interrupted runs and
pending job/capability approvals, with links to review. Reads of run history are
date-bounded. An unreadable source shows an unavailable message rather than an
all-clear. The summary is a page-load snapshot, not live provider health or an
assertion that all problems are resolved.

Access saves show working/error/success states and carry the success receipt over
the reload. Edits are disabled while the request runs. An unconfirmed mutation says
to reload and check; it is never automatically retried. Preview itself is read-only.

Dashboard layout writes serialize and coalesce later edits. The UI reports success
only after the server acknowledges it. A failure/timeout stops further layout saves
in that page until reload, preserving the authoritative copy and avoiding races with
an unknown outcome. It does not merge concurrent edits from different windows;
separate windows still have last-completed-write semantics.

## Evidence

`tools/owner_workflow_probe.py --output build/owner-workflows.json` uses a temporary
account, synthetic realm, disabled job proposal and mocked provider endpoints. It
checks cancellation, focus, 1024px/150% layouts, preview byte preservation, ordered
layout saves and refusal reporting. Visual captures render the native DOM in an
isolated Chromium profile at the native logical viewport size.

`test_access_preview.py` compares previews against saved policy across all three
providers and checks malformed policies, realm exceptions and unchanged bytes.
`test_attention_summary.py` checks actionable links, escaping and unreadable sources.
Existing capability, confirmation, provider and dashboard regression suites remain
part of the full release gate. The design detector's findings were pre-existing
accent-border patterns; no visual-system replacement is part of this milestone.
