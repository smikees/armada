# `armada/setup.py`

`armada new` — scaffold a ARMADA-native realm from a template (SPEC §12).

Writes the neutral on-disk schema (realm.json, theme.json, objectives.md, tenets.md, and
each agent's folder with agent.json + mandate.md + soul.md). This is the greenfield path;
the read/adopt path (reader.py) handles an existing realm.

### `scaffold(folder, template_id: str='scratch', name: str | None=None, icon: str | None=None, agents: list | None=None)`

—
