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
- Release gates and public publication evidence will be recorded after they complete.

The task agent still receives transcribed input, not raw audio. Native speech can paraphrase
or shorten the work result; the spoken wording is now visible and recoverable. Provider
transcripts are not word-aligned physical speaker recordings. Post-gain samples demonstrate
app output, not the audibility of the owner's chosen Windows device. Voice remains experimental.
The authorized maintenance installer is unsigned; compatible updates remain Ed25519-signed.
Publishing does not restart the owner's app or change agent/job models.
