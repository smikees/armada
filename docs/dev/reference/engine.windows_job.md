# `armada/engine/windows_job.py`

Windows CLI process-tree ownership using documented Job Object and thread APIs.

Start suspended so no tool child can escape before assignment. Failure to establish ownership
fails launch; process.py then kills the still-suspended child. No shell or taskkill is involved.

### class `BasicLimits`

—


### class `ExtendedLimits`

—


### class `ThreadEntry`

—


### class `WindowsJob`

—

- `WindowsJob.__init__(self)` — —
- `WindowsJob.attach_and_resume(self, process)` — —
- `WindowsJob.close(self)` — —
