# 0.99.104 verification

Smart search for Add a capability ([design](SMART_SEARCH.md)). The owner confirmed the trial
decisions: Opus 5.5 at low effort, all sources on by default, the filter-based browser removed, and
"Bring in from Claude" importing everything Claude Code has set up.

## Behavior and boundaries

- Alexander's turn runs through the managed-tools broker with only `list_sources` and `search`
  (read-only). No built-in tools, web, files, shell or realm writes are available to it.
- Result cards are built only from records a search returned; any other key in Alexander's answer
  is dropped. His summary is capped at 240 characters.
- Sources the owner switched off cannot be searched in that turn.
- Adding stays outside the turn: Review & add runs the Bring a link review and adds the catalogue
  entry with the review's findings; ChatGPT plugins become "<plugin> · Codex" rows that bind on
  Connect through Codex's `plugin/read`; install consent stays in ChatGPT.
- The ChatGPT plugin directory comes from Codex's app-server `plugin/list` (about 13 MB, app-backed
  plugins only), cached for a day; the RPC reader's line limit is raised for that call only.
- "In this realm" matching is exact (catalogue key or id), not the catalogue's looser name match.

## Checks

- `tests/test_smart_search.py`: each source's records and actions; switched-off sources refused;
  a fake Claude turn proving only returned keys become cards and the summary cap; the skill's
  rules; ChatGPT plugin → Codex row → bind on Connect; the tab's controls; script syntax.
- Live runs (Opus 5.5) on a copy of the owner's realm: 6–42 s, $0.01–0.07 usage-equivalent each.
- Goldens regenerated after the version and changelog; diffs reviewed.

## Results

Published 2026-10-10 as normal/latest [v0.99.104](https://github.com/smikees/armada/releases/tag/v0.99.104)
from source `ee859e1`, through `tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated release gate: **3,615 passed, 5 skipped**.
- [Exact-source CI](https://github.com/smikees/armada/actions/runs/38074700128) passed on the first attempt.
- Native upgrade gate: 69 real-page, restart and cleanup checks passed, upgrading 0.99.103 to 0.99.104.
- The owner's running app was not restarted.

| Public artifact | SHA-256 |
| --- | --- |
| `ARMADA-Setup-0.99.104.exe` | `379564b3988fc47dcaa89557a84c8f436fc59967ed636c435e75aa7db26dc43a` |
| `armada-0.99.104.zip` | `ece9667c7f8ee199c9d0e5330e7ab9ebd76ad1066ca36e7eb1c211ec2722559e` |
| `armada-update.json` | `bb0e74bea0bca7c4d5d68dc48a791a2843008655da460d73e41aea716797f780` |
| `armada-update.json.sig` | `a79d4be3dc9be34bad770b994092c540f62d2b6adcb7769d3e90ff744180e489` |

Website: `website/index.html` carries 0.99.104 in source. The FTPS upload runs with the owner's
local credentials (`build/publish_website.py 0.99.104`); its verification is recorded here once done.
