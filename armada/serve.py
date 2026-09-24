"""`armada serve` — the interactive local app (SPEC §13).

A real, clickable cockpit served on 127.0.0.1: browse agents and jobs, read each job's actual
prompt, **run** a job (mock or the live engine) and watch the output, ask "what's due now", and
one-click **Update & Restart** (git pull + hot re-exec). stdlib-only, local-only, no deps — the
engine underneath is the same runner/scheduler the CLI uses. Later this same UI gets wrapped in a
native window; today it's the browser reaching http://127.0.0.1:<port>.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from . import activerealm, reader, render, scheduler, util, brand, origins
from .util import safe_seg
from .routes import realm as routes_realm, agents as routes_agents, jobs as routes_jobs
from .routes import caps as routes_caps, catalogue as routes_catalogue, settings as routes_settings
from .routes import dashboard as routes_dashboard, _shared as routes_shared
from .routes._shared import _reg_ensure, _reg_load
from .util import swallowed

REPO = Path(__file__).resolve().parents[1]
log = logging.getLogger("armada.serve")


class Handler(routes_realm.RealmRoutes, routes_agents.AgentRoutes, routes_jobs.JobRoutes,
              routes_caps.CapabilityRoutes, routes_catalogue.CatalogueRoutes,
              routes_settings.SettingsRoutes, routes_dashboard.DashboardRoutes,
              routes_shared.SharedRoutes, http.server.BaseHTTPRequestHandler):
    realm = "."
    _streams: dict = {}          # tid -> running chat Popen (for stop)

    def _send(self, code, body, ctype="text/html; charset=utf-8", cache: str = ""):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        if getattr(self, "_sandbox_this", False):
            # Untrusted content served from the app's own origin — only when the content server
            # couldn't start (5.8a). Opaque origin: its scripts can reach nothing of the app's.
            self.send_header("Content-Security-Policy",
                             "sandbox allow-scripts allow-forms allow-popups allow-downloads allow-modals")
        if cache:
            # Cacheable static assets (CSS/JS/fonts). Safe because their <link>/<script> URLs carry a
            # ?v=<mtime> cache-buster that changes on Update & Restart, forcing a refetch of changed
            # files. Caching stops the per-navigation re-download of CSS/JS/fonts that made every page
            # change flash the fallback font and jump the layout.
            self.send_header("Cache-Control", cache)
        else:
            # HTML/JSON: never cache — a full-page navigation must always get fresh server-rendered UI.
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(b)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json; charset=utf-8")

    def _query(self):
        q = urllib.parse.urlparse(self.path).query
        return {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8-sig"))  # tolerate a stray BOM
        except Exception:  # noqa
            log.debug('_body: failed; returning a fallback', exc_info=True)
            return {}

    def _same_origin(self) -> bool:
        """CSRF guard: a local server is reachable by any page in the browser. Block a mutating
        request whose Origin doesn't match our Host. Requests with no Origin (curl, the app's
        own tooling, non-browser clients) have no cross-site vector, so they pass."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            return urllib.parse.urlparse(origin).netloc == self.headers.get("Host", "")
        except Exception:  # noqa
            log.debug('_same_origin: failed; returning a fallback', exc_info=True)
            return False

    # Names this server answers to. It only ever binds 127.0.0.1, so a request naming any other host
    # arrived through DNS rebinding: a web page whose own domain has been re-pointed at 127.0.0.1.
    # To the browser that page is then same-origin with us — it can read every GET and its POSTs
    # carry a matching Origin/Host pair, so _same_origin() alone waves them through — and a POST to
    # /api/chat-stream starts an agent turn that runs with the engine's permissions skipped.
    # Checking Host closes it: a rebound request still says the attacker's name.
    _LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return False
        if host.startswith("["):                       # [::1]:8756
            name = host[: host.find("]") + 1] if "]" in host else host
        else:
            name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        return name in self._LOCAL_HOSTS

    def _refuse_host(self) -> None:
        log.warning("refused request for %s with Host=%r (not a local name — DNS rebinding?)",
                    self.path, self.headers.get("Host"))
        self._send(421, "misdirected request", "text/plain")

    def log_message(self, *args):  # noqa — silence default per-request stderr spam; we log our own
        pass

    # A page on another origin — a website, or the content server's own untrusted pages (5.8a) — can
    # make the browser GET any URL here (an <img>, a link), and a few GETs change things (/switch,
    # /api/chat-stop). Browsers say where a request came from; refuse the ones from elsewhere. Static
    # files stay loadable; the app window's own navigations are same-origin or "none".
    _REFUSE_CROSS_SITE = True

    def _cross_site(self) -> bool:
        sfs = (self.headers.get("Sec-Fetch-Site") or "").lower()
        return self._REFUSE_CROSS_SITE and sfs in ("cross-site", "same-site") \
            and not urllib.parse.urlparse(self.path).path.startswith("/static/")

    def do_GET(self):
        self._sandbox_this = False             # per request, even on a kept-alive connection
        if not self._host_ok():
            self._refuse_host()
            return
        if self._cross_site():
            log.warning("refused cross-site GET %s (Sec-Fetch-Site=%s)", self.path,
                        self.headers.get("Sec-Fetch-Site"))
            self._send(403, "cross-site request refused", "text/plain")
            return
        try:
            self._route_get()
        except util.UnsafeSegment as e:
            self._send(400, f"bad request: {e}", "text/plain")
        except Exception:  # noqa — never crash the handler thread; log the traceback
            log.exception("GET %s failed", self.path)
            try:
                self._send(500, "internal error (see server log)", "text/plain")
            except Exception:  # noqa
                log.debug('do_GET: failed; ignored', exc_info=True)

    # Declarative routing: exact paths → handler-method name; prefix paths → (prefix, method) in
    # order. Handlers for exact routes take no args; prefix handlers take the request path.
    _REALM_PAGES = ("ministers", "goals", "jobs", "memory", "skills", "artefacts", "inbox")
    _GET_EXACT = {
        "/": "_get_index", "/index.html": "_get_index", "/settings": "_get_settings",
        "/approvals": "_get_approvals", "/docs": "_get_docs", "/new/realm": "_get_new_realm", "/switch": "_get_switch",
        "/api/pick-folder": "_get_pick_folder", "/api/check-update": "_get_check_update",
        "/api/chat-stop": "_get_chat_stop", "/api/realms": "_get_realms",
        "/api/retired-agents": "_get_retired_agents", "/api/catalogue": "_get_catalogue", "/add-section": "_get_add_section",
        "/new/agent": "_get_new_agent", "/new/job": "_get_new_job", "/embed/thread": "_get_embed_thread",
        "/api/threads": "_get_threads", "/api/proposals-count": "_get_proposals_count",
        "/api/agent-activity": "_get_agent_activity",
        "/api/thread-turns": "_get_thread_turns", "/api/thread-rail": "_get_thread_rail",
        "/api/job-calendar": "_get_job_calendar", "/api/usage": "_get_usage",
        "/api/usage-limits": "_get_usage_limits", "/api/auth-status": "_get_auth_status",
        "/api/notifications": "_get_notifications", "/api/system-jobs": "_get_system_jobs",
        "/api/telegram-status": "_telegram_status", "/api/scheduler-status": "_get_scheduler_status",
        "/api/skill-content": "_get_skill_content",
        "/realm-icon": "_get_realm_icon", "/user-avatar": "_get_user_avatar",
        "/thread-file": "_get_thread_file", "/api/realm": "_get_realm", "/api/job": "_get_job_detail",
    }
    _GET_PREFIX = [
        ("/edit-section/", "_get_edit_section"), ("/section-asset/", "_section_asset"),
        ("/section-raw/", "_section_raw"), ("/section/", "_get_section"), ("/job/", "_get_job"),
        ("/agent/", "_get_agent"), ("/avatar/", "_get_avatar"), ("/static/", "_static"),
        ("/docs/", "_get_doc_page"),
    ]

    # --- welcome mode (5.3): no realm open yet --------------------------------------------------
    # Every route below assumes a realm. With none, the server answers only what the first-run
    # page needs; any other page is the welcome page, and any other API call a plain refusal
    # (never a traceback from a handler reading realm files out of "").
    welcome_note = ""
    _WELCOME_GET = {"/api/pick-folder": "_get_pick_folder", "/api/auth-status": "_get_auth_status",
                    "/switch": "_get_switch"}
    _WELCOME_POST = {"/api/set-approot": "_set_approot", "/api/first-realm": "_first_realm",
                     "/api/new-realm": "_new_realm", "/api/auth-login": "_auth_login"}

    def _route_welcome_get(self, path: str):
        if path.startswith("/static/"):
            self._static(path)
        elif path in self._WELCOME_GET:
            getattr(self, self._WELCOME_GET[path])()
        elif path.startswith("/api/"):
            self._json(409, {"ok": False, "error": "no realm is open yet"})
        else:
            from .webui import welcome, layout as _layout
            self._send(200, welcome.render_welcome(_reg_load(), note=type(self).welcome_note,
                                                   dark=_layout.dark_default()))

    def _route_welcome_post(self, path: str):
        name = self._WELCOME_POST.get(path)
        if name:
            self._json(200, getattr(self, name)(self._body()))
        else:
            self._json(409, {"ok": False, "error": "no realm is open yet"})

    def _untrusted(self, path: str) -> bool:
        """Is this request for content ARMADA didn't write (5.8a)? Section pages always; a thread
        attachment only when it's a type that runs as a document (HTML, SVG, …)."""
        if path.startswith(("/section-raw/", "/section-asset/")):
            return True
        if path == "/thread-file":
            return origins.is_active(self._query().get("name", ""))
        return False

    def _route_get(self):
        path = urllib.parse.urlparse(self.path).path
        if not self.realm:
            self._route_welcome_get(path)
            return
        if self._untrusted(path):
            if origins.content_port():
                self.send_response(302)
                self.send_header("Location", origins.content_url(self.path))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._sandbox_this = True          # no content server: serve it here, sandboxed
        if path.lstrip("/") in self._REALM_PAGES:
            self._get_realm_page(path.lstrip("/"))
            return
        name = self._GET_EXACT.get(path)
        if name:
            getattr(self, name)()
            return
        for prefix, mname in self._GET_PREFIX:
            if path.startswith(prefix):
                getattr(self, mname)(path)
                return
        self._send(404, "not found", "text/plain")

    # --- GET handlers (one per route; wired through _GET_EXACT / _GET_PREFIX above) ---------------
    def _err_page(self, e, bare: bool = False):
        body = f"{e}" if bare else f"<h2>{brand.NAME}</h2><p>{e}</p>"
        self._send(200, f"<body style='font:15px system-ui;padding:24px'>{body}</body>")

    def _dark(self) -> bool:
        """Whether to render this page dark.

        Was `"dark" in self._query()` at a dozen call sites, which made the colour mode a property
        of the URL rather than a preference: it applied to the page Settings navigated to and was
        lost the moment you clicked anything. The ?dark=1 override stays, for embeds and for
        linking someone straight to a dark page."""
        from .webui import layout as _layout
        return ("dark" in self._query()) or _layout.dark_default()

    def do_POST(self):
        if not self._host_ok():
            self._refuse_host()
            return
        if not self._same_origin():
            log.warning("blocked cross-origin POST %s from Origin=%s", self.path, self.headers.get("Origin"))
            self._json(403, {"ok": False, "error": "cross-origin request blocked"})
            return
        try:
            self._route_post()
        except util.UnsafeSegment as e:
            self._json(400, {"ok": False, "error": f"bad request: {e}"})
        except Exception:  # noqa — never crash the handler thread; log the traceback
            log.exception("POST %s failed", self.path)
            try:
                self._json(500, {"ok": False, "error": "internal error (see server log)"})
            except Exception:  # noqa
                log.debug('do_POST: failed; ignored', exc_info=True)

    # Most POSTs are uniform: take the JSON body, return a dict that's sent as JSON. Path → method.
    _POST_JSON = {
        "/api/run": "_run", "/api/chat": "_chat", "/api/save-job": "_save_job",
        "/api/job-proposal": "_job_proposal", "/api/save-agent": "_save_agent",
        "/api/render-md": "_render_md",
        "/api/job-enable": "_job_enable", "/api/delete-job": "_delete_job",
        "/api/upload-avatar": "_upload_avatar", "/api/upload-realm-icon": "_upload_realm_icon",
        "/api/save-realm-settings": "_save_realm_settings", "/api/set-avatar-preset": "_set_avatar_preset",
        "/api/remove-avatar": "_remove_avatar", "/api/save-user": "_save_user",
        "/api/user-avatar": "_user_avatar_upload", "/api/user-avatar-preset": "_user_avatar_preset",
        "/api/user-avatar-remove": "_user_avatar_remove", "/api/new-thread": "_new_thread",
        "/api/save-dashboard": "_save_dashboard", "/api/section-snapshot": "_section_snapshot",
        "/api/thread-action": "_thread_action", "/api/thread-truncate": "_thread_truncate",
        "/api/reveal": "_reveal", "/api/refresh-system": "_refresh_system_ep",
        "/api/save-appearance": "_save_appearance",
        "/api/save-capability": "_save_capability", "/api/delete-capability": "_delete_capability",
        "/api/toggle-capability": "_toggle_capability", "/api/cap-permission": "_set_cap_permission",
        "/api/cap-update": "_update_capability_version", "/api/scan-updates": "_scan_updates",
        "/api/reveal-skill": "_reveal_skill", "/api/notify-test": "_notify_test",
        "/api/save-channels": "_save_channels",
        "/api/telegram-token": "_telegram_token", "/api/telegram-env": "_telegram_env",
        "/api/telegram-link": "_telegram_link", "/api/telegram-forget": "_telegram_forget",
        "/api/open-file": "_open_file", "/api/delete-artefact": "_delete_artefact",
        "/api/auth-login": "_auth_login", "/api/scheduler-start": "_scheduler_start",
        "/api/notifications-read": "_notifications_read",
        "/api/system-job-run": "_system_job_run", "/api/system-job-toggle": "_system_job_toggle",
        "/api/inbox-unread": "_inbox_unread", "/api/inbox-delete": "_inbox_delete",
        "/api/inbox-process": "_inbox_process",
        "/api/realm-archive": "_realm_archive", "/api/realm-export": "_realm_export",
        "/api/realm-delete": "_realm_delete",
        "/api/catalogue-refresh": "_catalogue_refresh", "/api/catalogue-add": "_catalogue_add",
        "/api/catalogue-reveal": "_catalogue_reveal",
        "/api/catalogue-review": "_catalogue_review", "/api/catalogue-add-link": "_catalogue_add_link",
        "/api/agent-retire": "_agent_retire", "/api/agent-reinstate": "_agent_reinstate",
        "/api/agent-delete": "_agent_delete",
        "/api/realm-preflight": "_realm_preflight", "/api/set-workspace": "_set_workspace",
        "/api/workspace-migrate": "_workspace_migrate", "/api/set-approot": "_set_approot",
        "/api/cap-grant": "_cap_grant", "/api/cap-revoke": "_cap_revoke",
        "/api/cap-request-approve": "_cap_request_approve",
        "/api/cap-request-reject": "_cap_request_reject",
        "/api/refresh-connectors": "_refresh_connectors", "/api/new-agent": "_new_agent",
        "/api/new-job": "_new_job", "/api/new-realm": "_new_realm", "/api/adopt-release": "_adopt_release", "/api/add-section": "_add_section",
        "/api/update-section": "_update_section", "/api/delete-section": "_delete_section",
        "/api/rename-section": "_rename_section", "/api/reorder-sections": "_reorder_sections",
        "/api/add-widget-section": "_add_widget_section",
        "/api/save-covenant": "_save_covenant",
        "/api/add-memory": "_add_memory", "/api/delete-memory": "_delete_memory",
        "/api/add-goal": "_add_goal", "/api/delete-goal": "_delete_goal",
        "/api/set-goal-agents": "_set_goal_agents",
    }

    def _route_post(self):
        path = urllib.parse.urlparse(self.path).path
        if not self.realm and path != "/restart":
            self._route_welcome_post(path)
            return
        if path == "/api/chat-stream":                      # streams its own response, not JSON
            self._chat_stream(self._body())
            return
        if path == "/update":                                # takes no body
            self._json(200, self._git_pull())
            return
        if path == "/api/dryrun":                            # 400-on-error, so kept explicit
            try:
                self._json(200, {"due": scheduler.tick(self.realm, engine="mock", dry_run=True)})
            except Exception as e:  # noqa
                swallowed(log, '_route_post: failed; reported to the caller')
                self._json(400, {"error": str(e)})
            return
        if path == "/restart":                               # reply first, then re-exec off-thread
            self._json(200, {"ok": True, "msg": "restarting"})
            threading.Thread(target=self._restart, daemon=True).start()
            return
        name = self._POST_JSON.get(path)
        if name:
            out = getattr(self, name)(self._body())
            # A handler returning None has already written its own response — /api/speak sends WAV
            # bytes, not JSON. Anything else is a dict for the usual envelope.
            if out is None:
                return
            self._json(200, out)
            return
        self._send(404, "not found", "text/plain")

    _CT = {".css": "text/css", ".ttf": "font/ttf", ".png": "image/png", ".svg": "image/svg+xml",
           ".js": "text/javascript", ".woff2": "font/woff2", ".gif": "image/gif", ".jpg": "image/jpeg",
           ".jpeg": "image/jpeg", ".webp": "image/webp", ".json": "application/json",
           ".ico": "image/x-icon", ".webmanifest": "application/manifest+json", ".woff": "font/woff",
           ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8"}

    def _static(self, path: str):
        rel = path[len("/static/"):].replace("..", "").lstrip("/")
        f = Path(__file__).resolve().parent / "webui" / "static" / rel
        if not f.is_file():
            self._send(404, "not found", "text/plain")
            return
        ct = self._CT.get(f.suffix.lower(), "application/octet-stream")
        # Cache static assets so navigating between pages doesn't re-download CSS/JS/fonts (which
        # flashed the fallback font and jumped the layout on every page change). The ?v= buster on
        # CSS/JS links forces a refetch when a file changes on Update & Restart.
        self._send(200, f.read_bytes(), ct, cache="public, max-age=604800")

    def _git_check(self) -> dict:
        """Fetch and report whether the local checkout is behind its upstream."""
        try:
            subprocess.run(["git", "-C", str(REPO), "fetch", "--quiet"],
                           capture_output=True, text=True, timeout=60)
            up = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "@{u}"],
                                capture_output=True, text=True, timeout=15)
            if up.returncode != 0:
                return {"ok": True, "newer": False, "error": "no upstream configured"}
            cnt = subprocess.run(["git", "-C", str(REPO), "rev-list", "--count", "HEAD..@{u}"],
                                 capture_output=True, text=True, timeout=15)
            behind = int((cnt.stdout or "0").strip() or "0")
            latest = ""
            desc = subprocess.run(["git", "-C", str(REPO), "describe", "--tags", "--abbrev=0", "@{u}"],
                                  capture_output=True, text=True, timeout=15)
            if desc.returncode == 0:
                latest = desc.stdout.strip().lstrip("v")
            return {"ok": True, "newer": behind > 0, "behind": behind, "latest": latest}
        except Exception as e:  # noqa
            log.debug('_git_check: failed; error returned to the caller', exc_info=True)
            return {"ok": True, "newer": False, "error": str(e)[:200]}

    def _git_pull(self) -> dict:
        try:
            r = subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only"],
                               capture_output=True, text=True, timeout=90)
            return {"ok": r.returncode == 0, "out": (r.stdout + r.stderr).strip()[:1500] or "up to date"}
        except Exception as e:  # noqa
            log.debug('_git_pull: failed; error returned to the caller', exc_info=True)
            return {"ok": False, "out": f"no git remote / {e}"}

    def _restart(self):
        time.sleep(0.4)
        # Hand the port over cleanly. os.execv replaces this process, but the launcher chain means
        # the listening socket can outlive the swap for a moment — long enough for the *new* image
        # to see a live server on 8756 and refuse to start as a duplicate of itself. Closing it
        # here makes the handover explicit rather than a race.
        try:
            self.server.socket.close()
        except Exception:  # noqa — best-effort; the exec below tears it down regardless
            log.debug('_restart: failed; ignored', exc_info=True)
        os.chdir(REPO)
        argv = [sys.executable, "-m", "armada", _launch_mode(), self.realm,
                "--port", str(self.server.server_address[1])]
        # Under pythonw nothing sees stderr, so a restart that fails to come back used to leave no
        # trace at all (seen once, 2026-09-24). Say what's about to run; the new process's own
        # start-up failures are logged by cli (see _serve_logged).
        log.info("restart: re-executing %s", argv)
        try:
            os.execv(sys.executable, argv)
        except OSError:
            log.exception("restart: re-exec failed; this process is exiting without a server")
            raise

    def log_message(self, *a):  # quiet
        pass


