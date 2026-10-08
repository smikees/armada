"""Scheduler leases and durable daily attempts. A PID is diagnostic, never lock ownership.

The kernel lease prevents concurrent dispatch; the attempt record prevents replay after a crash.
Neither can make a provider's external side effects exactly once. See dev/PERSISTENCE.md.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
import tempfile
import time
from contextlib import contextmanager

from . import util


def _owner_path(root):
    return Path(root) / "scheduler.lock.json"


def _pause_path(root):
    key = hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode()).hexdigest()
    return Path(tempfile.gettempdir()) / "armada-realm-lifecycle" / (key + ".pause.json")


def lifecycle_paused(root):
    """External to the realm, so the folder can be recycled while dispatch is held."""
    data = util.read_json_state(_pause_path(root), default=dict, max_schema=1)
    if not data:
        return False
    if (type(data.get("pid")) is not int or type(data.get("expires")) not in (int, float)
            or not isinstance(data.get("token"), str)):
        raise util.StateError("Invalid realm lifecycle pause; scheduler dispatch is held.")
    return util.pid_alive(data["pid"]) and data["expires"] > time.time()


@contextmanager
def pause_for_lifecycle(root, timeout=5):
    """Called under realmops.lifecycle_lock. Cooperatively release the idle daemon lease."""
    path = _pause_path(root)
    token = uuid.uuid4().hex
    util.write_json_atomic(path, {"schema_version": 1, "pid": os.getpid(),
                                 "token": token, "expires": time.time() + 600})
    try:
        until = time.monotonic() + timeout
        while holder(root):
            if time.monotonic() >= until:
                raise util.StateError("The scheduler has not released this realm yet. Wait for its tasks to finish; if using an older ARMADA version, update and restart ARMADA before deleting it.")
            time.sleep(.05)
        yield
    finally:
        data = util.read_json_state(path, default=dict, max_schema=1)
        if data.get("token") == token:
            path.unlink(missing_ok=True)


def _stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Lease:
    """An open kernel lock, an unguessable incarnation token, and a non-reentrant tick gate."""

    def __init__(self, root, lock, token):
        self.root = Path(root).resolve()
        self.token = token
        self.pid = os.getpid()
        self._lock = lock
        self._gate = threading.Lock()
        self._closed = False

    def verify(self, root):
        if self._closed or self.pid != os.getpid() or self.root != Path(root).resolve():
            raise util.StateError("Scheduler lease is closed or belongs to another realm/process.")
        info = util.read_json_state(_owner_path(self.root), max_schema=1)
        if info.get("owner_token") != self.token:
            raise util.StateError("Scheduler ownership record changed; dispatch is held.")

    def close(self):
        # Wait for this lease's current tick before releasing its OS lock. An old handle cannot
        # release a newer incarnation, even when both happen to have the same PID.
        with self._gate:
            if self._closed:
                return
            if self.pid != os.getpid():
                raise util.StateError("Cannot release another process's scheduler lease.")
            try:
                info = util.read_json_state(_owner_path(self.root), default=dict, max_schema=1)
                if info.get("owner_token") == self.token:
                    _owner_path(self.root).unlink()
            except OSError:
                # Stale metadata is harmless: the kernel remains the source of ownership.
                pass
            finally:
                self._closed = True
                self._lock.__exit__(None, None, None)


def acquire(root) -> Lease | None:
    """Return exclusive ownership, None when busy; raise on any persistence error."""
    root = Path(root).resolve()
    if lifecycle_paused(root):
        return None
    util.assert_realm_writable(_owner_path(root))
    lock = util.file_lock(_owner_path(root), timeout=.05)
    try:
        lock.__enter__()
    except util.FileLockTimeout:
        return None
    try:
        if lifecycle_paused(root):
            lock.__exit__(None, None, None)
            return None
        old = util.read_json_state(_owner_path(root), default=dict, max_schema=1)
        # Compatibility guard for the old PID-only protocol. Upgrades must stop all old writers;
        # do not deliberately run over a known live old daemon, even one in this process.
        if old and "owner_token" not in old and util.pid_alive(old.get("pid")):
            lock.__exit__(None, None, None)
            return None
        token = uuid.uuid4().hex
        util.write_json_atomic(_owner_path(root), {
            "schema_version": 1, "pid": os.getpid(), "started": _stamp(), "owner_token": token,
        })
        return Lease(root, lock, token)
    except BaseException:
        lock.__exit__(None, None, None)
        raise


def holder(root):
    """Best-effort status; stale modern metadata is not evidence of a running scheduler."""
    path = _owner_path(root)
    try:
        info = util.read_json_state(path, max_schema=1)
        if "owner_token" not in info:
            return info if util.pid_alive(info.get("pid")) else None
        # Status never creates control files or needs to mutate a future-schema realm.
        if not path.with_name("." + path.name + ".lock").exists():
            return None
        try:
            with util.file_lock(path, timeout=0, validate_state=False):
                return None
        except util.FileLockTimeout:
            return util.read_json_state(path, max_schema=1)
    except OSError:
        return None


def release(lease: Lease):
    lease.close()


def _attempt_path(root, day):
    # Keep days separate: bounded read/modify/write cost, and no automatic deletion of evidence.
    dt.date.fromisoformat(day)
    return Path(root) / ".scheduler" / "attempts" / f"{day}.json"


def _key(agent, job):
    return hashlib.sha256(json.dumps([agent, job], ensure_ascii=True).encode()).hexdigest()


def _attempts(path):
    data = util.read_json_state(path, default=lambda: {"schema_version": 1, "attempts": {}}, max_schema=1)
    attempts = data.get("attempts")
    if not isinstance(attempts, dict):
        raise util.StateError("Invalid scheduler attempts; restore valid state before dispatch.")
    for key, entry in attempts.items():
        if (not isinstance(entry, dict) or entry.get("state") not in ("claimed", "finished")
                or not all(isinstance(entry.get(k), str) and entry[k]
                           for k in ("agent", "job", "day", "attempt_id", "owner_token", "started"))
                or key != _key(entry["agent"], entry["job"]) or entry["day"] != path.stem):
            raise util.StateError("Invalid scheduler attempt; dispatch is held.")
    return data


def claim(lease: Lease, agent, job, day):
    """Persist admission before side effects. Return (attempt, newly_claimed). Never replay."""
    lease.verify(lease.root)
    path, key = _attempt_path(lease.root, day), _key(agent, job)
    with util.file_lock(path):
        data = _attempts(path)
        existing = data["attempts"].get(key)
        if existing:
            return existing, False
        entry = {"agent": agent, "job": job, "day": day, "attempt_id": uuid.uuid4().hex,
                 "owner_token": lease.token, "state": "claimed", "started": _stamp()}
        data["attempts"][key] = entry
        util.write_json_atomic(path, data)
        return entry, True


def inspect_attempt(root, agent, job, day):
    """Advisory dry-run read; creates neither state nor lock files."""
    return _attempts(_attempt_path(root, day))["attempts"].get(_key(agent, job))


def resume_waiting(lease, agent, job, day):
    """Transfer a known finished-attempt backoff after a scheduler restart."""
    from . import job_retries
    lease.verify(lease.root)
    waiting = job_retries.pending(lease.root, agent, job)
    if not waiting or not job_retries.retryable(waiting.get('last_report', {})):
        raise util.StateError('No safely resumable retry is recorded.')
    path = _attempt_path(lease.root, day)
    with util.file_lock(path):
        data = _attempts(path)
        entry = data['attempts'].get(_key(agent, job))
        if not entry:
            raise util.StateError('Retry has no scheduler claim.')
        entry.update(owner_token=lease.token, state='claimed')
        util.write_json_atomic(path, data)
        return entry


def finish(lease: Lease, attempt, status):
    """Complete only our own claim; a failure leaves it uncertain and ineligible for replay."""
    lease.verify(lease.root)
    path = _attempt_path(lease.root, attempt["day"])
    with util.file_lock(path):
        data = _attempts(path)
        entry = data["attempts"].get(_key(attempt["agent"], attempt["job"]), {})
        if (entry.get("attempt_id") != attempt["attempt_id"]
                or entry.get("owner_token") != lease.token or entry.get("state") != "claimed"):
            raise util.StateError("Scheduler attempt ownership changed; result was not recorded.")
        entry.update(state="finished", status=status, finished=_stamp())
        util.write_json_atomic(path, data)
