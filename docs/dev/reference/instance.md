# `armada/instance.py`

One desktop/server owner per OS account, independent of realm and install path.

### `_account_directory()`

Resolve the Windows token's profile, independent of environment/profile overrides.

### `_path()`

—

### `current()`

—

### `_legacy()`

Recognize authenticated older servers which predate the account-wide lock.

### `_focus_pid(pid)`

—

### `activate(info)`

—

### `claim(role, port)`

Kernel-held lifetime lock: simultaneous launches and crashes cannot steal ownership.

### `publish_port(port)`

—

### `desktop_ready()`

—

### `watch_activation(callback)`

Bring a tray-hidden window back when a second launch requests activation.
