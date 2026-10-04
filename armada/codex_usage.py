"""Account-wide OpenAI limits through Codex's authenticated app-server protocol.

No credentials are read by Armada and no model turn is started. The short-lived subprocess
only initializes and reads account/rateLimits/read; failures never become a fabricated 0%.
"""
from __future__ import annotations
from .background import process_options

import datetime as dt
import json
import math
import queue
import subprocess
import threading
import time

from .engine.codex import CodexEngine, _feature_args, _NO_WINDOW
from .usage_api import _countdown

_LOCK = threading.Lock()
_CACHE = {"at": 0.0, "data": None}
_TTL = 60
_PLAN_WARMING = False
_PLAN_LOCK = threading.Lock()


def _read_limits(timeout=20) -> dict:
    launcher = CodexEngine()._launcher()
    if not launcher:
        raise FileNotFoundError("Codex CLI is not installed.")
    # Suppress unrelated integrations. Account reads require no thread, MCP server or tool.
    proc = subprocess.Popen(launcher + _feature_args() + ["app-server"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", **process_options())
    replies = queue.Queue()

    def read():
        try:
            for line in proc.stdout:
                try:
                    replies.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            replies.put(None)

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    deadline = time.monotonic() + timeout

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def response(rid):
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex limits request timed out.")
            try:
                msg = replies.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("Codex limits request timed out.") from None
            if msg is None:
                raise RuntimeError("Codex closed the limits connection.")
            if not isinstance(msg, dict) or msg.get("id") != rid:
                continue
            if "error" in msg:
                # Do not expose arbitrary server data or account identifiers in page chrome.
                raise RuntimeError("Codex could not read account limits. Check its ChatGPT sign-in.")
            return msg.get("result") or {}

    try:
        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "armada", "title": "Armada", "version": "1.0"}}})
        response(1)
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "account/rateLimits/read"})
        return response(2)
    finally:
        # The app-server would otherwise stay alive waiting for another client request.
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        worker.join(timeout=1)
        proc.stdin.close()
        proc.stdout.close()


def _window(raw, fallback):
    if not isinstance(raw, dict):
        return None
    pct = raw.get("usedPercent")
    if not isinstance(pct, (int, float)) or isinstance(pct, bool) or not math.isfinite(pct):
        return None
    minutes = raw.get("windowDurationMins")
    label = fallback
    if (isinstance(minutes, (int, float)) and not isinstance(minutes, bool)
            and math.isfinite(minutes) and minutes > 0):
        label = ("Weekly" if minutes == 10080 else
                 f"{minutes / 1440:g}d window" if minutes >= 1440 else
                 f"{minutes / 60:g}h window" if minutes >= 60 else f"{minutes:g}m window")
    else:
        minutes = None
    resets = raw.get("resetsAt")
    stamp = ""
    if isinstance(resets, (int, float)):
        try:
            stamp = dt.datetime.fromtimestamp(resets, dt.timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            pass
    return {"label": label, "window_minutes": minutes, "pct": round(max(0, min(100, pct)), 1),
            "resets_at": stamp, "resets_in": _countdown(stamp) if stamp else ""}


def _normalize(raw):
    if not isinstance(raw, dict):
        raw = {}
    buckets = raw.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict) or not buckets:
        legacy = raw.get("rateLimits")
        buckets = {"codex": legacy} if isinstance(legacy, dict) else {}
    groups = []
    legacy = raw.get("rateLimits")
    plan = str(legacy.get("planType") or "") if isinstance(legacy, dict) else ""
    for key, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        if key == "codex":
            plan = str(bucket.get("planType") or plan)
        windows = [w for w in (_window(bucket.get("primary"), "Primary"),
                              _window(bucket.get("secondary"), "Secondary")) if w]
        if windows:
            groups.append({"id": key, "name": bucket.get("limitName") or key, "windows": windows})
    if not groups:
        return {"available": False, "message": "OpenAI limits are unavailable for this Codex login. "
                "ChatGPT subscription limits require a ChatGPT sign-in."}
    groups.sort(key=lambda g: (g["id"] != "codex", g["name"]))
    return {"available": True, "groups": groups, "plan": plan, "stale": False, "age_sec": 0}


def fetch():
    """Cache account readings for one minute, including failures; never block a page render."""
    with _LOCK:
        now = time.time()
        if _CACHE["data"] is not None and now - _CACHE["at"] < _TTL:
            return _CACHE["data"]
        try:
            data = _normalize(_read_limits())
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            data = {"available": False, "message": "OpenAI limits could not be read. "
                    "Check Codex sign-in in Settings; this will retry shortly."}
        _CACHE.update(at=time.time(), data=data)
        return data


def cached_plan() -> str:
    """Return a known plan without delaying provider cards on an account probe."""
    global _PLAN_WARMING
    data = _CACHE["data"] or {}
    plan = data.get("plan", "")
    if time.time() - _CACHE["at"] >= _TTL:
        with _PLAN_LOCK:
            if not _PLAN_WARMING:
                _PLAN_WARMING = True
                def warm():
                    global _PLAN_WARMING
                    try:
                        fetch()
                    finally:
                        _PLAN_WARMING = False
                threading.Thread(target=warm, daemon=True).start()
    return plan
