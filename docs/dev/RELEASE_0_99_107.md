# 0.99.107 verification

Found while building the finance team (stress-test log, 11 October 2026): Feynman answered a test
message in his thread and ended it with "ARMADA_JOB_RESULT: FAILED", because his mandate says how
every run ends. Profiles describe job endings; nothing told the agent that a turn was a conversation.

## Change

`execution.turn_kind_note` adds one line to the system context of every model turn that goes
through the turn coordinator:

- scheduled job runs (job threads): "This turn is a scheduled job run (job <id>)…"; the structured
  result contract is appended to the prompt as before;
- one-off requests (Inbox tasks, run by hand outside a job thread): job endings don't apply;
- conversations: names the thread; job endings don't apply.

Dry runs build their own request and are unchanged. ARMADA only parses result markers on scheduled
runs, so nothing that reads results changes.

## Owner tweaks in the same release

- Armada II starts at 13 px (`vtheme.THEMES`, `fonts.reference_size`). `fonts._adopt_armada_ii_13`
  moves a 15 px start saved by choosing the theme in 0.99.106 to 13 px once; a size chosen later stays.
- "Play a quiet sound when ARMADA is ready" is a switch under Settings → App → Advanced (same
  `st-startup-sound` control and save path; on by default).
- Inspector agents (`is_inspector: true`) show Boxicons "scan-search" (MIT) beside their name in the
  agent header, the Ministers cards and the roster table (`agentbits._inspector_mark`).

## Checks

- `tests/test_turn_kind_note.py`: the three notes; a chat turn's system context carries the
  conversation note.
- `tests/test_armada_ii.py`: 13 px defaults and the one-time move from 15 px.
- `tests/test_inspector_mark.py`: the mark only for inspectors; the sound switch under Advanced.
- Goldens regenerated after the version and changelog.

## Results

Published 2026-10-11 as normal/latest [v0.99.107](https://github.com/smikees/armada/releases/tag/v0.99.107)
from source `ec99949`, through `tools/publish_release.py --maintenance-unsigned` (exact-source Windows
CI passed before the build).

- Pinned isolated release gate: **3,639 passed, 5 skipped**.
- Native WebView2: 16 multi-window session checks passed; native upgrade gate: 69 real-page, restart
  and cleanup checks passed, upgrading 0.99.106 to 0.99.107.
- The owner's running app was not restarted.

| Public artifact | SHA-256 |
| --- | --- |
| `ARMADA-Setup-0.99.107.exe` | `32e4355f22e0040c4de64c0284db27e68a3724e52c037363a9718b4ca1140d80` |
| `armada-0.99.107.zip` | `ec6f342818bfe35dbd7f9ff9bded70a2b38793bba7d0e77bf408b52b965593aa` |
| `armada-update.json` | `5aacc247ac864efdfe8157fb14072f3354637bf70c5d30d30b5707cd7d284bbd` |
| `armada-update.json.sig` | `2dc76d70dc44ca597c45534b5c8b1afeb95a451991da451723ef6a3a9c911da7` |

Website: `website/index.html` carries 0.99.107 in source; the owner's FTPS upload and its
verification are recorded here once done.
