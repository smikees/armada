# 0.99.132 — Less page work and smoother navigation

M10 candidate, 8 November 2026. Publication and maintainer acceptance are pending.

Math assets, avatar choices and settings menu rows load when used. Navigation
restores presentation state without saving settings or sending messages. Section
snapshots refresh in bounded background workers; failures preserve the existing
copy and report an error. [Contracts and measurements](PAGE_WORK.md).

The isolated native page-work probe passed all six behavior checks; shared-window
synchronization and Stop passed 79 checks. Light Settings and dark changelog
captures and all 21 golden-page diffs were reviewed. Full pinned
tests, exact-source CI, packaged native and signed-upgrade gates remain required.
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
