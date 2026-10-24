# 0.99.113 verification

The owner reproduced different spoken and displayed replies, then explicitly selected natural
Codex voice with its actual spoken transcript used as the conversation and subsequent context.
The [investigation](VOICE_FIDELITY_INVESTIGATION.md) confirmed that appendSpeech paraphrases,
while 0.99.112 discarded native assistant transcript content.

## Changes

- Keep one normal assistant record: its native spoken words become conversation content,
  while the original backend result remains in a collapsed **Work result** disclosure.
  Task outcome, tool evidence, output artifacts and accounting remain unchanged.
- Commit spoken text only after matching browser output-sample receipt. Preserve interrupted
  text as partial; use an explicit unspoken text fallback if audio never arrives or the call ends
  before the work finishes. Audio closure does not cancel accepted normal work.
- Supply actual spoken wording to the next queued turn. Recoverable history updates preserve
  concurrent appends and prevent stale compaction overwrites; pending speech cannot be compacted.
- Reduce input batching to 250 ms, watcher polling to 100 ms and audio state polling to 250 ms.
  Changes to live speech wake canonical thread refresh. This removes roughly a second of local
  batching/polling delay; it does not promise a reduction in provider setup or inference time.

## Validation

- Focused voice/thread suites and browser controls harness pass, including actual-word history,
  duplicate finals, follow-up context, retained tool output, interruption, mode switching,
  unavailable output, concurrent appends, deletion and compaction.
- Real Codex synthetic-speech tests in Chrome and native WebView2 compare persisted content
  with native output transcripts, alongside measured output samples. No owner microphone or
  conversation is used. Native voice/dictation/voice uses one microphone and peer.
- Main 1280×900 and detached 480×760 light/dark views, with Work result collapsed/expanded,
  have no horizontal overflow. Fresh finish review required no redesign and identified the
  no-audio receipt edge case, addressed with explicit receipt and fallback regressions.
- The review fix was scored resolved and the documentation handoff completed.
- Final native WebView2 voice/dictation/voice: samples 20 / 0 / 17, six stored messages,
  one microphone/peer, no JS errors, exact saved/native transcript matches for both voice replies.
  Setup took 5.7 s; saved-result-to-first-audio took 2.0 and 2.5 s. These are samples, not benchmarks.
- Native detached synchronization/Stop probe passed all 76 checks. Its first run exposed an
  existing Windows progress-file read/delete sharing race; progress reads now use the same
  lock as writers and completion. The repeated native run passed without that sharing violation.
- Final release gates and public download verification passed, as recorded below.

The task agent still receives transcribed input, not raw audio. Native speech can paraphrase
or shorten the work result; the spoken wording is now visible and recoverable. Provider
transcripts are not word-aligned physical speaker recordings. Post-gain samples demonstrate
app output, not the audibility of the owner's chosen Windows device. Voice remains experimental.
The authorized maintenance installer is unsigned; compatible updates remain Ed25519-signed.
Publishing does not restart the owner's app or change agent/job models.

## Publication evidence

Published 2026-10-24 as normal/latest
[v0.99.113](https://github.com/smikees/armada/releases/tag/v0.99.113) from source `f7e1c9c19b8d1916040d499a8a04b40bf3cb3a6c` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3738 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40123863608) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- The native detached-thread synchronization, Stop, sizing and shadow probe passed all 76 checks.
- The bounded UI finish review and documentation handoffs passed for spoken, partial and unspoken replies with collapsed/expanded work evidence in main/detached light and dark views.
- Signed compatible upgrade from 0.99.112 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values; the update signature
  verifies, and its package contains exactly 430 tracked application files,
  byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `84883ed19c3f4f4bfa798c130e40a47906e8d19b7a3117e40ad8b5d6bef18ff6`.
- Release defaults retain the same-day 0.99.112 provider-catalogue review: each primary release default is listed. Gemini no longer lists the
  secondary 3.7 fallback on this account; existing connected-provider filtering and provider-default
  fallback remain in place. No agent/job model or account settings were changed.
- The owner's running application was not restarted. Windows publisher signing remains pending;
  the maintenance installer is unsigned and the update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.113.zip` | `ade41e201f29f88dfb337d55f66ad52e4ce2aaf4b7c4e38558afa80ff83f5a2c` |
| `ARMADA-Setup-0.99.113.exe` | `5fd8941400c2d74bd03b6cb53d767a1d77bcc32d38ce9913d950f46f2f13d0c8` |
| `armada-update.json` | `e6bcde2982f08342fcb6c2dade533dd999252abd00506c428463c3d59e39506f` |
| `armada-update.json.sig` | `e1a14883c79596d1326d7546d01293648036f75df3f08b83d2ad74d325de4ad3` |
