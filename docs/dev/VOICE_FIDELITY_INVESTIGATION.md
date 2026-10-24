# Voice/text divergence in 0.99.112

Investigated 2026-10-24 against source `8f76954415491165ceacf2376008a86d17207252`.
This confirmed defect led to the owner-selected contract implemented in 0.99.113:
natural Codex voice, with its actual output transcript as conversation history.
The reproduction below describes 0.99.112. See [0.99.113 verification](RELEASE_0_99_113.md)
and [the current voice contract](VOICE_POC.md#spoken-conversation-fidelity--099113).

## Reproduction

An isolated synthetic realm used real Codex signaling, generated microphone input and
the shipping browser code. No owner microphone or conversation was used. The normal
agent was instructed to return this synthetic answer:

> The code word is cobalt. The blue folder contains three notes, and the deadline is
> Tuesday at 14:30. Keep the original files unchanged. I receive a transcript of your
> speech, not the audio itself, so I cannot assess your pronunciation or background
> noise. If a word was transcribed incorrectly, please correct it in this conversation.

The saved answer matched. The native assistant output transcript for its readback was:

> Code word is cobalt. Blue folder has three notes, deadline is Tuesday at 14:30,
> don't change the original files.

Post-gain audio samples were present. The old playback/mode test passed, despite the
missing sentences and changed wording. This demonstrates a gap in the release test:
audible output is not evidence of reply fidelity. The provider transcript is evidence
of generated speech, not a physical recording of the user's output device.

One sample measured approximately 6.3 s from initial setup display to listening,
11.8 s from finalized input transcript to saved answer, and another 2.3 s to first
output audio. These are single-run measurements, not a latency benchmark. The saved
message timestamp has one-second resolution.

Ignored local evidence: `build/voice-fidelity/comparison.json`, `chrome-fixed.json`,
and `server.txt`. Do not publish raw provider logs or authentication launch files.

## Cause

- `voice_turns.py` submits final user transcripts to the normal TurnCoordinator. It
  persists the normal agent answer before calling the speech callback.
- `VoiceCall._reply` sends the answer (currently limited to 3,500 characters) through
  `CodexVoice.speak`, which calls experimental `thread/realtime/appendSpeech`.
- This is a conversational audio model, not a deterministic text reader. The
  installed schema describes speakable text but does not promise verbatim speech.
- `VoiceCall._transcript` discards assistant transcript content, treating it only as
  a playback completion signal. The normal agent therefore cannot know what was
  actually spoken on the next turn. A request to repeat the last spoken response
  can only recover the saved text answer.
- Prompting the audio model to acknowledge only receipt does not reliably suppress
  its own answers. Previous synthetic logs also contain unsolicited native answers.
  The output gate is necessary, but it does not enforce wording or identify buffered
  media by answer ID.

The normal task agent receives transcribed text, not raw audio. The realtime audio
component receives audio. Neither the UI nor future agent instructions should blur
this distinction or imply tone/hearing abilities for the text agent.

Official context: [GPT-Live delegation and tools](https://developers.openai.com/api/docs/guides/live-delegation)
describes spoken commentary as paraphrased and requires applications to maintain both
input and output transcripts. This supports the architectural distinction; it does
not establish that every public Live option is exposed by the installed Codex CLI.

## Product decision

The owner selected option 1 from these alternatives:

1. Native conversational voice with its actual spoken transcript as the visible
   conversation and subsequent agent context. Keep backend work/results distinct
   from the conversational utterance, preserving execution evidence without a second
   competing answer. Do not overwrite a completed task result with speech. Preserve
   interrupted speech as partial and ensure promises cannot mark work completed.
2. Exact read-aloud of the normal saved answer using a separate speech synthesizer.
   Native Codex appendSpeech cannot be represented as a guaranteed exact reader.
   Local Windows voices have a quality tradeoff; an external service introduces
   separate configuration, cost and data handling, which have not been authorized.

Do not silently switch providers, insert generated audio transcripts as user commands,
or strengthen the prompt and call the fidelity issue fixed. No shipping code or
production settings changed during the initial investigation. The subsequent 0.99.113
implementation retains native voice and separates spoken conversation from work evidence.

## Latency and regression requirements

- Instrument connection, speech finalization, queue admission, agent first/final text,
  speech first sample and playback completion separately. Do not retain raw audio.
- Investigate reusing an initialized CLI process while keeping microphone access and
  provider audio sessions explicitly user-started. Do not warm an active microphone.
- Replace avoidable polling/serial waits with notifications where supported. The
  current one-second speech batching plus half-second watcher/state polling adds
  delay, but removing turn boundaries blindly risks executing unfinished requests.
- Streaming stable speech-sized results may reduce time to first sound; do not speak
  private reasoning, uncommitted/revised text or unverified action claims.
- Exercise multi-sentence answers, figures, follow-up references to spoken wording,
  interruption, dictation switching and ending audio during continuing agent work.
  Check content correspondence, not only nonzero audio samples.
