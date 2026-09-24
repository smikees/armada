"""Status dots must mean what the legend on the same page says they mean.

The Jobs page prints the 7-day health legend directly above a table of status dots. They were
coloured from two different palettes, crossed in both directions: `success` took
--color-accent-2 — the exact variable the legend labels "Running" — while `running` took
--status-warn, which the legend calls "Warning". A job that finished cleanly 21 hours ago showed
the colour for "in progress", with the key to read it by two inches higher up the page.
"""
from armada import status
from armada.webui import widgets


def _var(style: str) -> str:
    """The CSS variable a health-legend style is built from."""
    import re
    m = re.search(r"var\(--[a-z0-9-]+\)", style)
    return m.group(0) if m else ""


def test_success_is_the_legends_success_colour():
    assert status.color("ok") == "var(--status-ok)"
    assert _var(widgets._HEALTH_STYLES["Success"]) == "var(--status-ok)"


def test_running_is_the_legends_running_colour():
    assert status.color("running") == "var(--color-accent-2)"
    assert _var(widgets._HEALTH_STYLES["Running"]) == "var(--color-accent-2)"


def test_success_and_running_are_not_the_same_colour():
    """The bug in one line: 'finished' and 'in progress' rendered identically."""
    assert status.color("ok") != status.color("running")


def test_warning_and_failed_match_the_legend():
    assert status.color("warn") == _var(widgets._HEALTH_STYLES["Warning"])
    assert status.color("error") == _var(widgets._HEALTH_STYLES["Failed"])


def test_every_legend_state_has_a_distinct_meaning_in_the_palette():
    """Success / Running / Warning / Failed are four different things and must look it."""
    cols = {status.color(s) for s in ("ok", "running", "warn", "error")}
    assert len(cols) == 4, cols


def test_the_running_constant_agrees_with_the_palette():
    """The user-jobs table colours a running row from widgets._RUNNING_COLOR and the system table
    from status.color('running'); one page, so one colour."""
    assert widgets._RUNNING_COLOR == status.color("running")


def test_aliases_still_resolve_to_the_right_colour():
    for raw in ("ok", "OK", "done", "success", "ran"):
        assert status.color(raw) == "var(--status-ok)", raw
    for raw in ("error", "fail", "failed", "bad"):
        assert status.color(raw) == "var(--status-bad)", raw


def test_unknown_status_is_idle_grey():
    assert status.color("") == "var(--status-idle)"
    assert status.color("wat") == "var(--status-idle)"
