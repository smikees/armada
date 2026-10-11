# 0.99.105 verification

Owner review of 0.99.104's smart search ([design](SMART_SEARCH.md)).

## Changes

- Layout: Ask Alexander is the main column; a side panel holds **Have a link?** and **Browse for
  yourself**. A pasted link's review renders in the main column.
- One link field replaces Bring a link and Add an MCP server by its address. Every link is
  reviewed; on Add, an MCP server address (`/mcp`, `/sse`, `mcp.` host; never GitHub) is saved as a
  connector for every engine carrying the review's findings, anything else is recorded as before.
- Results never add directly: catalogue entries with a link show **Review** (the link review);
  entries on this computer show **Review** (a local file check, `/api/smart-search-check`). The
  review card offers **Add to realm**, which adds the catalogue entry with the findings.
- In-realm results show "In this realm" as green status text and a **Go to <type>** button.
- The Sources menu closes on an outside click or Escape.

## Checks

- `tests/test_smart_search.py`: in-realm text and Go to label; Review-only actions; local check
  route; MCP address detection and add-with-review; Sources close handlers; side-panel layout.
- Goldens regenerated after the version and changelog; diffs reviewed.

## Results

Published 2026-10-11 as normal/latest [v0.99.105](https://github.com/smikees/armada/releases/tag/v0.99.105)
from source `5faf8a9`, through `tools/publish_release.py --maintenance-unsigned`, which waited
for exact-source Windows CI to pass before building.

- Pinned isolated release gate: **3,620 passed, 5 skipped**.
- Native upgrade gate: 69 real-page, restart and cleanup checks passed, upgrading 0.99.104 to 0.99.105.
- The owner's running app was not restarted.

| Public artifact | SHA-256 |
| --- | --- |
| `ARMADA-Setup-0.99.105.exe` | `0c96c7d29d362ffff7e818efdd66aab479185919c20b18e85b59e3177d55f302` |
| `armada-0.99.105.zip` | `c23512356307bfc5e1f049db395f2d211365f986716c8bcf2cbcedf4a35b5636` |
| `armada-update.json` | `2d00d020cd336479bca93b95889e31130517093fed8b89b1ee5a7796913ab492` |
| `armada-update.json.sig` | `04d36d091f4cf4268b58f6c3bc54c48696c44b048dc9ea63f3d85259c1cc3dda` |

Website: `website/index.html` carries 0.99.105 in source; the owner's FTPS upload
(`build/publish_website.py 0.99.105`) and its verification are recorded here once done.
