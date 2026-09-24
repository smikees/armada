"""Settings, the signed-in user, notification channels (incl. Telegram), auth, and system
jobs.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from .. import activerealm, reader, render, scheduler, util, brand
from ..util import safe_seg
from . import _shared
from ._shared import _reg_load
from ..util import swallowed

log = logging.getLogger("armada.serve")


class SettingsRoutes:
    def _get_settings(self):
        from .. import webui
        from ..engine import get_engine
        ok, detail = get_engine("claude").doctor()
        self._send(200, webui.render_settings(reader.read(self.realm), self.realm, ok, detail, _reg_load(),
                                              dark=self._dark()))

    def _get_approvals(self):
        from .. import webui
        self._send(200, webui.render_approvals(reader.read(self.realm), self.realm, dark=self._dark()))

    def _get_docs(self):
        from .. import webui
        self._send(200, webui.render_docs(reader.read(self.realm), self.realm, dark=self._dark()))

    def _get_doc_page(self, path: str):
        from .. import webui
        slug = path[len("/docs/"):].strip("/")
        self._send(200, webui.render_docs(reader.read(self.realm), self.realm, dark=self._dark(), slug=slug))

    def _get_user_avatar(self):
        from .. import webui
        f = webui._user_avatar_file(self.realm)
        if f and f.is_file():
            self._send(200, f.read_bytes(), self._CT.get(f.suffix.lower(), "image/png"))
        else:
            self._send(404, "no user avatar", "text/plain")

    def _save_user(self, body: dict) -> dict:
        rj = Path(self.realm) / "realm.json"
        if not rj.exists():
            return {"ok": False, "error": "no realm.json"}
        try:
            with util.file_lock(rj):
                cfg = json.loads(rj.read_text(encoding="utf-8-sig"))
                user = dict(cfg.get("user") or {})
                # Timezone is no longer here: it belongs to the realm (the scheduler runs jobs
                # against it), so it's edited in Realm settings and lives at the top level.
                for k in ("name", "gender", "birthdate"):
                    if k in body:
                        user[k] = (body.get(k) or "").strip()
                if "about" in body:                       # free text, every agent reads it
                    user["about"] = (body.get("about") or "").strip()[:4000]
                user.pop("timezone", None)
                cfg["user"] = user
                # keep the top-level owner in sync (used by the Hand gate)
                if user.get("name"):
                    cfg["owner"] = user["name"]
                util.write_json_atomic(rj, cfg)
            # realm.json/user is the source of truth for owner facts; regenerate the (read-only)
            # System memory so every agent sees the new values.
            self._refresh_system("user-settings")
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_save_user: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _user_avatar_upload(self, body: dict) -> dict:
        try:
            d = Path(self.realm) / "user"
            d.mkdir(parents=True, exist_ok=True)
            return self._write_data_image(d / "avatar", body.get("data", ""))
        except Exception as e:  # noqa
            swallowed(log, '_user_avatar_upload: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _user_avatar_preset(self, body: dict) -> dict:
        import shutil
        preset = str(body.get("preset", ""))
        src = Path(__file__).resolve().parent / "webui" / "static" / "avatars" / f"{preset}.png"
        if ".." in preset or not src.is_file():
            return {"ok": False, "error": "unknown preset"}
        try:
            d = Path(self.realm) / "user"
            d.mkdir(parents=True, exist_ok=True)
            for old in d.glob("avatar.*"):
                old.unlink()
            shutil.copyfile(src, d / "avatar.png")
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_user_avatar_preset: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _user_avatar_remove(self, body: dict) -> dict:
        try:
            d = Path(self.realm) / "user"
            if d.is_dir():
                for old in d.glob("avatar.*"):
                    old.unlink()
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_user_avatar_remove: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _get_system_jobs(self):
        from .. import sysjobs
        self._json(200, {"jobs": sysjobs.status(self.realm)})

    def _system_job_run(self, body: dict) -> dict:
        """Run a system job on demand. `manual` so it runs even when switched off — pressing the
        button is an explicit request, not a schedule."""
        from .. import sysjobs
        return sysjobs.run_one(self.realm, str(body.get("id", "")), manual=True)

    def _system_job_toggle(self, body: dict) -> dict:
        from .. import sysjobs
        return sysjobs.set_enabled(self.realm, str(body.get("id", "")), bool(body.get("on", True)))

    def _get_notifications(self):
        from .. import notify as _n
        items = _n.feed(self.realm, limit=50)
        self._json(200, {"items": items, "unread": _n.unread_count(self.realm, items),
                         "last_read": _n.last_read(self.realm)})

    def _notifications_read(self, body: dict) -> dict:
        from .. import notify as _n
        return _n.mark_read(self.realm)

    def _get_auth_status(self):
        from .. import auth
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self._json(200, auth.status(force=(q.get("force") or [""])[0] == "1"))

    def _auth_login(self, body: dict) -> dict:
        """Start Claude Code's own sign-in in its own window. ARMADA never handles the credential:
        the owner completes the flow in their browser and Claude Code stores the result itself."""
        from .. import auth
        return auth.start_login()

    def _support_preview(self, body: dict) -> dict:
        """Report an issue (5.6), step 1: build the report and show it. Nothing is sent here."""
        from .. import support
        if not str(body.get("message") or "").strip():
            return {"ok": False, "error": "Say what happened first — a sentence is enough."}
        return support.preview(self.realm, message=body.get("message"), page=body.get("page"),
                               title=body.get("title"), email=body.get("email"),
                               include_logs=bool(body.get("include_logs", True)))

    def _support_send(self, body: dict) -> dict:
        """Step 2: send exactly what was previewed (by its token)."""
        from .. import support
        return support.send(str(body.get("token") or ""))

    def _get_scheduler_status(self):
        from .. import schedsvc
        self._json(200, schedsvc.status(self.realm))

    def _scheduler_start(self, body: dict) -> dict:
        """The bar's Start button. Starts the one scheduler process (which ticks every realm), not a
        per-realm one — see schedsvc."""
        from .. import schedsvc
        if schedsvc.status(self.realm)["running"]:
            return {"ok": True, "already": True}
        return schedsvc.start()

    def _notify_test(self, body: dict) -> dict:
        """Send a sample notification down ONE channel, so 'does this actually reach me?' can be
        answered per destination. Bypasses the per-event grid on purpose — it's a delivery test."""
        from .. import notify as _n
        ch = str(body.get("channel") or "desktop")
        if ch not in _n.CHANNELS:
            return {"ok": False, "error": "Unknown channel."}
        if not _n.channel_enabled(ch):
            return {"ok": False, "error": f"{_n.CHANNELS[ch]} notifications are switched off in App settings."}
        title, msg = f"{brand.NAME} notifications are on", "This is what a notification looks like."
        if ch == "inapp":
            item = _n.record(self.realm, "test", title, msg, "/settings")
            return ({"ok": True, "detail": "added to the bell"} if item
                    else {"ok": False, "error": "Could not write to the notification feed."})
        # Off-realm channels are named for the realm, exactly as a real notification would be —
        # a delivery test that doesn't look like the thing it's testing isn't much of a test.
        if ch == "desktop":
            if os.name != "nt":
                return {"ok": False, "error": "Desktop notifications are Windows-only for now."}
            ok = _n.toast(title, msg, realm_root=self.realm)
            return {"ok": True, "detail": "sent to your desktop"} if ok else {
                "ok": False, "error": "Could not send the notification."}
        if ch == "telegram":
            from .. import telegram as _tg
            if not _tg.ready():
                return {"ok": False, "error": "Telegram isn't connected — set it up in App settings."}
            return ({"ok": True, "detail": "sent to Telegram"}
                    if _tg.send(f"{_n._titled(self.realm, title)}\n\n{msg}")
                    else {"ok": False, "error": "Telegram didn't accept the message."})
        return {"ok": False, "error": "Unknown channel."}

    # ---- Telegram setup ------------------------------------------------------------------------

    def _telegram_status(self):
        """GET handler: writes its own response (POST handlers return a dict; these don't)."""
        from .. import telegram as _tg
        s = _tg.status()
        s.pop("chat_id", None)          # not a secret, but no reason to echo it into a page
        self._json(200, {"ok": True, **s})

    def _telegram_token(self, body: dict) -> dict:
        from .. import telegram as _tg
        return _tg.save_token(str(body.get("token", "")))

    def _telegram_env(self, body: dict) -> dict:
        from .. import telegram as _tg
        return _tg.save_env_file(str(body.get("path", "")))

    def _telegram_link(self, body: dict) -> dict:
        from .. import telegram as _tg
        r = _tg.link_chat()
        if r.get("ok"):
            # Connecting is the whole point of switching the channel on, so do it rather than
            # leaving a connected integration that silently sends nothing.
            try:
                from .. import appconfig, notify as _n
                appconfig.save({"notify_telegram": True})
                _tg.register_commands(self.realm)
                _tg.send("ARMADA is connected. Send /agents to see who's here.")
                _ = _n
            except Exception:  # noqa
                swallowed(log, '_telegram_link: failed; ignored')
        return r

    def _telegram_forget(self, body: dict) -> dict:
        from .. import telegram as _tg, appconfig
        _tg.save_token("")
        _tg.save_env_file("")
        try:
            p = _tg._store_path()
            if p.exists():
                p.unlink()
        except OSError:
            pass
        appconfig.save({"notify_telegram": False})
        return {"ok": True}

    def _save_channels(self, body: dict) -> dict:
        """Persist the per-machine notification channel switches (~/.armada/config.json)."""
        from .. import appconfig, notify as _n
        try:
            upd = {}
            for c in _n.CHANNELS:
                key = f"notify_{c}"
                if key in body:
                    upd[key] = bool(body[key])
            appconfig.save(upd)
            return {"ok": True, "channels": _n.channels_enabled()}
        except Exception as e:  # noqa
            swallowed(log, '_save_channels: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _save_appearance(self, body: dict) -> dict:
        """Persist the per-app visual theme or colour mode (~/.armada/config.json).

        The mode used to live only in localStorage, written and never read — so it applied to the
        one page Settings navigated to and was lost on the next click. It belongs here, next to the
        theme: both are properties of this machine."""
        from .. import appconfig, vtheme
        from ..webui import layout as _layout
        mode = str(body.get("mode") or "").strip().lower()
        if mode:
            if mode not in _layout.APPEARANCE_MODES:
                return {"ok": False, "error": "unknown colour mode"}
            appconfig.save({"appearance": mode})
            return {"ok": True, "mode": mode}
        theme = str(body.get("theme") or "").strip()
        if theme not in vtheme.THEMES:
            return {"ok": False, "error": "unknown theme"}
        try:
            appconfig.save({"theme": theme})
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_save_appearance: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

