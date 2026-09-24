"""Support for the golden-HTML snapshot suite (Phase 0 of the refactor).

The refactor (splitting webui.py/serve.py into layers) must not change a single byte of
rendered output. To prove that, we render every page against a DETERMINISTIC fixture realm
— built fresh each run with pinned dates and fixed seed content — and compare the (lightly
normalized) HTML to committed golden files. Any drift fails the test.

Why a fixture and not the live Hand-realm: the live realm's data changes (new threads, runs,
memories), so it can't be a byte-stable oracle. The fixture is fixed by construction; the only
volatile output is the static cache-buster and real-time clock strings, which normalize() erases.
"""
from __future__ import annotations
import json
import socket
import threading
import time
import urllib.request
import re
from pathlib import Path


# ---- fixture realm -----------------------------------------------------------------------------

_PIN_DATE = "2026-01-01"


def build_fixture(dest: Path) -> str:
    """Create a deterministic 'crew' realm at dest and return its path (str).

    Seeds: user settings, one realm memory, one agent memory, one goal, one custom section,
    and a two-message thread — enough to exercise every render path. All dates are pinned so
    the output is stable across runs and machines.
    """
    import contextlib
    import io
    from armada import setup, goals, memory
    from armada.threads import Thread
    from armada import util

    dest = Path(dest)
    # scaffold prints a unicode arrow; swallow its stdout so it can't crash on a cp1252 console.
    with contextlib.redirect_stdout(io.StringIO()):
        setup.scaffold(str(dest), "crew", "Test Realm")

    # Pin realm.json: created date + owner facts + one custom section.
    rj = dest / "realm.json"
    cfg = json.loads(rj.read_text(encoding="utf-8-sig"))
    cfg["created"] = f"{_PIN_DATE}T00:00:00+00:00"
    cfg["user"] = {"name": "Test Owner", "timezone": "UTC", "gender": "Prefer not to say", "birthdate": ""}
    cfg["sections"] = [{"name": "Handbook", "path": "shared/handbook.md"}]
    util.write_json_atomic(rj, cfg)
    (dest / "shared" / "handbook.md").write_text("# Handbook\n\nFixture section content.\n", encoding="utf-8")

    # Pin each agent's appointed date.
    for aj in sorted((dest / "agents").glob("*/agent.json")):
        a = json.loads(aj.read_text(encoding="utf-8-sig"))
        a["appointed"] = _PIN_DATE
        util.write_json_atomic(aj, a)

    # A realm memory + an agent memory (deterministic bodies).
    (dest / "memory" / "house-style.md").write_text(
        "---\ntitle: House style\n---\nAlways answer in plain prose.\n", encoding="utf-8")
    cap = dest / "agents" / "captain"
    (cap / "memory").mkdir(exist_ok=True)
    (cap / "memory" / "prefs.md").write_text(
        "---\ntitle: Captain prefs\n---\nPrefers short status updates.\n", encoding="utf-8")

    # A goal.
    goals.save_goal(dest, "Reach open water", "Chart a course and sail.", status="", target="")

    # A two-message thread on the coordinator.
    Thread(cap, "main").append("Status?", "All hands accounted for.")

    # Pin the model catalog to the offline seed lineup with a fresh timestamp. Rendering a page
    # otherwise kicks a background live refresh (models._maybe_refresh_async) that, on a machine
    # with valid Claude creds, fetches the real /v1/models list and writes it into this fixture
    # mid-run — making model dropdowns/chips (overview, ministers, settings, new_agent) nondeterministic.
    # A fresh updated_at makes the cache look current, so no refresh fires; the seed matches the goldens.
    from armada import models as _models
    _cat = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "models": [{**m, "created_at": "", "active": True} for m in _models._SEED]}
    _cp = dest / ".armada"
    _cp.mkdir(parents=True, exist_ok=True)
    (_cp / "models.json").write_text(json.dumps(_cat, ensure_ascii=False, indent=2), encoding="utf-8")

    # Regenerate the managed System memory now that everything exists.
    memory.refresh_system_memory(dest, trigger="fixture")
    return str(dest)


# ---- in-process server harness -----------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# The instant every golden page is rendered at. Changing it means regolding the whole set, which
# is the point: the goldens are a snapshot, and a snapshot has a time.
GOLDEN_NOW = "2026-09-19T20:12:00"


