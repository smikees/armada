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
