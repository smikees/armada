# 0.99.126 — Bound local requests and provider refreshes

M4 of the stabilization plan. The cockpit and content-origin servers now bound
incomplete headers, request size, input time and concurrent handlers. Control
requests have separate capacity from ordinary work and long conversations.
Malformed JSON is an error before dispatch, rather than silently becoming `{}`.
Provider refreshes and the older auth-status endpoint share in-flight observations;
unchanged observations skip configuration writes. Disconnect remains authoritative.

See [the HTTP resource contract](HTTP_LIMITS.md) for exact limits, single-request
connection semantics and the remaining local-flood/slow-reader boundaries. There
is no automatic replay of mutations or agent work. Security checks remain required
in every lane. The native launcher/runtime baseline is unchanged from 0.99.125;
versions through 0.99.124 still require the full installer.

## Validation

182 targeted HTTP/provider/authentication/realm/content tests passed. 297 final transport/concurrency, reference and golden-page checks passed, including
21 socket/concurrency cases and streaming beyond the input deadline. Full
pinned/CI/native/upgrade gates and publication remain pending. Tests use synthetic
realms and provider observations; the owner's running app is not restarted.

The existing unsigned-maintenance distribution continues. Publisher signing and
clean-machine WebView2 GUI acceptance remain unverified until explicitly recorded.

Provider defaults are unchanged; official provider model metadata is reviewed at
this release boundary and connected-provider catalogues remain authoritative.

Official model metadata reviewed 5 November 2026:
[Claude](https://platform.claude.com/docs/en/models/opus-5-5/overview),
[Codex](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Gemini](https://aistudio.google.com/docs/models/gemini-3.8-flash).

## Native Stop investigation

The first auxiliary native thread-window run timed out waiting for Stop from the
observing main window while the full suite was running. Publication was stopped.
The 0.99.125 baseline passed 76 checks, as did four instrumented M4 repetitions;
every recorded Stop response reported a cancelled backend turn.

The probe's readiness check reused text present in previous turns and could compare
equal old snapshots. It now additionally requires the current turn's text and an
enabled Stop button before clicking. Failure evidence records button state, active
run count and synthetic cancellation responses. The original timeout's cause was
not conclusively established; no production cancellation fix is claimed.

Three sequential runs of the strengthened probe passed **79 checks each**, including
Stop in sender/observer windows, stale run IDs, disconnect and reopening during work.
Evidence: `build/thread-window-m4-final-{1,2,3}.json`. The framing suite also passed
21 checks after explicitly accepting legal trailing HTTP header whitespace.
