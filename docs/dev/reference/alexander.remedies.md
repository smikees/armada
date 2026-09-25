# `armada/alexander/remedies.py`

Remedies: the fixed list of app actions Alexander may propose (ADR-012, docs/dev/ALEXANDER.md).

He names one and its arguments in a ```remedy block; `card()` validates that against this list and
the realm on disk and returns what the page shows — a sentence saying exactly what will happen,
one button, and the app endpoint the button posts to. The endpoint is the same one the app's own
button uses, so a remedy does nothing the owner couldn't do by hand, and each endpoint keeps its
own checks. Anything that doesn't validate returns None, and the page shows nothing.

Adding a remedy is a code change and a release. He can't invent one.

### `_job_file(realm_root, agent: str, job: str)`

—

### `_job_name(p: Path, fallback: str)`

—

### `_agent_name(realm_root, agent: str)`

—

### `_run_job(realm_root, args: dict)`

—

### `_set_job(on: bool)`

—

### `_start_scheduler(realm_root, args: dict)`

—

### `_refresh_environment(realm_root, args: dict)`

—

### `_check_updates(realm_root, args: dict)`

—

### `_open_page(realm_root, args: dict)`

—

### `card(realm_root, proposal)`

The card for one ```remedy proposal, or None when it doesn't validate.

### `context()`

The `<remedies>` section of his context: names, arguments, one line each.
