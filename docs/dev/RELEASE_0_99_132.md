# 0.99.132 — Less page work and smoother navigation

M10 released, 8 November 2026, from `ef761115cd3e608b0b9f8363bec1c0e93bc3c7a7`.
Maintainer acceptance remains pending.

Math assets, avatar choices and settings menu rows load when used. Navigation
restores presentation state without saving settings or sending messages. Section
snapshots refresh in bounded background workers; failures preserve the existing
copy and report an error. [Contracts and measurements](PAGE_WORK.md).

The isolated native page-work probe passed all six behavior checks; shared-window
synchronization and Stop passed 79 checks. Light Settings and dark changelog
captures and all 21 golden-page diffs were reviewed. The publisher's full pinned
suite passed **4,245 tests / six skipped**. Both exact-source Windows CI jobs
passed **4,247 / four skipped**. Packaged launcher recovery and DLL isolation,
16 session checks, 68 tray checks, 69 checks in each restart mode, 86 presentation
recovery checks and **72 signed-upgrade checks** passed. Fresh recovery captures
were reviewed. Public Ed25519 signature, package/source bytes and installer hash
verified; the matching website and download links are live.
Installer SHA-256: `6d66a88532148faf24c6272c621592a844917d712f7def29803da2d8cc2c50d0`.
No owner app, live realm or provider is used for testing.

Release-owned model preferences were reviewed on 8 November against official
[Claude models](https://platform.claude.com/docs/en/models/overview),
[OpenAI models](https://developers.openai.com/codex/models), and
[Antigravity models](https://antigravity.google/docs/models/). No model selection
change is part of this release: live catalogue validation and provider-default
fallback remain authoritative. Python 3.14.10 and launcher protocol 2 are unchanged.

Publication follows the existing unsigned Windows beta maintenance path. Update
manifests are Ed25519-signed; Windows publisher signing and clean-machine WebView2
acceptance remain unverified. See `PAGE_WORK.md` for local filesystem blocking and
HTTP deadline limits. Passing tests does not substitute for maintainer acceptance.
