# `armada/alexander/wizard_script.py`

Everything Alexander says in the setup wizard, written in advance (ADR-012; docs/dev/ALEXANDER.md).

Scripted rather than generated: the first run costs nothing, can't fail on quota, sign-in or a
model's mood, and every line here is reviewed like any other copy. Voice as PROMPT.md: plain
English, British spelling, short sentences, no exclamation marks, no emoji; warm, direct, firm.

Placeholders in braces are filled by the wizard from the owner's own answers: {owner}, {realm},
{coordinator}, {collective}, {agent}, {count}, {folder}. A line only uses placeholders that exist
by its step. `line(step, key, **values)` fills one; a missing value leaves the brace text visible,
which the tests catch.

### class `_Keep`

Leaves an unknown placeholder visible rather than raising, so a gap shows in review.

- `_Keep.__missing__(self, k)` — —

### `line(step: str, key: str, **values)`

—

### `placeholders(text: str)`

—
