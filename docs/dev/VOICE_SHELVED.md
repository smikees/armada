# Agent voice — built, shelved, and how to bring it back

**Status:** removed from the shipping code on 2026-09-19, before v1.
**Where it lives:** git. Six commits, oldest first:

| commit | what it added |
|---|---|
| `6c14af6` | The POC: `voice_*` on the agent, the Voice box on Configure, speak-on-reply via the browser's `speechSynthesis`. |
| `60869fc` | Voice-list refresh, a link to the OS voice settings. (Also verbosity in the cost dial — **keep that, it is unrelated**.) |
| `13ccdd5` | Corrected the link after discovering Narrator's voices are unreachable. |
| `46e0682` | Piper as a second provider: `armada/tts.py`, `/api/speak`, `/api/tts-status`. |
| `91bf50e` | Moved the Piper path from the realm to the machine config. |
| `17f0d66` | The read-aloud switch in the thread, text cleaning, the UTF-8 and curly-quote fixes. |

**The removal is `0ef6b1f`** (v0.95.0). To restore: `git revert 0ef6b1f`, or
cherry-pick the six above onto a branch. Everything below is what those commits
cannot tell you.

One thing the revert will not undo: `_save_agent` now *strips* `voice_enabled`,
`voice`, `voice_provider` and `voice_rate` from an `agent.json` on every save,
so any agent saved since 0.95.0 has lost its stored voice. Delete that loop
before reverting, or the restored UI will silently drop what it writes.

---

## Why it is off

It works. It is not pleasant to listen to, and the gap is not polish:

- **Numbers are read digit by digit.** "58 names" becomes "five eight names".
  Piper has no text-normalisation stage — no number-to-words, no dates, no
  currency, no units. That layer has to be written or borrowed before an agent
  that talks mostly in figures is worth hearing.
- **Intonation is flat.** Piper's voices are VITS models with no prosody
  control: no emphasis, no question contour, no pauses that mean anything. A
  long analytical reply reads as one continuous monotone.
- **Symbols leak through.** `~` was spoken as "tilde"; the cleaner covered URLs,
  emoji, rules and table pipes but not the long tail of mathematical and
  typographic symbols. That tail is long.
- **Latency.** ~17s to synthesise a 3,700-character reply before any sound. The
  fix is sentence-by-sentence streaming, which is real work (see below).

Any one of these is fixable. Together they mean the feature reads as broken
rather than as basic, which is worse than not having it.

## What we learned — do not re-derive this

**Windows' good voices are not available to applications.** Narrator's "Natural"
voices (Microsoft Ryan, Andrew HD, Ava…) install as app packages —
`MicrosoftWindows.Voice.en-GB.Ryan.1` — and register **no speech token
anywhere**. Verified with two installed: absent from
`HKLM\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens`, absent from
`System.Speech` (SAPI), and absent from
`Windows.Media.SpeechSynthesis.AllVoices`, which is what the Web Speech API sits
on. They are Narrator-only by construction. No refresh, no reboot, no API.
So `speechSynthesis` on Windows can only ever offer the old OneCore set, and its
ceiling is low. Do not send users to "Add natural voices" — it costs them a
download and changes nothing.

**Piper is GPL-3.0-or-later.** `rhasspy/piper` (MIT) was archived in October
2025; the live project is `OHF-Voice/piper1-gpl`. ARMADA is free-for-personal-
use, which cannot link against it. The arrangement that works is arm's length:
never import it, never bundle it, run the executable the owner installed and read
a WAV back. `armada/tts.py` did exactly that and had a test asserting
`import piper` never appears. **Keep that discipline if this comes back.**
Voice models carry their own separate licences per voice (`MODEL_CARD` in
`rhasspy/piper-voices`) — mostly CC BY 4.0, some trained on corpora that bar
commercial use. Check per voice before shipping any.

**Two bugs that will recur if the code is rewritten from scratch:**

