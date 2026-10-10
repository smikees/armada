# Smart search (Add a capability)

Status: released in 0.99.104 after an owner trial; decisions below confirmed by the owner.

## Shape

- `armada/smart_search.py`: sources, normalised records, the ChatGPT plugin directory cache, the
  sealed Alexander turn, and background jobs (`start`/`status`).
- `armada/system_skills/smart-search/SKILL.md`: Alexander's instructions. Terse by design: a 1–2
  line summary (≤240 chars) and a reason per result; JSON out.
- `armada/webui/smartsearch.py` + `static/js/smartsearch.js`: the tab, source toggles (saved in
  localStorage per machine), progress polling, cards and actions.
- Routes: `POST /api/smart-search` (start), `GET /api/smart-search?id=` (poll),
  `POST /api/smart-search-add` (ChatGPT plugin → Codex row), `POST /api/smart-search-warm`.

## Safety

- Alexander's turn uses ARMADA's managed-tools broker with only `list_sources` and `search`; no
  built-in tools, web, files, shell or realm writes (`managed_tools.claude_args`).
- Cards are built from records a search returned (`Session.seen`); unknown keys are dropped.
- Adding anything is outside the turn and goes through the existing review (Bring a link) or the
  engine's own consent (ChatGPT, claude.ai).

## Sources

| Id | What | How |
| --- | --- | --- |
| realm | This realm | realm.json |
| my-skills | Your skills elsewhere | catalogue index (mine/installed) |
| claude-code | Set up in Claude Code | `claude mcp list` + `claude plugin list`, cached 10 min |
| chatgpt-installed | Installed in ChatGPT | Codex `plugin/list`, installed flag |
| engine-connectors | ARMADA's per-engine services | connector_registry.SERVICES |
| chatgpt-plugins | ChatGPT plugin directory | Codex app-server `plugin/list` (~13 MB, app-backed plugins only, cached 24 h) |
| claude-plugins | Claude plugin marketplaces | catalogue index (local marketplace clones) |
| anthropic-skills | Anthropic skills | catalogue index |
| mcp-registry | MCP registry | live search |

Not searchable: Claude's connector directory (no public list), skills.sh (its API needs a Vercel
OIDC token), Gemini/Antigravity extensions. Linked under "Browse for yourself".

## Decisions taken for the trial (owner may revisit)

- Model fixed to Claude Opus 5.5, effort low (speed over depth for ranking).
- All sources on by default; switches persist per machine.
- The old filter-based catalogue browser is removed from the tab; its data still feeds the sources.
- Engine-installed connectors not in the realm offer "Bring in from Claude" (imports all of
  Claude Code's servers, as the former refresh did).
