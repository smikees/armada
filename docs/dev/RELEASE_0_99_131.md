# 0.99.131 — Faster reads of long histories

M9 release candidate, 6 November 2026. Publication is authorized by the owner's
request to complete M9 and publish it. Full-source and packaged release gates
remain required; publication and maintainer acceptance are not yet recorded.

Overview and Usage use disposable summaries; recent views use date offsets.
Conversation previews have independent dependencies, concurrent windows coalesce
rebuilds and transcript metrics share the rendered snapshot. Policy and execution
admission remain fresh canonical reads. [Contract and benchmarks](HISTORY_READS.md).

The expanded synthetic regression passed **157 tests, three skipped**. The first
full-scan summary build is slower; warm reads and multi-window polling improve.
No owner app, live realm or provider was used for testing.

The native shared-window probe passed **79 checks**. Golden review showed only
the intended release notes in Settings. Final review aligned middle-of-file BOM
handling with the canonical parser; the final **30-test summary batch passed**.
The mandatory publisher will repeat the complete suite on the committed source.
The initial pinned gate passed **4,231 tests, six skipped in 685.68 seconds**.

Release-owned preferences were reviewed against official
[Claude models](https://platform.claude.com/docs/en/models/overview),
[OpenAI models](https://developers.openai.com/codex/models), and
[Antigravity models](https://antigravity.google/docs/models/) on 6 November 2026.
Existing preferences remain runtime-catalogue gated with provider-default fallback;
the UI seed catalogue does not establish account availability. No model change is
part of this performance release.

Python 3.14.10 and launcher protocol 2 remain unchanged. Publication continues the
existing unsigned Windows beta distribution; update manifests remain Ed25519-signed.
Publisher signing and clean-machine WebView2 acceptance remain unverified.
