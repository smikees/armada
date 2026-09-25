# `armada/routes/settings.py`

Settings, the signed-in user, notification channels (incl. Telegram), auth, and system
jobs.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.

### class `SettingsRoutes`

—

- `SettingsRoutes._get_settings(self)` — —
- `SettingsRoutes._get_approvals(self)` — —
- `SettingsRoutes._get_docs(self)` — —
- `SettingsRoutes._get_doc_page(self, path: str)` — —
- `SettingsRoutes._get_user_avatar(self)` — —
- `SettingsRoutes._save_user(self, body: dict)` — —
- `SettingsRoutes._user_avatar_upload(self, body: dict)` — —
- `SettingsRoutes._user_avatar_preset(self, body: dict)` — —
- `SettingsRoutes._user_avatar_remove(self, body: dict)` — —
- `SettingsRoutes._get_system_jobs(self)` — —
- `SettingsRoutes._system_job_run(self, body: dict)` — Run a system job on demand. `manual` so it runs even when switched off — pressing the button is an explicit request, not a schedule.
- `SettingsRoutes._system_job_toggle(self, body: dict)` — —
- `SettingsRoutes._get_notifications(self)` — —
- `SettingsRoutes._notifications_read(self, body: dict)` — —
- `SettingsRoutes._get_auth_status(self)` — —
- `SettingsRoutes._auth_login(self, body: dict)` — Start Claude Code's own sign-in in its own window. ARMADA never handles the credential: the owner completes the flow in their browser and Claude Code stores the result itself.
- `SettingsRoutes._alexander_ask(self, body: dict)` — One support turn, as Server-Sent Events: 'status' while he thinks, 'text' as he writes, then 'done' with the reply taken apart into prose and cards.
- `SettingsRoutes._alexander_history(self, body: dict)` — —
- `SettingsRoutes._alexander_addon(self, body: dict)` — —
- `SettingsRoutes._support_preview(self, body: dict)` — Report an issue (5.6), step 1: build the report and show it. Nothing is sent here.
- `SettingsRoutes._support_send(self, body: dict)` — Step 2: send exactly what was previewed (by its token).
- `SettingsRoutes._get_scheduler_status(self)` — —
- `SettingsRoutes._scheduler_start(self, body: dict)` — The bar's Start button. Starts the one scheduler process (which ticks every realm), not a per-realm one — see schedsvc.
- `SettingsRoutes._notify_test(self, body: dict)` — Send a sample notification down ONE channel, so 'does this actually reach me?' can be answered per destination. Bypasses the per-event grid on purpose — it's a delivery test.
- `SettingsRoutes._telegram_status(self)` — GET handler: writes its own response (POST handlers return a dict; these don't).
- `SettingsRoutes._telegram_token(self, body: dict)` — —
- `SettingsRoutes._telegram_env(self, body: dict)` — —
- `SettingsRoutes._telegram_link(self, body: dict)` — —
- `SettingsRoutes._telegram_forget(self, body: dict)` — —
- `SettingsRoutes._save_channels(self, body: dict)` — Persist the per-machine notification channel switches (~/.armada/config.json).
- `SettingsRoutes._save_appearance(self, body: dict)` — Persist the per-app visual theme or colour mode (~/.armada/config.json).
