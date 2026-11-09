# 0.99.136 — Timed inbox tasks and ARMADA system memory

Candidate, 9 November 2026. Publication pending.

Inbox processing windows are code-enforced, including after capacity waits.
An acknowledged owner Process now warning overrides a valid window once and
records that choice. App Settings manages shared instructions for every agent
and realm. [Behavior and boundaries](INBOX_TIMING.md).

Final focused inbox, memory, Settings, documentation and golden checks: **522 passed**.
Provider/execution checks: **117 passed**. The final native UI probe passed ten
checks. Light Settings and dark 1024px timing-warning captures were reviewed, as
were all three changed golden pages (context size, Help index and Settings).
Final committed-source stabilization, full suite, exact-source CI, packaged
lifecycle and signed-upgrade checks remain required. Synthetic fixtures only; no owner app
restart or live realm/provider testing.

Provider preferences were reviewed on 9 November against official
[Claude models](https://platform.claude.com/docs/en/models/overview),
[OpenAI models](https://developers.openai.com/api/docs/models) and
[Gemini models](https://ai.google.dev/gemini-api/docs/latest-model).
No provider/model selection changes are included; authenticated catalogues still
control availability. Python 3.14.10 and launcher protocol 2 remain unchanged.
Publication uses the existing unsigned Windows beta maintenance distribution
with Ed25519-signed update manifests. Windows publisher signing, clean-machine
WebView2 acceptance and maintainer product acceptance remain open.
