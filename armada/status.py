"""Canonical run-status vocabulary — one place that knows the statuses a job/run can be in, how to
normalise the many raw spellings into them, and their colours. Imported by reader/webui so status
handling isn't re-derived (and allowed to drift) in each module.
"""
from __future__ import annotations

# the canonical statuses
SUCCESS, WARN, FAILED, RUNNING, QUIET, MISSED, SCHEDULED, IDLE = (
    "success", "warn", "failed", "running", "quiet", "missed", "scheduled", "idle")

# every raw spelling we've seen → its canonical status
_ALIASES = {
    "ok": SUCCESS, "success": SUCCESS, "done": SUCCESS, "ran": SUCCESS,
    "quiet": QUIET,
    "warn": WARN, "warning": WARN, "issues": WARN,
    "error": FAILED, "fail": FAILED, "failed": FAILED, "bad": FAILED,
    "run": RUNNING, "running": RUNNING,
    "missed": MISSED, "scheduled": SCHEDULED,
    "idle": IDLE, "none": IDLE, "planned": IDLE, "unknown": IDLE,
}

# Canonical status → CSS custom property used to colour it in the UI.
#
# These MUST agree with the 7-day health legend (webui.widgets._HEALTH_STYLES), because the two sit
# on the same screen: the Jobs page prints the legend directly above a table of status dots. They
# used to be crossed in both directions — success took --color-accent-2, the exact variable the
# legend labels "Running", while running took --status-warn, which the legend calls "Warning". So a
# job that had finished cleanly 21 hours ago showed the colour for "in progress", and the key to
# read it by was two inches above.
#
# One vocabulary, one palette. Anything that colours a run status goes through here.
COLOR = {
    SUCCESS: "var(--status-ok)", QUIET: "var(--status-ok)",
    WARN: "var(--status-warn)", FAILED: "var(--status-bad)",
    RUNNING: "var(--color-accent-2)", MISSED: "var(--status-idle)",
    SCHEDULED: "var(--status-idle)", IDLE: "var(--status-idle)",
}
_IDLE_COLOR = "var(--status-idle)"


def normalize(raw) -> str:
    """Map a raw status string to its canonical form ('' if unrecognised/empty)."""
    return _ALIASES.get(str(raw or "").strip().lower(), "")


def is_bad(raw) -> bool:
    """True for statuses that should draw attention (a warning or an outright failure)."""
    return normalize(raw) in (WARN, FAILED)


def color(raw) -> str:
    """CSS colour for a raw status (idle grey when unknown)."""
    return COLOR.get(normalize(raw), _IDLE_COLOR)
