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

### class `ActivationError`

An existing process could not fulfill a desktop launch.


### `activate(info, requested_role='app', timeout=10.0)`

Ask the owner to show a window; never mistake an old headless server for one.

### `claim(role, port)`

Kernel-held lifetime lock: simultaneous launches and crashes cannot steal ownership.

### `_publish(**updates)`

—

### `publish_port(port)`

—

### `server_ready()`

—

### `promote_to_desktop()`

—

### `keep_headless(error)`

Keep serving after a failed GUI attempt; repeat launches explain the failure.

### `owned_role()`

Runtime role takes precedence over argv after a headless owner opens its UI.

### `desktop_ready()`

—

### `watch_activation(callback)`

Bring a tray-hidden window back when a second launch requests activation.
