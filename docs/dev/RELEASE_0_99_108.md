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
  Refreshing grants preserves engine reach, so a Claude-only connector cannot reappear on
  another provider through legacy alias translation.
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
- A real Claude turn admitted EODHD as connected with 100 tool schemas after owner sign-in;
  no EODHD data tool was called. The existing owner grants were preserved.
- Native thread-window probe: all 76 checks passed, including shared live/terminal transcripts,
  cancellation from either view and reopen/disconnect behavior.
- Existing release model preferences were checked against the connected providers' catalogues;
  all preferred IDs are present. No agent or job model was changed.

The first full gate correctly refused publication on 16 legacy assertions. Those fixtures
assumed Claude-hosted connectors were portable without another provider binding, or that
normal chats had no host setup broker. Updated fixtures declare public endpoints and independent
bindings; new assertions retain filesystem boundaries and explicitly reject cross-provider
use of Claude-only connections. Focused Gemini/translation validation then passed all 62 tests.
A fresh exact-source full gate is required for the corrected test commit.

Publication uses the continuing owner-authorized unsigned Windows beta installer and signed
update through the unified release gate. Windows publisher signing remains pending. Full suite,
exact-source Windows CI, staged native session/recovery, packaged upgrade and public website
verification must pass before the release is complete. The owner's app is not restarted merely
to publish. Final publication evidence is recorded after the enforced gate succeeds.


## Publication evidence

Published 2026-10-11 as normal/latest
[v0.99.108](https://github.com/smikees/armada/releases/tag/v0.99.108) from source
`112e4f3c723d2fe71168091851452a7f275c1a1c` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3,657 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/38157234698)
  passed before artifact staging.
- Compiled native launcher: all 5 interruption/recovery checks passed.
- Staged WebView2: all 16 multi-window session checks passed.
- Compatible signed upgrade from 0.99.107: all 69 real-page/restart/cleanup checks passed.
- Downloaded all 4 public assets and verified their sizes, SHA-256 values and update signature.
  The signed package contains exactly the 359 tracked application files, byte for byte.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup and verified temporary upload before rename. Public HTTPS page and installer download
  match the local release. Website source SHA-256:
  `16b3e56c2bc94a7154a2f757aff761eecfddfabe0a363ce47704b41f0373310c`.
- The owner's running application was not restarted. EODHD sign-in was verified separately;
  neither the provider smoke tests nor schema check read financial data.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.108.zip` | `d6a35f57450918da37f0f948ab936f178f90490b50fc638bde0c5a3d762825eb` |
| `ARMADA-Setup-0.99.108.exe` | `0d7290d93665f4508c80d877da21515be98aa2573d7880ca2f7619ca43f9b189` |
| `armada-update.json` | `f65d6e62fa69b551b581baf8be8cd8b72bb89499e9e208ec6247dd62e6826f3e` |
| `armada-update.json.sig` | `a21e8f4ba4b997ae875b714a47dd176dbf8b56020388f7c95c46c52c21d6289b` |
