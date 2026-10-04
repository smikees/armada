"""Golden check: the exported Cabinet realm still parses and validates.
Only reads a realm named explicitly with --live-realm; default tests never discover personal data."""
import os
from pathlib import Path
import pytest
from armada import reader, validate

@pytest.fixture(scope="module")
def realm_path(request):
    value = request.config.getoption("--live-realm")
    if not value:
        pytest.skip("Live realm checks require an explicit --live-realm path")
    if not Path(value).is_dir():
        pytest.fail("--live-realm is not a directory")
    return value


def test_reads_expected_roster(realm_path):
    realm = reader.read(realm_path)
    assert realm.coordinator is not None, "coordinator (hand) should be present"
    assert len(realm.agents) >= 5, "expected the full cabinet roster"
    # every agent has an id and display
    assert all(a.id and a.display for a in realm.agents)


def test_jobs_have_schedules(realm_path):
    realm = reader.read(realm_path)
    total_jobs = sum(len(a.jobs) for a in realm.agents)
    assert total_jobs > 0, "cabinet export should carry jobs"
    for a in realm.agents:
        for j in a.jobs:
            assert j.id and j.name


def test_validate_reports_runnable(realm_path):
    # validate.run prints a report and returns an exit code; 0 == runnable native realm
    assert validate.run(realm_path) == 0
