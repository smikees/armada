# `armada/validate.py`

`armada validate` — is this folder a runnable ARMADA realm, and what's in it?

This is the contract check behind "point ARMADA at a folder and it figures out the realm":
it reports what ARMADA expects (the native spec, SPEC §4), what's present, and what's missing
or malformed — per realm and per job — so an export (e.g. the cabinet) can be verified against
the spec before you try to run it. Errors block running; warnings are advisory.

### `_read(p: Path)`

—

### `_json(p: Path)`

—

### `validate(folder)`

—

### `run(folder)`

—
