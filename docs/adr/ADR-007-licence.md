# ADR-007 — Source-available: free for personal use, commercial use by agreement

**Status:** Accepted · 2026-09-21 · decided by Mihai · **one action before any distribution**

## Context

Mihai's decision: the source is open to read and use, free for personal use, and anyone
wanting to use it commercially talks to him first.

Two facts about the current state matter. First, the repository has never been pushed anywhere
— there is no remote — so no licence has ever been *distributed*, and changing it is clean.
Second, the repository currently carries an **MIT licence** (`LICENSE`, and "MIT licensed" in
the README). MIT permits commercial use unconditionally and cannot be revoked for any copy
already given out. The two are incompatible, and the MIT text must be replaced before the
first beta build leaves this machine.

A note on words, because people care about them: "open source" as defined by the OSI requires
no restriction on field of use, so a licence that carves out commercial use is not open
source. The accurate term is **source-available**. Calling it open source would draw
correction from exactly the audience most likely to contribute.

## Decision

1. ARMADA is **source-available**: the code is public, free to use, modify and share for
   non-commercial purposes; commercial use requires a separate agreement with Mihai.
2. **Licence text: PolyForm Noncommercial 1.0.0** (confirmed by Mihai 2026-09-21). It is written for precisely
   this arrangement, is short and readable, and is widely recognised. The alternative is a
   custom licence, which is more work to write and less likely to be understood. *(I am not a
   lawyer; Mihai should confirm the choice, and it costs little to have someone qualified read
   it once before the beta ships.)*
3. The README and the About page say "source-available, free for personal use; for commercial
   use, get in touch" and link to the licence. They do not say "open source".
4. Contributions: to keep the commercial-licensing option real, outside contributions need a
   simple contributor agreement (a CLA or a DCO-plus-assignment) so Mihai retains the right to
   license the whole under different terms. Decide the mechanism before accepting the first
   outside pull request; not needed for the beta.

## Consequences

- **Before the first beta build (Phase 5):** replace `LICENSE` with the chosen text, update the
  README line, add the licence and third-party notices to the installer (step 5.9), and add a
  licence line to the About page.
- Third-party notices: the app depends on the Claude CLI (not bundled) and a small set of
  Python packages; the installer lists their licences.
- Alexander-the-developer (ADR-002) writes plugins into the user's own folders, not into the
  app, so the licence question doesn't arise for what it produces. Had it forked the app, the
  fork would have needed the same licence; one more reason for the extension-point route.
- We give up: the "open source" label and the contributor goodwill that comes with it. In
  exchange Mihai keeps a commercial path.
