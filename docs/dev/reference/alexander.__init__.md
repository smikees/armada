# `armada/alexander/__init__.py`

Alexander — ARMADA's guide (Phase 6; docs/dev/ALEXANDER.md, ADR-012).

The one bundled agent: the same in every install, not part of any realm, not editable by the owner.
Scripted in the setup wizard (`wizard_script`), live in support. This module holds what's fixed
about him; the prompt is `PROMPT.md` beside it, shipped with the app.

### `prompt()`

The system prompt, without the leading reviewer comment.
