# ADR-004 — The Catalogue is search + bring-a-link, not browse

**Status:** Accepted · 2026-09-21

## Context

The Catalogue tab was built as a browsable directory over three sources: the Claude plugin
marketplace (~310 plugins), Anthropic's public skills (~19), and the MCP registry, queried live.
Its ordering, filters and counts were designed as if discovery were possible.

The data does not support discovery, and this was measured rather than felt. The MCP registry
holds 33,657 servers; it publishes no popularity signal, no publisher field, no category, and
ignores its own sort parameter. The marketplace publishes no download or install counts.
Name collisions are the norm — a search for "filesystem" returns eleven unrelated servers, and
before the fix in 0.99.22 the app ticked every one of them as "already in your realm". Nothing
any source publishes is a thing a person would sort by. A browse UI over that data can only be
as good as the data.

What turned out to be valuable while building it was none of the browse UI. It was provenance
(every capability in a realm says where it came from, established from evidence like its
command line rather than a name guess), the cross-realm "you already use this" hint,
inspection and a risk tier *with a reason* at the moment of adding, the skill-registry contract
every agent follows for anything it writes or fetches, and a shared trust vocabulary — who made
it, what it can touch, curated versus self-published. That is what Claude Desktop does not do,
and it all survives if browsing goes.

## Decision

The Catalogue is reframed as **Add a capability**, with two paths:

1. **Search known sources.** Search stays across all three sources — when you know the name,
   it is faster than a link. Browsing is removed: no "Suggested" ordering, no sample of 100
   from 33,657 on an empty search, no counts that imply completeness. With no search, the pane
   shows the mirrored sources only and says the registry is searched, not browsed.
2. **Bring a link.** Paste a URL — a repository, a package, an MCP server — and an agent runs
   the capability-review protocol against it and produces a **review report** the user reads
   before Add is enabled. This is the headline path, because it is the one that scales to the
   sources we don't mirror.

The **review report** is the product: what it is, who published it, what it can reach, what was
actually found, what the reviewer could not check. One format, used on the bring-a-link path,
on search results at add time, and in the User tab's expanded panel.

The mirror of Anthropic's marketplace and skills is kept. Those two sources are curated, their
counts are honest, and they are the safest things a new user can add — which is what the setup
wizard draws from.

## Consequences

- Phase 1 of the launch plan is mostly removal, plus the bring-a-link entry point and the report
  format. `inspect`, the capability-review system skill, `adopt` and the skill-registry
  contract already exist; the missing piece is the entry point and the report.
- Code the reframe orphans is removed: `suggested()`, `why_ranked`, `multi_vendors`, the
  empty-search sample path.
- The info box's copy changes to "where we can search" plus "bring your own, we'll review it".
- We give up: the promise of discovering something you didn't know to look for. That promise
  was not being kept.