1. `subprocess.run(..., text=True)` encodes stdin with the **locale** codec. On
   Windows that is cp1252, so an agent writing a minus sign (U+2212) killed the
   whole utterance with a `UnicodeEncodeError`. Pass `encoding="utf-8"`.
2. Piper's phonemiser **rejects curly quotes** (`“ ” ‘ « »`) — the traceback
   lands inside `voice.synthesize`. A minus sign and an em dash pass fine.
   Fold them before synthesis, server-side, so every caller is covered.

**Design choices that were right and should survive a rewrite:**

- Speak the **canonical rendered reply** (`innerText` of the rendered markdown),
  not the streamed chunks. That is what avoids a second markdown parser.
- `voice_provider` as a stored field, not an assumption — it is what let Piper
  slot in beside the system provider without migrating a single `agent.json`.
- The voice **name**, never an index — indexes are not stable across machines.
- A voice id arriving from the browser is resolved by **matching the installed
  list**, never by joining a path.
- Piper's path belongs to the **machine** (`~/.armada/config.json`), not the
  realm. Scoping it per realm meant "not installed" in whichever realm you
  happened to be looking at.
- The switch starts **off** every session. Giving an agent a voice says it *can*
  speak, not that it should start talking when a thread opens.

## The wiring, for re-entry

Every touch point the six commits created:

**Model / storage**
- `armada/model.py` — `Agent.voice_enabled`, `voice_provider`, `voice`,
  `voice_rate`.
- `armada/reader.py` — reads those from `agent.json`; `_clamp_rate()` holds the
  rate inside 0.5–2.0 (a number is clamped, a non-number defaults).
- `armada/serve.py` `_save_agent` — writes only non-defaults, so agents are not
  pinned to today's values.

**Server**
- `armada/tts.py` — the whole Piper provider: `binary()`, `voices()`,
  `status()`, `synth()`, `speakable()`.
- `armada/serve.py` — `GET /api/tts-status`, `POST /api/speak` (returns
  `audio/wav`, which is why the POST dispatcher learned to let a handler return
  `None` and write its own response — **that change stays, it is general**).
- `armada/serve.py` `_open_os_settings` + `_OS_SETTINGS` — opened the OS voice
  settings page from an allowlist of page names.

**UI**
- `armada/webui/agentframe.py` — `_voice_box()` on Configure (provider, voice,
  speed, Hear it / Stop), and the read-aloud switch in `_agent_header()`.
- `armada/webui/threadsview.py` — `data-voice-*` attributes on `#mc-turns`.
- `armada/webui/static/js/voice.js` — the whole client: voice enumeration,
  `speechText()` cleaning, `say()` provider dispatch, Piper playback.
- `armada/webui/static/js/chat.js` — `mcSpeakLastReply()` hanging off
  `mcRefreshTurns`, and the switch's state (sessionStorage `mc-voiceover`).
- `armada/webui/static/js/agent.js` — the `voice` block in the save payload.
- `armada/icons.py` — `voice-over-off`, `voice-over-on`, `volume-2`, `volume-x`.
- `armada/assets.py` — `VOICE_JS`; loaded **before** `chat.js`, which paints the
  switch at parse time.

**Tests** — `tests/test_agent_voice.py`, `tests/test_tts_piper.py`.

## If this comes back, in order

1. **Fix the listening experience first, with a throwaway script.** Number
   normalisation and sentence streaming, measured on a real Warren reply. If it
   still sounds bad, the provider is wrong and no UI work will save it.
2. **Re-evaluate providers.** A paid API (ElevenLabs et al.) solves prosody and
   normalisation outright but is a recurring per-character cost and puts a key in
   the realm — a policy decision, not a technical one. Check whether anything
   local has closed the gap since.
3. **Only then** cherry-pick the UI back. It was the part that worked.

## Left on this machine (harmless, delete if you like)

- `D:\Work\Work2\piper-env\` — the Piper install (its own venv).
- `~\.armada\voices\` — three voice models, ~235 MB.
- `~\.armada\config.json` — a `tts.piper_bin` key, now ignored.