class ServedRealm:
    """Start armada.serve in a daemon thread against `realm`; expose GET helpers.

    Isolates HOME/USERPROFILE to a temp dir so the global realm registry (~/.armada/realms.json)
    and other home-rooted state don't leak between runs or pollute the real machine — the realm
    switcher on Settings then lists exactly the fixture realm, keeping output deterministic.
    """

    def __init__(self, realm: str):
        import os
        import tempfile
        self.realm = realm
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self._home = tempfile.mkdtemp(prefix="mchome-")
        self._saved_env = {k: os.environ.get(k) for k in ("USERPROFILE", "HOME", "ARMADA_NO_MODEL_SYNC")}
        self._t = None

    def __enter__(self):
        import os
        from armada import clock, serve
        # Freeze the clock for the whole snapshot run. Without this the goldens carry TODAY in
        # them — weekday letters, dates, and (the part no amount of string-scrubbing can
        # normalise) which squares in a job's week strip read Scheduled versus Missed. The suite
        # went red every morning and the only remedy was to regold, which silently accepts
        # whatever the page has started saying. A fixed instant makes the snapshot a snapshot.
        #
        # A Saturday evening, mid-month, mid-week-window: the strip then spans a weekend in one
        # direction and weekdays in the other, so the fixture's crons exercise both.
        clock.freeze(GOLDEN_NOW)
        os.environ["USERPROFILE"] = self._home
        os.environ["HOME"] = self._home
        # On a machine with valid Claude creds the server force-refreshes the model catalog on boot
        # (serve.serve), which would overwrite the fixture's pinned seed with the live lineup mid-run
        # and make model dropdowns/chips nondeterministic. The kill-switch keeps the seed lineup.
        os.environ["ARMADA_NO_MODEL_SYNC"] = "1"
        self._t = threading.Thread(target=serve.serve, args=(self.realm, self.port), daemon=True)
        self._t.start()
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                urllib.request.urlopen(self.base + "/", timeout=0.5)
                return self
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("fixture server did not come up")

    def __exit__(self, *exc):
        import os
        import shutil
        from armada import clock
        clock.freeze(None)          # the rest of the suite runs on the real clock
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self._home, ignore_errors=True)
        return False

    def get(self, path: str) -> str:
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return r.read().decode("utf-8")

    def post(self, path: str, obj: dict) -> dict:
        data = json.dumps(obj).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


# ---- volatile-field normalization --------------------------------------------------------------

_SUBS = [
    (re.compile(r"\?v=\d+"), "?v=V"),                                   # static cache-buster (mtime)
    (re.compile(r"http://127\.0\.0\.1:\d+"), "http://127.0.0.1:PORT"),         # the content server's port (5.8a)
    (re.compile(r"\bv\d+\.\d+\.\d+\b"), "vX"),                          # app version string (bumps each release)
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]\d{2}:\d{2}"), "TS"),  # iso timestamps
    # Bare YYYY-MM-DD — the artefact filters render today's date into `max=`, so without this the
    # whole golden set fails the first time it is run on a different day from the last regold. Must
    # come after the ISO-timestamp rule above, which consumes the full-timestamp form first.
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "YYYY-MM-DD"),
    (re.compile(r"\b\d{2}-\d{2}-\d{2}\b"), "DD-MM-YY"),                 # dd-mm-yy dates
    (re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2}(st|nd|rd|th) \d{2}:\d{2}\b"), "NEXTRUN"),
    (re.compile(r"\b([01]\d|2[0-3]):[0-5]\d\b"), "HH:MM"),              # bare times
    # environment digest is machine-specific; blank the values so it's host-independent
    (re.compile(r"(Operating system|Machine|CPU|Memory|GPU|App): [^<\n]+"), r"\1: ENV"),
]


def normalize(html: str, realm: str = "") -> str:
    # The fixture realm lives in a random temp dir, so any absolute realm path embedded in the
    # page (e.g. Settings' data-flow note) is volatile — blank it in every slash/escaping form.
    if realm:
        for form in (realm, realm.replace("\\", "/"), realm.replace("\\", "\\\\")):
            html = html.replace(form, "REALM")
    for pat, repl in _SUBS:
        html = pat.sub(repl, html)
    return html


# ---- the routes we snapshot (HTML pages + a couple of stable JSON reads) ------------------------

def routes_for(realm_path: str) -> list[tuple[str, str]]:
    """(label, path) pairs. Agent/job/section paths are derived from the fixture."""
    r = [
        ("overview", "/"),
        ("ministers", "/ministers"),
        ("goals", "/goals"),
        ("jobs", "/jobs"),
        ("memory", "/memory"),
        ("capabilities", "/skills"),
        ("artefacts", "/artefacts"),
        ("settings", "/settings"),
        ("approvals", "/approvals"),
        ("docs", "/docs"),
        ("new_realm", "/new/realm"),
        ("new_agent", "/new/agent"),
        ("section_0", "/section/0"),
        ("agent_threads", "/agent/captain"),
        ("agent_jobs", "/agent/captain/jobs"),
        ("agent_capabilities", "/agent/captain/skills"),
        ("agent_memories", "/agent/captain/memories"),
        ("agent_artefacts", "/agent/captain/artefacts"),
        ("agent_inbox", "/agent/captain/inbox"),
        ("embed_thread", "/embed/thread?agent=captain&thread=main"),
    ]
    return r