def _say(msg: str) -> None:
    """print() that survives having no console.

    Under pythonw.exe (how ARMADA.vbs starts the app) there is no stdout at all — sys.stdout is
    None — so a bare print() raises AttributeError. serve() runs on a daemon thread of the app
    process, so that exception killed the thread *after* the socket was bound but *before*
    serve_forever(): the app logged "serving on :8756", then nothing ever listened, and the window
    timed out waiting for a server that had already died. Console chatter must never be load-bearing.
    """
    try:
        if sys.stdout is not None:
            print(msg)
    except Exception:  # noqa — a broken/closed stream must not take the server down
        log.debug('_say: failed; ignored', exc_info=True)


def _launch_mode() -> str:
    """How this process was started: 'app' (native window) or 'serve' (headless).

    Update & Restart re-execs us, and it must come back the same way it went in. When `armada app`
    is running, serve.serve() is on a background thread of the app process — so re-execing a bare
    'serve' would silently swap the user's window for a headless server (the window just disappears
    and never returns). sys.argv still carries the original subcommand, so trust it.
    """
    for a in sys.argv[1:]:
        if a in ("app", "serve"):
            return a
    return "serve"


def _init_logging(realm: str) -> None:
    """Log to stderr and to ~/.armada/logs/armada.log (outside the versioned realm) so swallowed
    handler errors are visible during daily use and the stress test."""
    util.init_logging("armada.log")


