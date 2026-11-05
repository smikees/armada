# `armada/control_files.py`

Shared classification of application state versus model-authored output.

Classification does not grant access. Callers must still validate canonical paths,
owner scopes and the operation's content. Owner APIs and the trusted builder do
not use the scoped model-write boundary.

### `kind(root, target, *, agent='')`

Classify an already checked path as control, own memory, proposal or output.
