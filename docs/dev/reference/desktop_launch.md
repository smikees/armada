# `armada/desktop_launch.py`

Start the desktop app with Explorer's lifetime and unvirtualized user context.

Detaching a console alone does not escape an MSIX caller's job/device map. Use the
Windows parent-process attribute and the desktop user's environment instead.

### `_windows()`

—

### `desktop_parent()`

True only for a process launched directly under the interactive desktop.

### `spawn(argv, cwd=None)`

Launch under Explorer, outside the caller's job and virtualized filesystem.

### `relaunch_if_needed(args)`

—