class _Server(http.server.ThreadingHTTPServer):
    """The cockpit's HTTP server.

    Keeps SO_REUSEADDR (the socketserver default) on purpose: Update & Restart re-execs the
    process, and the port it just released sits in TIME_WAIT for up to two minutes. Without
    address reuse the restarted process cannot rebind its own port and the app never comes back.

    Duplicate instances are prevented by an explicit pre-bind check (`port_owner`) instead — see
    serve(). That's the right tool for the job: a TIME_WAIT socket refuses connections, so it
    can't be mistaken for a live server, while a real second instance answers immediately.
    """


def port_owner(port: int = 8756) -> bool:
    """True if something is already listening on the loopback port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.35)
        return s.connect_ex(("127.0.0.1", port)) == 0


class ContentHandler(Handler):
    """The content-only server (5.8a): the untrusted pages and nothing else — no API, no POST.

    It shares the app's realm (a class attribute read through inheritance, so /switch on the app
    moves both) and its handlers; only the routing differs. A different port is a different origin:
    what runs here can't read the app, and the app refuses its POSTs and its cross-site GETs.
    """
    _REFUSE_CROSS_SITE = False     # the app's own frames load it from :8756 — "same-site" by design

    def _route_get(self):
        path = urllib.parse.urlparse(self.path).path
        if not self.realm:
            self._send(404, "no realm open", "text/plain")
            return
        if path == "/thread-file":
            self._get_thread_file()
            return
        for prefix, mname in (("/section-raw/", "_section_raw"), ("/section-asset/", "_section_asset")):
            if path.startswith(prefix):
                getattr(self, mname)(path)
                return
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        self._send(403, "this server serves content only", "text/plain")


def start_content_server(port: int) -> int | None:
    """Bind the content server on `port` (the app's port + 1), or any free port if that one is still
    held — Update & Restart hands ports over, and for a moment the old process may keep it. Returns
    the port bound, or None if nothing could be (the app then sandboxes that content itself)."""
    deadline = time.monotonic() + 3.0
    for want in (port, 0):
        while True:
            try:
                httpd = _Server(("127.0.0.1", want), ContentHandler)
                break
            except OSError:
                if want == 0 or time.monotonic() > deadline:
                    httpd = None
                    break
                time.sleep(0.25)
        if httpd is not None:
            got = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, name="armada-content", daemon=True).start()
            origins.set_content_port(got)
            log.info("content server on :%s (untrusted pages, no API)", got)
            return got
    log.error("content server could not bind; untrusted pages will be sandboxed on the app's port")
    origins.set_content_port(None)
    return None


def serve(realm: str, port: int = 8756):
    Handler.realm = realm
    _init_logging(realm)
    # Refuse to start a second instance, before doing any other work. SO_REUSEADDR would otherwise
    # let the bind succeed on Windows while the OS kept routing connections to the process that
    # already owns the port — ARMADA would log "serving" and then answer nothing. Asking the port
    # whether anyone replies catches that without breaking restart-over-TIME_WAIT (a TIME_WAIT
    # socket doesn't accept connections, so it can't be mistaken for a live server).
    # Restart hands the port over from the outgoing process, so tolerate a brief overlap before
    # calling it a duplicate. A real second instance keeps answering and still fails here.
    deadline = time.monotonic() + 4.0
    while port_owner(port):
        if time.monotonic() > deadline:
            log.error("ARMADA: port %s already has a live server — is ARMADA already running?", port)
            raise OSError(f"port {port} is already serving — ARMADA may already be running")
        time.sleep(0.25)
    start_content_server(port + 1)
    if not realm:
        # First run (5.3): nothing to open yet. Serve the welcome page until a realm exists.
        try:
            httpd = _Server(("127.0.0.1", port), Handler)
        except OSError as e:
            log.error("ARMADA: could not bind port %s (%s)", port, e)
            raise
        log.info("ARMADA serving on :%s (no realm yet — welcome page)", port)
        _say(f"ARMADA app → http://127.0.0.1:{port}  (no realm yet — the page will set one up)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            _say("\nstopped.")
        return
    # Bring the realm's on-disk format up to date before anything reads it (Phase 2, 2.8).
    from . import realmformat
    realmformat.ensure(realm)
    try:
        from . import reader
        _reg_ensure(realm, reader.read(realm).name)
    except Exception:  # noqa - registry is best-effort
        swallowed(log, 'serve: failed; falling back')
        _reg_ensure(realm, Path(realm).name)
    # The model catalogue is refreshed by the 'model-catalog' system job, not on every boot — this
    # used to fire on each server start (so repeatedly during a working session, and never at all
    # if the app stayed shut). Here we only run it if it's actually due, which also covers the case
    # where the scheduler isn't running.
    try:
        from . import sysjobs as _sysjobs
        # ARMADA_NO_MODEL_SYNC (tests, the golden fixture): not even the boot-time run. It would
        # only record a skip, but on a background thread that races the first page render.
        if not os.environ.get("ARMADA_NO_MODEL_SYNC") and _sysjobs.due(realm, "model-catalog"):
            threading.Thread(target=lambda: _sysjobs.run_one(realm, "model-catalog"),
                             daemon=True).start()
    except Exception:  # noqa — upkeep must never block serving
        swallowed(log, 'serve: failed; ignored')
    try:
        httpd = _Server(("127.0.0.1", port), Handler)
    except OSError as e:
        log.error("ARMADA: could not bind port %s (%s)", port, e)
        raise
    log.info("ARMADA serving on :%s (realm=%s)", port, realm)
    _say(f"ARMADA app → http://127.0.0.1:{port}  (realm: {realm})")
    _say("  Ctrl-C to stop · click agents/jobs, Run a job, or ⟳ Update & Restart.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _say("\nstopped.")


# ---- the single-page app ------------------------------------------------------------------
APP_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ARMADA</title><style>
:root{--navy:#0b3f86;--teal:#12a3b8;--ink:#1f2a37;--bg:#eef1f5;--card:#fff;--line:#e2e8f0;--dim:#6b7688}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,sans-serif}
#bar{position:sticky;top:0;z-index:99;display:flex;gap:10px;align-items:center;background:var(--navy);color:#fff;padding:8px 14px}
#bar img{height:26px} #bar b{letter-spacing:.5px}
#bar .rn{font-weight:700} #bar .eng{opacity:.8;font-size:12px}
#bar button{background:#1b5aa8;color:#fff;border:0;border-radius:7px;padding:6px 11px;cursor:pointer;font:inherit}
#bar button.primary{background:var(--teal);font-weight:700}
#bar .msg{margin-left:auto;opacity:.9;font-size:12px}
.kpis{display:flex;gap:20px;padding:10px 16px;background:#f7faff;border-bottom:1px solid var(--line);flex-wrap:wrap}
.kpi b{color:var(--navy);font-size:18px} .kpi span{color:var(--dim);font-size:11px;display:block}
#main{display:grid;grid-template-columns:290px 1fr;gap:14px;max-width:1200px;margin:0 auto;padding:14px}
@media(max-width:760px){#main{grid-template-columns:1fr}}
.side{display:flex;flex-direction:column;gap:8px}
.acard{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--teal);border-radius:10px;padding:9px 11px;cursor:pointer}
.acard.coord{border-left-color:var(--navy);background:#f7faff} .acard.sel{outline:2px solid var(--teal)}
.acard .n{font-weight:700;color:var(--navy)} .acard .l{color:#7c8aa0;font-size:12px;font-style:italic}
.acard .meta{color:var(--dim);font-size:11px;margin-top:3px;display:flex;gap:10px;flex-wrap:wrap}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-height:60vh}
h2{font-size:15px;color:var(--navy);margin:0 0 4px} .sub{color:var(--dim);font-size:12px;margin-bottom:12px}
table{width:100%;border-collapse:collapse} th{text-align:left;font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--line);padding:4px 6px}
td{padding:6px;border-bottom:1px solid #f0f3f7;font-size:13px} tr.job{cursor:pointer} tr.job:hover{background:#f4f8ff}
.tag{display:inline-block;background:#eef2f8;border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:9.5px;color:#5a6b86;font-family:ui-monospace,Consolas,monospace}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}
.btn{background:var(--teal);color:#fff;border:0;border-radius:7px;padding:7px 13px;font-weight:700;cursor:pointer;font:inherit}
.btn.ghost{background:#eef2f8;color:var(--navy)} .btn:disabled{opacity:.5;cursor:default}
.prompt{background:#0b1220;color:#cfe3ff;border-radius:8px;padding:12px;white-space:pre-wrap;max-height:320px;overflow:auto;font-family:ui-monospace,Consolas,monospace;font-size:12px}
.out{background:#0b1220;color:#d6f5e0;border-radius:8px;padding:12px;white-space:pre-wrap;max-height:360px;overflow:auto;font-family:ui-monospace,Consolas,monospace;font-size:12px;margin-top:8px}
.crumb{color:var(--teal);cursor:pointer} .pill{border-radius:999px;padding:1px 8px;font-size:10px;font-weight:800}
.chip{display:inline-flex;gap:3px;background:#eef2f8;border:1px solid var(--line);border-radius:999px;padding:1px 7px;font-size:11px;font-family:ui-monospace,Consolas,monospace;margin:2px 3px 0 0}
</style></head><body>
<div id="bar">
  <img src="__LOGO__" alt="ARMADA" onerror="this.style.display='none'">
  <span class="rn" id="rn">ARMADA</span><span class="eng" id="eng"></span>
  <button class="primary" onclick="mcUpdate()">⟳ Update &amp; Restart</button>
  <button onclick="load()">↻ Reload</button>
  <button onclick="dueNow()">⏰ What's due</button>
  <span class="msg" id="msg"></span>
</div>
<div class="kpis" id="kpis"></div>
<div id="main"><div class="side" id="side"></div><div class="panel" id="panel">Loading…</div></div>
<script>
let R=null, sel=null;
const E=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SC={green:'#1f9d57',yellow:'#d9a218',red:'#d64545',planned:'#9aa4b2',unknown:'#9aa4b2'};
const JS={ok:['●','#1f9d57','ran'],quiet:['●','#1f9d57','ran'],warn:['▲','#d9a218','issues'],error:['✕','#d64545','error']};
async function load(){
  const m=document.getElementById('msg'); m.textContent='loading…';
  try{ R=await (await fetch('/api/realm',{cache:'no-store'})).json(); }
  catch(e){ document.getElementById('panel').textContent='error: '+e; return; }
  if(R.error){ document.getElementById('panel').innerHTML='<h2>ARMADA</h2><p>'+E(R.error)+'</p>'; m.textContent=''; return; }
  document.getElementById('rn').textContent=R.name;
  document.getElementById('eng').textContent=' · '+R.theme.collective+' · engine: '+R.engine;
  const t=R.telemetry;
  document.getElementById('kpis').innerHTML=
    kpi(t.agents,R.theme.agent+'s')+kpi(t.jobs,'jobs')+kpi(t.runs_30d,'runs · 30d')+
    kpi(t.tokens_30d?Math.round(t.tokens_30d/1000)+'k':'—','tokens · 30d')+
    kpi(t.cost_30d?'≈$'+t.cost_30d.toFixed(2):'—','api-equiv · 30d');
  const side=document.getElementById('side'); side.innerHTML='';
  if(R.coordinator) side.appendChild(acard(R.coordinator,true));
  R.agents.forEach(a=>side.appendChild(acard(a,false)));
  m.textContent='';
  if(sel){ const a=[R.coordinator,...R.agents].find(x=>x&&x.id===sel); if(a) showAgent(a); else showHome(); }
  else showHome();
}
const kpi=(v,l)=>`<div class="kpi"><b>${E(v)}</b><span>${E(l)}</span></div>`;
function acard(a,coord){
  const d=document.createElement('div'); d.className='acard'+(coord?' coord':'')+(sel===a.id?' sel':'');
  const c=SC[a.status]||SC.unknown;
  d.innerHTML=`<div class="n">${coord?'♛ ':''}${E(a.display)}</div><div class="l">${E(a.leader)}</div>
    <div class="meta"><span><span class="dot" style="background:${c}"></span>${E(a.status)}</span>
    <span>${a.jobs.length} jobs</span>${a.tokens_30d?'<span>'+Math.round(a.tokens_30d/1000)+'k tok</span>':''}</div>`;
  d.onclick=()=>{sel=a.id; load();};
  return d;
}
function showHome(){
  const p=document.getElementById('panel');
  let g=(R.gaps||[]).map(x=>`<li style="color:${x.kind==='warn'?'#a15c00':'#41506a'}">${E(x.label)}</li>`).join('');
  p.innerHTML=`<h2>${E(R.name)}</h2><div class="sub">Pick a ${E(R.theme.agent)} on the left to see its jobs. Root: <span class="mono">${E(R.root)}</span></div>
    <h2 style="margin-top:14px">Health &amp; gaps</h2><ul>${g}</ul>`;
}
function showAgent(a){
  sel=a.id;
  document.querySelectorAll('.acard').forEach(e=>e.classList.remove('sel'));
  const p=document.getElementById('panel');
  let rows=a.jobs.map(j=>{const s=JS[j.last_status]||['○','#9aa4b2','no telemetry'];
    return `<tr class="job" onclick="showJob('${a.id}','${j.id}')"><td>${E(j.name)} ${j.kind==='command'?'<span class=tag>cmd</span>':''}</td>
      <td class="mono" style="color:#6b7688">${E(j.cadence)}</td>
      <td style="color:${s[1]};white-space:nowrap">${s[0]} ${s[2]}${j.last_seen?' · '+E(j.last_seen):''}</td></tr>`;}).join('')
    ||'<tr><td colspan=3 style="color:#6b7688">No jobs.</td></tr>';
  let sk=a.skills.map(s=>`<span class="chip">${E(s.id)}${s.version!=='*'?'@'+E(s.version):''}</span>`).join('')||'<span style="color:#6b7688">none</span>';
  p.innerHTML=`<div class="sub"><span class="crumb" onclick="sel=null;showHome();document.querySelectorAll('.acard').forEach(e=>e.classList.remove('sel'))">← ${E(R.name)}</span></div>
    <h2>${a.is_coordinator?'♛ ':''}${E(a.display)} <span style="font-weight:400;color:#7c8aa0;font-style:italic;font-size:13px">${E(a.leader)}</span></h2>
    <div class="sub">${E(a.bulletin||'')}</div>
    <table><tr><th>Job</th><th>Cadence</th><th>Last run</th></tr>${rows}</table>
    <div style="margin-top:12px;font-size:12px;color:#41506a">Skills: ${sk}</div>`;
}
async function showJob(aid,jid){
  const p=document.getElementById('panel'); p.innerHTML='Loading job…';
  const j=await (await fetch('/api/job?agent='+encodeURIComponent(aid)+'&job='+encodeURIComponent(jid))).json();
  let runs=(j.runs||[]).map(r=>`<tr><td class=mono>${E((r.ts||'').slice(0,16))}</td><td style="color:${(JS[r.status]||['','#6b7688'])[1]}">${E(r.status)}</td><td>${E(r.summary||'')}</td></tr>`).join('')||'<tr><td colspan=3 style="color:#6b7688">no runs yet</td></tr>';
  const body=j.kind==='command'?`<div class="sub">command</div><div class="prompt">${E(j.run)}</div>`
                               :`<div class="prompt">${E(j.prompt||'(no prompt)')}</div>`;
  p.innerHTML=`<div class="sub"><span class="crumb" onclick="showAgent([R.coordinator,...R.agents].find(x=>x&&x.id==='${aid}'))">← ${E(aid)}</span></div>
    <h2>${E(j.name)} <span class="tag">${E(j.kind)}</span></h2>
    <div class="sub">cadence: <span class="mono">${E(j.cadence)}</span>${j.allow_tools?' · tools enabled':''}</div>
    ${body}
    <div style="margin-top:10px;display:flex;gap:8px;align-items:center">
      <button class="btn ghost" onclick="runJob('${aid}','${jid}','mock',this)">▶ Run (mock)</button>
      <button class="btn" onclick="runJob('${aid}','${jid}','claude',this)">▶ Run (claude)</button>
      <span id="runmsg" style="color:#6b7688;font-size:12px"></span>
    </div>
    <div id="out" class="out" style="display:none"></div>
    <h2 style="margin-top:16px;font-size:13px">Recent runs</h2><table><tr><th>When</th><th>Status</th><th>Summary</th></tr>${runs}</table>`;
}
async function runJob(aid,jid,engine,btn){
  const out=document.getElementById('out'), rm=document.getElementById('runmsg');
  out.style.display='block'; out.textContent='running ('+engine+')…'; rm.textContent='';
  document.querySelectorAll('.btn').forEach(b=>b.disabled=true);
  try{
    const r=await (await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:aid,job:jid,engine})})).json();
    out.textContent=r.output||'(no output)';
    rm.textContent=r.ok?'done ✓':'finished with errors';
    rm.style.color=r.ok?'#1f9d57':'#d64545';
  }catch(e){ out.textContent='error: '+e; }
  document.querySelectorAll('.btn').forEach(b=>b.disabled=false);
}
async function dueNow(){
  const m=document.getElementById('msg'); m.textContent='checking…';
  try{ const r=await (await fetch('/api/dryrun',{method:'POST'})).json();
    const d=r.due||[]; m.textContent=d.length?('due now: '+d.map(x=>x.agent+'/'+x.job).join(', ')):'nothing due right now';
  }catch(e){ m.textContent='error: '+e; }
}
async function mcUpdate(){
  const m=document.getElementById('msg'); m.textContent='pulling latest…';
  try{ const j=await (await fetch('/update',{method:'POST'})).json();
    m.textContent=(j.ok?'updated — restarting…':'update: '+(j.out||'no remote')+' — restarting…');
    await fetch('/restart',{method:'POST'});
    let n=0; const t=setInterval(async()=>{n++;try{await fetch('/api/realm',{cache:'no-store'});clearInterval(t);load();}catch(e){if(n>40){clearInterval(t);m.textContent='reload manually';}}},400);
  }catch(e){ m.textContent='error: '+e; }
}
load();
</script></body></html>"""
