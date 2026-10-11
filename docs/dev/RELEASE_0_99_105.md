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

Recorded below when the maintenance publisher completes.
