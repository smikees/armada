"""Golden check: the exported Cabinet realm still parses and validates.
Locates Hand-realm via $ARMADA_TEST_REALM or common paths; skips if unavailable
(so the suite stays green on machines without the realm)."""
import os
from pathlib import Path
import pytest
from armada import reader, validate

_CANDIDATES = [
    os.environ.get("ARMADA_TEST_REALM", ""),
    "/sessions/kind-youthful-clarke/mnt/Work/Hand-realm",
    r"D:\Work\Hand-realm",
    str(Path(__file__).resolve().parents[2] / "Hand-realm"),
]


def _realm_path():
    for p in _CANDIDATES:
        if p and Path(p).is_dir():
            return p
    return None


realm_path = _realm_path()
needs_realm = pytest.mark.skipif(realm_path is None, reason="Hand-realm not found")


@needs_realm
def test_reads_expected_roster():
    realm = reader.read(realm_path)
    assert realm.coordinator is not None, "coordinator (hand) should be present"
    assert len(realm.agents) >= 5, "expected the full cabinet roster"
    # every agent has an id and display
    assert all(a.id and a.display for a in realm.agents)


@needs_realm
def test_jobs_have_schedules():
    realm = reader.read(realm_path)
    total_jobs = sum(len(a.jobs) for a in realm.agents)
    assert total_jobs > 0, "cabinet export should carry jobs"
    for a in realm.agents:
        for j in a.jobs:
            assert j.id and j.name


@needs_realm
def test_validate_reports_runnable():
    # validate.run prints a report and returns an exit code; 0 == runnable native realm
    assert validate.run(realm_path) == 0
