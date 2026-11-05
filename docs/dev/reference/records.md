# `armada/records.py`

Record health: strict admission, diagnostic views, and explicit owner repair.

Presentation failures never supply replacement configuration to execution. Original
bytes are retained, including when an owner replaces a damaged configuration.

### `decode(raw: str | bytes)`

—

### `validate(data: dict, kind: str, identity: str | None=None)`

Validate consumed field shapes; missing optional fields retain legacy semantics.

### `read(path: Path, kind: str, *, max_schema='current')`

—

### `admit_agent(root, agent)`

Strict shared admission for automatic dispatch and deterministic commands.

### `presentation(path: Path, kind: str)`

A missing config is damaged too; callers must render an explicit held record.

### `history(path: Path)`

Display valid rows, diagnose excluded rows; never rewrite the evidence.

### `target(root, agent, job='')`

—

### `repair(root, agent, job, replacement, expected_sha256)`

Owner-only operation: validate, compare, preserve evidence, atomically replace.
