# `armada/routes/jobs.py`

Jobs: new/save/enable/delete a job, job detail, job calendar, run.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.

### class `JobRoutes`

—

- `JobRoutes._get_new_job(self)` — —
- `JobRoutes._get_job(self, path)` — —
- `JobRoutes._get_job_calendar(self)` — —
- `JobRoutes._get_job_detail(self)` — —
- `JobRoutes._new_job(self, body: dict)` — —
- `JobRoutes._job_calendar(self, dfrom: str, dto: str, scope: str='')` — —
- `JobRoutes._job_enable(self, body: dict)` — Switch a job on or off. Off means the scheduler skips it; 'Run now' still works.
- `JobRoutes._delete_job(self, body: dict)` — Delete a job file. The run history in agents/<id>/runs stays — it is a record of what actually happened, and removing it because the job was retired would falsify the telemetry.
- `JobRoutes._save_job(self, body: dict)` — —
- `JobRoutes._run(self, body: dict)` — —
