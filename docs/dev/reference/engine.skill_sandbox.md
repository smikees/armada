# `armada/engine/skill_sandbox.py`

Windows LPAC launcher for approved draft scripts; no network or child processes.

Only private staged trees receive a unique container SID. Production ACLs are never
modified. The existing process supervisor still owns deadlines, cancellation and pipes.
See Microsoft's implementing-an-appcontainer and UpdateProcThreadAttribute references.

### class `Startup`

—


### class `StartupEx`

—


### class `ProcessInfo`

—


### class `SidAndAttributes`

—


### class `Capabilities`

—


### class `Trustee`

—


### class `Access`

—


### `available()`

—

### class `SkillSandbox`

A launch factory accepted only by the owned command supervisor.

- `SkillSandbox.__init__(self, *, readonly, writable)` — —
- `SkillSandbox._setup(self)` — —
- `SkillSandbox._ok(value)` — —
- `SkillSandbox._grant(self, path, access, *, mode=1)` — —
- `SkillSandbox.__call__(self, args, *, cwd, env, **kwargs)` — —
- `SkillSandbox.close(self)` — —
- `SkillSandbox.__enter__(self)` — —
- `SkillSandbox.__exit__(self, *args)` — —

### class `NativeProcess`

—

- `NativeProcess.__init__(self, api, handle, pid, fds, args)` — —
- `NativeProcess.poll(self)` — —
- `NativeProcess.wait(self, timeout=None)` — —
- `NativeProcess.kill(self)` — —
