# `armada/agentdates.py`

Appointment dates are profile history, not configuration modification times.

### `_birthtime(path: Path)`

—

### `appointment_date(config: dict, agent_dir: Path)`

Prefer recorded history; recover a best-known date for pre-date-field profiles.
