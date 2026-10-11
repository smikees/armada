# 0.99.108 verification

Normal chats were blocked before the model could reply when any granted connector was
unlinked, missing or signed out. A coordinator inherits every enabled realm capability, so an
unlinked GitHub row also blocked an unrelated EODHD setup request. Claude's real MCP inventory
includes a `(HTTP)` or `(SSE)` suffix; treating that suffix as part of the URL caused a false
configuration conflict. Its installed OAuth command also requires an interactive terminal.

## Changes

- Runner and adapters withhold missing, mismatched, disabled and unauthenticated connections
  individually. Invocation-local evidence and model context explain the missing operations.
  Invalid permissions, ambiguous identities, malformed inventories and ungranted callable
  native apps still fail closed. No disabled connection is implicitly re-enabled.
- Claude inventory parsing strips recognised transport suffixes and retains authentication
  state. Windows sign-in uses the provider's owned interactive console, observes exit status
  and kills the attempt at its five-minute deadline. ARMADA does not read the console or tokens.
- Normal owner chats receive an authenticated loopback MCP setup broker alongside existing
  grants: `list_connectors`, `connect_connector`, `request_connector_access`. It only prepares
  existing enabled, approved realm connectors; it cannot change endpoints, register arbitrary
  servers or grant access. Coordinators can request another agent's owner-approved access.
  Fresh grants are checked for every call; cancellation, turn completion and realm archival
  expire the broker. OAuth URLs are withheld from model replies and action audits.
- Inspectors, dry runs and scheduled jobs do not receive setup tools. Provider credentials
  remain separate. Newly connected data tools load on the following conversation turn.
- Persisted assistant status reaches the canonical thread HTML. Both thread views display
  Failed, Stopped, Completed with warnings or Done rather than a universal success indicator.

## Validation

- Targeted tests cover real Claude inventory formats, individual withholding, endpoint mismatch,
  unbound chat admission, chat-only setup, fresh revocation, owner access requests, expiry,
  cancellation, audit redaction, interactive sign-in exit/timeout and browser outcome labels.
- Installed Claude, Codex and Gemini CLIs each called the new broker's `list_connectors` in a
  synthetic realm and returned the expected empty list. No business connector data was used.
- Native thread-window probe: all 76 checks passed, including shared live/terminal transcripts,
  cancellation from either view and reopen/disconnect behavior.
- Existing release model preferences were checked against the connected providers' catalogues;
  all preferred IDs are present. No agent or job model was changed.

Publication uses the continuing owner-authorized unsigned Windows beta installer and signed
update through the unified release gate. Windows publisher signing remains pending. Full suite,
exact-source Windows CI, staged native session/recovery, packaged upgrade and public website
verification must pass before the release is complete. The owner's app is not restarted merely
to publish. Final publication evidence is recorded after the enforced gate succeeds.
