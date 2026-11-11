# `armada/worker_process.py`

Windows alternate-account launch, retaining Python's pipe and communicate ownership.

No shell, credential arguments, owner environment inheritance or interactive desktop.
The regular supervisor assigns the suspended process to its kill-on-close Job Object.

### class `Startup`

—


### class `Information`

—


### class `WorkerPopen`

—

- `WorkerPopen.__init__(self, args, *, identity, spec, **kwargs)` — —
- `WorkerPopen._cleanup_worker(self)` — —
- `WorkerPopen.kill(self)` — —
- `WorkerPopen.wait(self, timeout=None)` — —
- `WorkerPopen._execute_child(self, args, executable, preexec_fn, close_fds, pass_fds, cwd, env, startupinfo, creationflags, shell, p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite, *unused)` — —
