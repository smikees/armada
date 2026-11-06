# 0.99.131 — Faster reads of long histories

M9 released on 6 November 2026 from
[`ea7df53`](https://github.com/smikees/armada/commit/ea7df53cc02bd746579140117514afe51253cc34).
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.131) and
[website](https://armada.stamih.com/) verified. The owner authorized M9 publication;
all required maintenance gates passed. Maintainer acceptance remains pending.

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
The mandatory publisher repeated the complete suite on the committed source.
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


## Final release verification

- Mandatory publisher on `ea7df53`: **4,232 passed, six skipped in 678.72s**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/42274709787):
  both configurations passed **4,234 tests, four skipped** (861.23s pinned and
  750.84s current patch); relay passed.
- Native shared-window probe: **79 checks**. Packaged launcher recovery passed all
  five interruption points; clean/legacy-parent DLL isolation passed. WebView2:
  **16 checks**; tray: **68**; visible/tray/busy restart: **69 each**; presentation
  recovery: **86**. Fresh light/dark main and compact recovery panels were reviewed.
- Signed **0.99.130 → 0.99.131** upgrade passed **72 checks**, including real-page,
  restart and cleanup checks with normal close-to-tray enabled.
- Public Ed25519 signature, exact manifest commit/version, package hash/size and
  changed application source bytes verified. Public installer matches build evidence.
  Website returned HTTPS 200 with matching version/release/installer links. Remote
  files were backed up and index.html published last.
- Installer SHA-256: `8ce756b1d419874fc7cf553a3119859de0f180ed7772f6153bf8d556c73b9931`.
- Package SHA-256: `6f6bad94fa11a3a58f8dd4b3246fc323b2611bb372986690f2ffafc6cd60c30a`.

No owner app restart or live realm/provider test was performed. Runtime and launcher
compatibility are unchanged; clean-machine Sandbox was not rerun for this app-only
release. Existing unsigned-publisher and clean-machine WebView2 limitations remain
open. See [the history-read contract](HISTORY_READS.md) for cold-read cost, cache
freshness, memory-accounting and canonical-source boundaries.
