# `armada/engine/defaults.py`

Release-owned defaults for new teams, independent of Alexander's personal settings.

Only authenticated providers participate. Seed catalogues are UI suggestions, not evidence
that a pinned model is available: an unknown/unavailable catalogue uses the CLI's default.
Review PREFERENCES with each release; existing realms and explicit agent/job picks stay put.

### `catalogues(states: dict)`

Read vendor model metadata during setup, never on a page-render path.

### `choose(states: dict, available: dict | None=None)`

Return persistable realm defaults, or refuse setup when no engine can run.
