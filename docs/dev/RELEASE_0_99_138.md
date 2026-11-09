# 0.99.138 — Steer an active conversation

Candidate prepared on 9 November 2026. Publication and final committed-source
release evidence are recorded below after the gates complete.

Codex app-server conversations accept text steering while working, through the
same composer in the main and detached views. Steer appears alongside Stop only
when the current process has an active provider turn. Exact-run admission,
durable delivery receipts, explicit duplicate-safe Check, preserved later draft
edits and a full-width narrow input protect the owner workflow. Claude, Gemini,
Codex fallback and background jobs do not advertise unsupported steering.

The transport retains the turn's permissions and owns a bounded stdin writer so
stalled input cannot block timeout or Stop. Receipt mutations use the existing
history journal and keep one original user/assistant pair. Accepted instructions
survive subsequent context and compaction. Unknown delivery remains explicit.
See the [contract and limits](STEERING.md).

Focused steering, transport lifecycle, history recovery, rendering, realm-bound
HTTP, golden and logging checks: **203 passed**. The final native thread probe
passed **100 checks**, including steering from both views, typing focus,
single-turn persistence, narrow layout, synchronization and cancellation.
Light main and dark narrow companion captures were reviewed in two bounded
passes; the first pass exposed a cramped input, corrected before confirmation.
All fixtures were synthetic; no owner app restart, live realm or provider call.

Protocol was checked against official app-server documentation and generated
schemas from the installed Codex CLI. Provider preferences were reviewed against
official sources on 9 November for 0.99.136 and are unchanged. Python 3.14.10 and
launcher protocol 2 remain unchanged. Distribution continues the existing
unsigned Windows beta maintenance path with Ed25519-signed update manifests.
Windows publisher signing, clean-machine WebView2 and maintainer product
acceptance remain open.
