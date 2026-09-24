# `armada/templates.py`

Realm templates (SPEC §3/§11): {theme} + starter agents over the neutral schema.

A template is presentation + seed data — the structure is identical underneath. `state`
frames a Cabinet of Ministers, `company` a Board of Executives, `crew` a Pirate ship, and
`scratch` is a blank realm you fill yourself. The theme only maps neutral nouns
(coordinator/agent/collective) to display labels + a default voice; it never changes the
data model, so a realm stays portable and re-themeable.

### `names()`

—
