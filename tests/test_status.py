"""Canonical run-status vocabulary: normalisation, badness, colours (armada.status)."""
from armada import status


def test_normalize_maps_known_spellings():
    assert status.normalize("ok") == status.SUCCESS
    assert status.normalize("DONE") == status.SUCCESS
    assert status.normalize(" Ran ") == status.SUCCESS
    assert status.normalize("quiet") == status.QUIET
    assert status.normalize("warning") == status.WARN
    assert status.normalize("issues") == status.WARN
    assert status.normalize("error") == status.FAILED
    assert status.normalize("fail") == status.FAILED
    assert status.normalize("failed") == status.FAILED
    assert status.normalize("running") == status.RUNNING
    assert status.normalize("missed") == status.MISSED
    assert status.normalize("scheduled") == status.SCHEDULED
    assert status.normalize("planned") == status.IDLE


def test_normalize_unknown_and_empty_are_blank():
    assert status.normalize("") == ""
    assert status.normalize(None) == ""
    assert status.normalize("wat") == ""


def test_is_bad_only_for_warn_and_failed():
    assert status.is_bad("error") is True
    assert status.is_bad("warning") is True
    assert status.is_bad("ok") is False
    assert status.is_bad("running") is False
    assert status.is_bad("") is False
    assert status.is_bad(None) is False


def test_color_maps_to_css_vars_and_idle_fallback():
    # These follow the 7-day health legend printed above the jobs tables; test_status_palette
    # holds the two together. They used to be crossed — success wore the legend's "Running"
    # colour and running wore its "Warning" one.
    assert status.color("ok") == "var(--status-ok)"
    assert status.color("quiet") == "var(--status-ok)"
    assert status.color("warn") == "var(--status-warn)"
    assert status.color("running") == "var(--color-accent-2)"
    assert status.color("error") == "var(--status-bad)"
    assert status.color("scheduled") == "var(--status-idle)"
    # unknown / empty → idle grey, never a crash
    assert status.color("wat") == "var(--status-idle)"
    assert status.color(None) == "var(--status-idle)"
