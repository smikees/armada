# `armada/sysskills.py`

System skills — the skills ARMADA itself needs to work.

A system skill ships inside the package (armada/system_skills/<id>/SKILL.md), not in the realm
folder. That's the whole mechanism behind "locked": there is nothing in the user's realm to edit or
delete, and the skill is versioned with the app, so it improves when ARMADA updates. They're shown
in the UI rather than hidden — the app runs these against the user's own capabilities, and that
should be inspectable.

Everything here is read-only and best-effort: a missing or malformed bundle degrades to "no system
skills" rather than breaking the Capabilities page.

### `_parse_front(text: str)`

Split a leading '---' frontmatter block off a SKILL.md. Returns (meta, body).

### `_one(d: Path)`

—

### `list_system_skills()`

Every bundled system skill, sorted by name. [] if the bundle is missing.

### `get_system_skill(sid: str)`

One system skill by id, or None. Guards against path traversal via the id.
