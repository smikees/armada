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

Recorded below when the maintenance publisher completes.
